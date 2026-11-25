#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["tqdm"]
# ///
"""srv round 1: review every (unit, perspective) task with independent omp reviewer sessions.

A task is one review unit of `rv/bin/plan-units.py` and one perspective that
`design.py` picked for it from the catalog: a value, the changes it judges, its depth (the level of
abstraction it judges at, high or low), and checks that each name their means.
Each task is `--samples` independent reviewer sessions (samples, `reviewer.py`),
whose findings are pooled, because one session misses causes another finds; all
samples of all tasks run at once, so the round takes about as long as its slowest
session. A session gets the brief (`references/brief.md`), the perspective with the
catalog perspective it was picked as and the rules attached to it, the requirement copies, the unit's hunks, the unit's
files at the head with line numbers, and the lines elsewhere in the head that name a
symbol the hunks define or change, and opens the rest of the head with its read
tools, and runs counterexamples with `sandbox_run` where a check's means is `execute`. The
answer is held to a JSON Schema, validated here, retried once when invalid, and its
finding lines are re-located from their anchors (`anchor-findings.py`).

`request_json` and `run_round` take the call that sends a request as a parameter:
srv passes the reviewer session, and prv (`~/.agents/skills/prv/bin/sweep.py`) keeps
the default, one HTTP structured-output call (`call_model`), whose refusals (an
overloaded server, an open circuit breaker, a dropped connection) wait and are sent
again.

Coverage is this script's job: it exits 1 when any task has no valid output,
because a task without output is a unit the swarm did not review.

Usage:
  uv run sweep.py --units units.json --diff diff.patch --repo HEAD_WORKTREE \
      --design design --requirements FILE [FILE ...] --out round-1 \
      --base-url URL --model MODEL [--api-key-env NAME] [--max-concurrency 128]
Exit codes: 0 every task has a valid output, 1 some task failed, 2 bad input.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import functools
import hashlib
import http.client
import importlib.util
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]
BRIEF_PATH = Path(__file__).resolve().parents[1] / "references" / "brief.md"
CATALOG = Path(__file__).resolve().parents[1] / "references" / "perspectives"
# What a change makes different, for someone who uses the code (`references/changes.md`); every change set element has
# one kind, and every catalog perspective names the kinds it is at stake in.
CHANGE_KINDS = (
    "returned_value", "stored_data", "state_and_ownership", "failure_result", "resource_use",
    "interface_and_name", "documented_promise", "test_contract", "external_contract",
)
# `structure` is a stake, not a change kind: the changes whose `structure.alters` is true, whatever their kind.
STAKE_KINDS = (*CHANGE_KINDS, "structure")
# What a change-set element touches beyond its kind, tagged by the change-set call so that code alone can decide which
# catalog perspectives a change picks (REVIEW-TECHNIQUES.md 6.2, step 3); `references/changes.md` defines each tag.
CHANGE_TAGS = (
    "fix", "feature", "layout", "new_unit", "new_logic", "concurrency", "resource", "trust_boundary", "model_call",
    "test_setup", "design_decision", "input", "io_or_parse", "serialized", "computation", "query", "sink",
    "user_interface", "claim",
)
DEPTHS = ("high", "low")
# A perspective's depth is the level of abstraction its value is judged at. The user's words (2026-11-24), after a lead
# had read the depth as read, trace, and execute: "하이레벨 로우레벨을 말한거다."
DEPTH_MEANINGS = {
    "high": "the value is judged on structure: the concepts the change introduces or handles and how each is "
    "represented, the data model and the invariants it can or cannot enforce, where each responsibility is placed, and "
    "the module boundaries. A counterexample is a structure, not one input: name every location that shows it, and "
    "search /work and the files of the whole change for the other places that hold or test the same concept",
    "low": "the value is judged on behaviour inside the functions the change touches: branches, boundary inputs, "
    "failure paths, and what each line does. A counterexample is an input and the path it takes, with the result that "
    "shows the value lowered",
}
MEANS_MEANINGS = (
    "Means of a check: `read`, the request and the lines it shows decide it; `trace`, follow callers, callees, or data "
    "with your tools to where the behaviour ends; `execute`, run the counterexample with `sandbox_run`, or, when no fake "
    "can stand for an external system, quote the sentence of its official documentation that decides it"
)
SEVERITIES = ("BLOCKER", "MAJOR", "MINOR", "NIT")
HEAD_CHARS_PER_UNIT = 60_000
WINDOW_LINES = 60
CALLER_LINES_PER_SYMBOL = 15
CALLER_LINES_TOTAL = 150
SYMBOL_RES = (
    re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)"),
    re.compile(r"^\s*class\s+([A-Za-z_]\w*)"),
    re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+([A-Za-z_]\w*)"),
    re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)"),
    re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)"),
)
HUNK_CONTEXT_RE = re.compile(r"^@@[^@]*@@\s*(.*)$")
# A server that refuses a call (overloaded, or a router whose circuit breaker is open) is waited for, not counted as
# a failed attempt: on 2026-11-20 the vllm-router on 100.99.0.1:8000 opened its circuit for 61 s after send errors to
# its workers, and 197 of 234 tasks failed because both attempts of each call came back refused within one second.
REFUSED_STATUSES = frozenset({429, 502, 503, 504})
REFUSAL_WINDOW_S = 900.0
BACKOFF_BASE_S = 2.0
BACKOFF_CAP_S = 60.0
# What a call reports and the round sums; `tool_calls` comes only from reviewer sessions.
USAGE_KEYS = ("prompt_tokens", "completion_tokens", "tool_calls")
PACK_FILE = "pack.md"  # the context pack `context.py` writes and every request of a review starts with

FINDINGS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["findings", "checked"],
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "severity", "file", "line", "anchor", "condition", "evidence", "fix"],
                "properties": {
                    "id": {"type": "string"},
                    "severity": {"type": "string", "enum": list(SEVERITIES)},
                    "file": {"type": "string"},
                    "line": {"type": "integer"},
                    "anchor": {"type": "string"},
                    "condition": {"type": "string"},
                    "evidence": {"type": "string"},
                    "fix": {"type": "string"},
                },
            },
        },
        "checked": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["item", "location", "result"],
                "properties": {
                    "item": {"type": "string"},
                    "location": {"type": "string"},
                    "result": {"type": "string"},
                },
            },
        },
    },
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolves annotations through sys.modules
    spec.loader.exec_module(module)
    return module


plan_units = load_module("plan_units", SKILLS / "rv" / "bin" / "plan-units.py")
anchor_findings = load_module("anchor_findings", Path(__file__).resolve().with_name("anchor-findings.py"))
reviewer = load_module("srv_reviewer", Path(__file__).resolve().with_name("reviewer.py"))


# srv's inspectors answer in this schema: prv's FINDINGS_SCHEMA plus `questions`, what the inspector could not decide
# inside its own perspective and asks the perspective that judges another change. `checked` rows hold what was
# observed at each location, not whether the value holds: a separate judge decides the value from them (team.py).
INSPECTION_SCHEMA = {
    **FINDINGS_SCHEMA,
    "required": [*FINDINGS_SCHEMA["required"], "questions"],
    "properties": {
        **FINDINGS_SCHEMA["properties"],
        "questions": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["about", "question"],
            "properties": {"about": {"type": "string"}, "question": {"type": "string"}},
        }},
    },
}


@dataclass(frozen=True)
class Task:
    unit: dict
    perspective: str

    @property
    def name(self) -> str:
        return f"{self.unit['id']}__{self.perspective}"


RECORD_SOURCE_PREFIXES = ("requirement:", "rule:")


@dataclass(frozen=True)
class CatalogPerspective:
    """One perspective of srv's catalog (`references/perspectives/<id>.md`): a review yardstick fixed before any change
    is seen, from which each review picks the ones its change has (the user, 2026-11-24, after a lead had let code
    build a perspective per value source, 266 of them on PR #1726: "관점은 코드에서 찾는게 아니라 미리 정해진 검토
    관점 중에서 코드 변경에 관련된 걸 고르는거다."). It holds one core `value`, the `depth` it is judged at (`high`:
    structure, wide and shallow; `low`: behaviour inside functions, narrow and deep), the `picks` that select it (change
    kinds, `structure`, and change tags), the `when` sentence those picks stand for, the `broken_if` frame whose 〈〉
    slots a review fills with this change's names, whether a review of it must run something (`execute`), and its
    `sources`. The list is REVIEW-TECHNIQUES.md section 4."""

    id: str
    title: str
    value: str
    when: str
    broken_if: str
    depth: str
    picks: tuple[str, ...]
    execute: bool = False
    sources: str = ""


def catalog_problems(catalog: dict[str, CatalogPerspective]) -> list[str]:
    """What a catalog lacks for a review to cover every change by construction; empty when it is complete. A review
    only picks from the catalog, and a change always has a kind but not always a tag, so a kind that no `low`
    perspective picks by kind, structure that no `high` one picks, or external contracts that no `execute` one picks
    would leave changes nobody judges."""
    problems = []
    low = {pick for p in catalog.values() if p.depth == "low" for pick in p.picks}
    if missing := [kind for kind in CHANGE_KINDS if kind not in low]:
        problems.append(f"change kinds {missing} are picked by no `low` perspective, so changes of those kinds would be "
                        "judged line by line by nobody; give a low perspective those kinds")
    if not any(p.depth == "high" and "structure" in p.picks for p in catalog.values()):
        problems.append("no `high` perspective picks `structure`, so a structural change would be judged only at low "
                        "level, where a structural defect shows as its symptoms")
    if not any(p.execute and "external_contract" in p.picks for p in catalog.values()):
        problems.append("no `execute` perspective picks `external_contract`, so what an external program does with what "
                        "the code builds would be decided by reading the code that assumes it")
    return problems


CATALOG_FIELD_RE = re.compile(r"^(Value|Picked when|Broken if|Sources): (.+)$", re.MULTILINE)


def read_catalog(directory: Path = CATALOG) -> dict[str, CatalogPerspective]:
    """The perspective catalog, one file per perspective with `id`, `depth`, `picks`, and optional `execute` in its
    front matter and `Value:`, `Picked when:`, `Broken if:`, `Sources:` lines in its body, checked field by field and
    for coverage; a catalog that fails raises ValueError naming what to fix, since a review picks only from it."""
    catalog: dict[str, CatalogPerspective] = {}
    problems: list[str] = []
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        head, _, body = text.removeprefix("---\n").partition("\n---\n")
        meta = dict(line.split(": ", 1) for line in head.splitlines() if ": " in line)
        fields = dict(CATALOG_FIELD_RE.findall(body))
        title = next((line[2:].strip() for line in body.splitlines() if line.startswith("# ")), "")
        picks = tuple(pick.strip() for pick in meta.get("picks", "").split(",") if pick.strip())
        wrong = [f"no `{key}:` line" for key in ("Value", "Picked when", "Broken if", "Sources") if not fields.get(key)]
        if meta.get("id") != path.stem or path.stem in catalog:
            wrong.append("`id` is not the file name")
        if meta.get("depth") not in DEPTHS:
            wrong.append(f"depth is not one of {DEPTHS}")
        if not picks or set(picks) - set(STAKE_KINDS) - set(CHANGE_TAGS):
            wrong.append(f"picks {list(picks)} are not a non-empty list of change kinds, `structure`, or tags {CHANGE_TAGS}")
        if wrong:
            problems.append(f"{path.name}: " + "; ".join(wrong))
            continue
        catalog[path.stem] = CatalogPerspective(path.stem, title.removeprefix(path.stem).strip(), fields["Value"], fields["Picked when"],
                                                fields["Broken if"], meta["depth"], picks, meta.get("execute") == "true",
                                                fields["Sources"])
    if not catalog and not problems:
        problems.append("no perspective file")
    problems += catalog_problems(catalog) if not problems else []
    if problems:
        raise ValueError(f"{directory}: " + " | ".join(problems))
    return catalog


def catalog_text(catalog: dict[str, CatalogPerspective], perspective_ids) -> str:
    """The named catalog perspectives as a request shows them."""
    rows = []
    for pid in perspective_ids:
        p = catalog[pid]
        run = " Decided by a run." if p.execute else ""
        rows.append(f"- {pid} {p.title} ({p.depth}): {p.value}. Picked when: {p.when}. Broken if: {p.broken_if}.{run}")
    return "\n".join(rows)


def catalog_id(source: object, catalog) -> str | None:
    """The catalog perspective a check's source names, as `catalog: <id>` or the bare id; None for any other source."""
    text = str(source or "").strip()
    if text.startswith("catalog:"):
        text = text[len("catalog:"):].strip()
    return text if text in catalog else None


def perspective_view(plan: dict, designs: dict[str, dict], perspective: dict) -> dict:
    """The part of the change a perspective's breadth spans, shaped as a unit: the files of every unit its changes
    come from, and per unit the hunks of those changes. Breadth is not bound to the review units."""
    hunks: dict[str, set[str]] = {}
    for gid in perspective["breadth"]:
        uid, cid = gid.split("/", 1)
        change = next(c for c in designs[uid]["changes"] if c["id"] == cid)
        hunks.setdefault(uid, set()).update(change["hunks"])
    files = [f for unit in plan["units"] if unit["id"] in hunks for f in unit["files"]]
    return {"id": "change", "rule": f"breadth of {perspective['id']}", "files": files, "hunks": hunks}


def list_tasks(plan: dict, designs: dict[str, dict], perspectives: dict) -> list[Task]:
    """One task per perspective of the whole change."""
    return [Task(perspective_view(plan, designs, p), p["id"]) for p in perspectives["perspectives"]]


def perspective_block(perspectives: dict, designs: dict[str, dict], perspective_id: str,
                      catalog: dict[str, CatalogPerspective]) -> str:
    """The perspective as the reviewer reads it: the catalog perspective it was picked as (value, method, sources), the
    `broken_if` bound to this change, depth, the changes it judges, checks with their means and the source each asks,
    and the repository rules attached to it with their text."""
    perspective = next(p for p in perspectives["perspectives"] if p["id"] == perspective_id)
    rows = []
    for gid in perspective["breadth"]:
        uid, cid = gid.split("/", 1)
        c = next(c for c in designs[uid]["changes"] if c["id"] == cid)
        structure = f"; structure: {c['structure']['what']}" if c["structure"]["alters"] else ""
        rows.append(f"- {gid} [{c['kind']}] {c['subject']}: {c['before']} -> {c['after']} "
                    f"(hunks {', '.join(f'{uid}/{h}' for h in c['hunks'])}{structure})")
    checks = "\n".join(f"{n}. [{check['means']}] {check['question']} (source: {check['source']})"
                       for n, check in enumerate(perspective["checks"], 1))
    picked = catalog[perspective["catalog"]]
    rules = "\n".join(f"- {row['rule']}: {row['text']}" for row in perspective.get("rules", []))
    return (
        f"# Perspective: {perspective_id}\n\nPicked from the catalog as {picked.id} {picked.title}.\n\nValue: {perspective['value']}\n\n"
        f"The value is broken if: {perspective['broken_if']}\n\n"
        f"Depth: {perspective['depth']} ({DEPTH_MEANINGS[perspective['depth']]})\n\n"
        f"Breadth (the changes this perspective judges):\n{chr(10).join(rows)}\n\nChecks:\n{checks}\n\n{MEANS_MEANINGS}.\n\n"
        f"Sources of the perspective: {picked.sources}"
        + (f"\n\nRepository rules this perspective applies (each is also a check's source):\n{rules}" if rules else "")
    )


def hunk_ids(changes: dict, unit: dict) -> list[str]:
    """`H1`, `H2`, ... for the unit's hunks, in file then hunk order."""
    return [f"H{n}" for n in range(1, sum(len(changes[f["path"]].hunks) for f in unit["files"]) + 1)]


def hunk_texts(changes: dict, unit: dict) -> dict[str, str]:
    """Each of the unit's hunk ids (`hunk_ids`) with its header and lines, as `labelled_diff` shows them."""
    hunks = [hunk for f in unit["files"] for hunk in changes[f["path"]].hunks]
    return {f"H{n}": "\n".join([hunk.header, *hunk.lines]) for n, hunk in enumerate(hunks, 1)}


def hunk_files(changes: dict, unit: dict) -> dict[str, str]:
    """The file each of the unit's hunk ids (`hunk_ids`) belongs to."""
    paths = [f["path"] for f in unit["files"] for _ in changes[f["path"]].hunks]
    return {f"H{n}": path for n, path in enumerate(paths, 1)}


def labelled_diff(changes: dict, unit: dict, keep: set[str] | None = None, prefix: str = "") -> str:
    """The unit's hunks as a unified diff, each hunk header followed by `[<prefix>H<n>]`; with `keep`, only those."""
    parts, number = [], 0
    for file in unit["files"]:
        change = changes[file["path"]]
        shown = []
        for hunk in change.hunks:
            number += 1
            if keep is None or f"H{number}" in keep:
                shown += [f"{hunk.header}  [{prefix}H{number}]", *hunk.lines]
        if shown:
            parts += [f"--- a/{change.old_path}\n+++ b/{change.path}  ({change.status})", *shown]
    return "\n".join(parts)


def breadth_diff(changes: dict, plan: dict, view: dict) -> str:
    """The hunks of a perspective's breadth, labelled `<unit>/H<n>`, unit by unit."""
    return "\n".join(labelled_diff(changes, unit, view["hunks"][unit["id"]], f"{unit['id']}/")
                     for unit in plan["units"] if unit["id"] in view["hunks"])


def strip_frontmatter(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                return "\n".join(lines[index + 1 :]).lstrip("\n")
    return text


def numbered_head_files(repo: Path, changes: dict, unit: dict) -> str:
    """Each unit file at the head, every line prefixed with its number.

    Whole files fill at most `HEAD_CHARS_PER_UNIT` characters per unit, smallest
    first; every other file is shown only around its changed lines
    (`WINDOW_LINES` on each side), so the prompt grows with the changed lines,
    not with the size of the files they sit in: on enterprise-memory#1415 two
    whole documents made one request 166k tokens.
    """
    texts = {}
    for file in unit["files"]:
        if file["status"] != "deleted":
            texts[file["path"]] = anchor_findings.head_lines(repo, file["path"])
    whole, used = set(), 0
    for path, lines in sorted(((p, l) for p, l in texts.items() if l is not None), key=lambda item: sum(len(x) + 1 for x in item[1])):
        size = sum(len(line) + 1 for line in lines)
        if used + size <= HEAD_CHARS_PER_UNIT:
            whole.add(path)
            used += size
    parts = []
    for file in unit["files"]:
        if file["status"] == "deleted":
            parts.append(f"### {file['path']} (deleted at the head; see its hunks)")
            continue
        lines = texts[file["path"]]
        if lines is None:
            parts.append(f"### {file['path']} (not readable at the head)")
            continue
        if file["path"] in whole:
            shown = [(1, len(lines))]
            title = f"### {file['path']}"
        else:
            shown = line_windows([(n, n) for n in changed_line_numbers(changes[file["path"]])], len(lines))
            title = f"### {file['path']} (only the lines around its changes; the file has {len(lines)} lines)"
        parts.append(title + "\n" + numbered_lines(lines, shown))
    return "\n\n".join(parts)


def numbered_lines(lines: list[str], spans: list[tuple[int, int]]) -> str:
    """The 1-based line spans of `lines` as `number| text`, spans joined by an elision line (prv uses it too)."""
    return "\n  ...\n".join(
        "\n".join(f"{number:>5}| {lines[number - 1]}" for number in range(first, last + 1)) for first, last in spans
    )


def line_windows(ranges: list[tuple[int, int]], length: int, radius: int = WINDOW_LINES) -> list[tuple[int, int]]:
    """Line ranges widened by `radius` on each side, clipped to 1..length, touching ones merged (prv uses it too).

    A range whose widened start is past the end yields nothing; the caller decides how to show that.
    """
    windows: list[tuple[int, int]] = []
    for start, end in sorted(set(ranges)):
        first, last = max(1, start - radius), min(length, end + radius)
        if first > last:
            continue
        if windows and first <= windows[-1][1] + 1:
            windows[-1] = (windows[-1][0], max(windows[-1][1], last))
        else:
            windows.append((first, last))
    return windows


def changed_line_numbers(change) -> list[int]:
    """Head line numbers the change touches: each added line, and the place of each removal."""
    numbers: list[int] = []
    for hunk in change.hunks:
        line_no = hunk.new_start
        for line in hunk.lines:
            if line.startswith("+"):
                numbers.append(line_no)
                line_no += 1
            elif line.startswith("-"):
                numbers.append(max(line_no, 1))
            elif line.startswith(" "):
                line_no += 1
    return numbers


def defined_name(line: str) -> str | None:
    for pattern in SYMBOL_RES:
        match = pattern.match(line)
        if match:
            return match.group(1)
    return None


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip())


def enclosing_names(lines: list[str], line_no: int) -> list[str]:
    """The definition on a head line and every definition enclosing it, innermost first.

    A definition encloses the line when it is the nearest one above it with a
    smaller indent; the walk stops at a top-level definition.
    """
    if not 1 <= line_no <= len(lines):
        return []
    names: list[str] = []
    own = defined_name(lines[line_no - 1])
    if own:
        names.append(own)
    target = lines[line_no - 1]
    limit = indent_of(target) if target.strip() else float("inf")
    for line in reversed(lines[: line_no - 1]):
        if limit == 0:
            break
        name = defined_name(line)
        if name and indent_of(line) < limit:
            names.append(name)
            limit = indent_of(line)
    return names


def changed_symbols(repo: Path, changes: dict, unit: dict) -> list[str]:
    """Names the unit's changes define or sit inside, read from the head files."""
    names: list[str] = []
    for file in unit["files"]:
        change = changes[file["path"]]
        lines = anchor_findings.head_lines(repo, change.path) if change.status != "deleted" else None
        candidates: list[str] = []
        if lines is not None:
            for line_no in changed_line_numbers(change):
                candidates += enclosing_names(lines, line_no)
        for hunk in change.hunks:
            context = HUNK_CONTEXT_RE.match(hunk.header)
            for line in ([context.group(1)] if context else []) + hunk.changed_lines:
                name = defined_name(line)
                if name:
                    candidates.append(name)
        for name in candidates:
            if name not in names and not name.startswith("test"):
                names.append(name)
    return names


def find_callers(repo: Path, unit: dict, symbols: list[str]) -> str:
    """Lines outside the unit that name each symbol, from `git grep -n -w` at the head."""
    excluded = [f":(exclude){file['path']}" for file in unit["files"]]
    parts, total = [], 0
    for symbol in symbols:
        if total >= CALLER_LINES_TOTAL:
            parts.append(f"(caller lines stop at {CALLER_LINES_TOTAL}; symbols after this point are not listed)")
            break
        result = subprocess.run(
            ["git", "-C", str(repo), "grep", "-n", "-w", "-I", "-e", symbol, "--", ".", *excluded],
            capture_output=True,
            check=False,  # exit 1 means no match; the output decides
            text=True,
        )
        hits = result.stdout.splitlines()
        if not hits:
            continue
        shown = hits[: min(CALLER_LINES_PER_SYMBOL, CALLER_LINES_TOTAL - total)]
        total += len(shown)
        more = f"\n  ({len(hits) - len(shown)} more)" if len(hits) > len(shown) else ""
        parts.append(f"#### {symbol}\n" + "\n".join(f"  {hit[:200]}" for hit in shown) + more)
    return "\n".join(parts) if parts else "(no line outside the unit names a changed symbol)"


def build_messages(task: Task, context: dict) -> list[dict]:
    """An inspector's request: the shared pack first (every request of the review starts with it, so the server reuses
    the prefix), then the perspective and the hunks of its breadth. A `low` perspective also gets the files of its
    breadth with line numbers, because it reads line by line; a `high` one judges the structure from the pack's
    occurrences and the change descriptions, and opens a file only for a location it must cite."""
    view = task.unit
    depth = next(p["depth"] for p in context["perspectives"]["perspectives"] if p["id"] == task.perspective)
    parts = [
        context["pack"],
        perspective_block(context["perspectives"], context["designs"], task.perspective, context["catalog"]),
        f"# The hunks of the breadth (`<unit>/H<n>`)\n\n```diff\n{breadth_diff(context['changes'], context['plan'], view)}\n```",
    ]
    if depth == "low":
        parts.append("# Their files at the head (line number, `|`, then the line)\n\n"
                     + numbered_head_files(context["repo"], context["changes"], view))
    parts.append("# Output JSON Schema\n\n```json\n" + json.dumps(INSPECTION_SCHEMA, indent=1) + "\n```")
    return [{"role": "system", "content": context["brief"]}, {"role": "user", "content": "\n\n".join(parts)}]


def validate_inspection(answer: object) -> list[str]:
    """Violations of an inspector's answer (INSPECTION_SCHEMA): prv's checks plus each question's target and text."""
    if not isinstance(answer, dict) or set(answer) != {"findings", "checked", "questions"}:
        return ["answer is not an object with exactly `findings`, `checked`, and `questions`"]
    problems = validate_answer({key: answer[key] for key in ("findings", "checked")})
    if not isinstance(answer["questions"], list):
        return [*problems, "`questions` is not a list"]
    for index, row in enumerate(answer["questions"]):
        if not isinstance(row, dict) or set(row) != {"about", "question"} or not str(row.get("question", "")).strip():
            problems.append(f"`questions[{index}]` is not an object with `about` (a change id `<unit>/E-<n>`) and a question")
    return problems


def validate_answer(answer: object) -> list[str]:
    """Schema violations of a parsed answer; empty when it is valid."""
    if not isinstance(answer, dict) or set(answer) != {"findings", "checked"}:
        return ["answer is not an object with exactly `findings` and `checked`"]
    problems = []
    for field_name in ("findings", "checked"):
        entries = answer[field_name]
        required = set(FINDINGS_SCHEMA["properties"][field_name]["items"]["required"])
        if not isinstance(entries, list):
            problems.append(f"`{field_name}` is not a list")
            continue
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict) or set(entry) != required:
                problems.append(f"`{field_name}[{index}]` keys are not {sorted(required)}")
            elif field_name == "findings":
                if entry["severity"] not in SEVERITIES:
                    problems.append(f"`findings[{index}].severity` is not one of {SEVERITIES}")
                if not isinstance(entry["line"], int):
                    problems.append(f"`findings[{index}].line` is not an integer")
    if answer["checked"] == []:
        problems.append("`checked` is empty: every checklist item of the perspective needs a row")
    return problems


def read_pack(directory: Path, source_sha256: str) -> str:
    """The pack built for this diff; a pack of another diff is refused."""
    meta = json.loads((directory / "pack.json").read_text(encoding="utf-8"))
    if meta["source_sha256"] != source_sha256:
        raise ValueError(f"{directory / PACK_FILE} was built for another diff; rerun context.py on this one")
    return (directory / PACK_FILE).read_text(encoding="utf-8")


class ServerRefused(Exception):
    """The server did not take the call now (HTTP 429, 502, 503, 504, or a refused or dropped connection).

    `retry_after` is the server's Retry-After in seconds, None when it gave none.
    """

    def __init__(self, message: str, retry_after: float | None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def retry_after_seconds(value: str | None) -> float | None:
    """Retry-After in its delay-seconds form (RFC 9110 section 10.2.3); the HTTP-date form is treated as absent."""
    return float(value) if value is not None and value.strip().isdigit() else None


def call_model(
    messages: list[dict], options: argparse.Namespace, schema: dict = FINDINGS_SCHEMA, schema_name: str = "srv-findings"
) -> tuple[str, dict, str]:
    """POST one chat completion held to `schema`; return the message content, the usage block, and the finish reason."""
    body = {
        "model": options.model,
        "messages": messages,
        "max_tokens": options.max_tokens,
        "response_format": {"type": "json_schema", "json_schema": {"name": schema_name, "schema": schema}},
    }
    if options.reasoning_effort:
        body["reasoning_effort"] = options.reasoning_effort
    headers = {"Content-Type": "application/json"}
    key = os.environ.get(options.api_key_env, "") if options.api_key_env else ""
    if key:
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(
        options.base_url.rstrip("/") + "/chat/completions", data=json.dumps(body).encode("utf-8"), headers=headers
    )
    try:
        with urllib.request.urlopen(request, timeout=options.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        # The server states the cause (context length, schema) in the body, not in the status line.
        body = error.read().decode("utf-8", errors="replace")[:500]
        if error.code in REFUSED_STATUSES:
            raise ServerRefused(f"HTTP {error.code}: {body}", retry_after_seconds(error.headers.get("Retry-After"))) from error
        raise ValueError(f"HTTP {error.code}: {body}") from error
    except urllib.error.URLError as error:
        if isinstance(error.reason, ConnectionError):
            raise ServerRefused(f"connection failed: {error.reason}", None) from error
        raise
    except ConnectionError as error:  # the server closed the connection before it answered
        raise ServerRefused(f"connection lost: {error}", None) from error
    try:
        choice = payload["choices"][0]
        return choice["message"].get("content") or "", payload.get("usage") or {}, choice.get("finish_reason") or ""
    except (KeyError, IndexError, TypeError, AttributeError) as error:
        raise ValueError(f"the response is not a chat completion ({type(error).__name__}: {error}): {str(payload)[:300]}") from error


@dataclass
class Reply:
    """The outcome of `request_json`: the valid answer, or None, with what it cost."""

    answer: dict | None
    attempts: int
    errors: list[str]
    usage: dict
    seconds: float


def request_json(
    messages: list[dict], options: argparse.Namespace, validate: Callable[[object], list[str]],
    schema: dict = FINDINGS_SCHEMA, schema_name: str = "srv-findings",
    on_invalid: Callable[[list[dict], str, list[str]], list[dict]] | None = None,
    call: Callable[..., tuple[str, dict, str]] = call_model,
) -> Reply:
    """Send one structured-output request; one retry when the call fails or the answer is invalid.

    A call the server refuses is sent again after a wait, capped exponential backoff with full jitter or the
    server's Retry-After, until it answers or `REFUSAL_WINDOW_S` passes; the wait uses no attempt.
    `validate` returns the problems of a parsed answer; `on_invalid` builds the retry's messages from the invalid
    content and its problems (by default the same messages are sent again). `call` sends the messages and returns
    the content, usage, and finish reason: `call_model` (one HTTP call, prv) or an omp reviewer session
    (`reviewer.Jail.call`, srv).
    """
    attempts, errors, usage_total = 0, [], {"prompt_tokens": 0, "completion_tokens": 0}
    started = time.monotonic()
    refused_since, refusals = None, 0
    while attempts < 2:
        try:
            content, usage, finish_reason = call(messages, options, schema, schema_name)
        except ServerRefused as refusal:
            now = time.monotonic()
            refused_since = now if refused_since is None else refused_since
            left = REFUSAL_WINDOW_S - (now - refused_since)
            if left <= 0:
                errors.append(
                    f"the server refused every call for {REFUSAL_WINDOW_S:.0f} s, last: {refusal}; check that it "
                    "answers (/v1/models, its logs) before rerunning the task"
                )
                break
            backoff = random.uniform(0, min(BACKOFF_CAP_S, BACKOFF_BASE_S * 2**refusals))
            delay = min(left, refusal.retry_after if refusal.retry_after is not None else backoff)
            refusals += 1
            errors.append(f"refused: {refusal}; sent again after {delay:.1f} s")
            time.sleep(delay)
            continue
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError, ValueError) as error:
            attempts += 1
            errors.append(f"attempt {attempts}: call failed: {error}")
            continue
        attempts += 1
        refused_since, refusals = None, 0
        for key in USAGE_KEYS:
            if key in usage or key in usage_total:
                usage_total[key] = usage_total.get(key, 0) + int(usage.get(key) or 0)
        if finish_reason == "length":
            errors.append(
                f"attempt {attempts}: the answer stopped at --max-tokens {options.max_tokens} (finish_reason length); "
                "reasoning tokens count toward it, so rerun the task with a larger --max-tokens"
            )
            break
        try:
            answer = json.loads(content)
        except ValueError as error:
            errors.append(f"attempt {attempts}: content is not JSON: {error}")
            continue
        problems = validate(answer)
        if problems:
            errors.append(f"attempt {attempts}: " + "; ".join(problems))
            if on_invalid is not None:
                messages = on_invalid(messages, content, problems)
            continue
        return Reply(answer, attempts, errors, usage_total, round(time.monotonic() - started, 1))
    return Reply(None, attempts, errors, usage_total, round(time.monotonic() - started, 1))


def run_task(task: Task, messages: list[dict], anchor: Callable[[list[dict]], list[dict]], options: argparse.Namespace,
             call: Callable[..., tuple[str, dict, str]] = call_model,
             validate: Callable[[object], list[str]] = validate_answer, schema: dict = FINDINGS_SCHEMA) -> dict:
    """Review one task once (one sample) with `request_json`; `anchor` re-locates the answer's finding lines."""
    reply = request_json(messages, options, validate, schema, call=call)
    result = {
        "task": task.name, "unit": task.unit["id"], "perspective": task.perspective, "ok": reply.answer is not None,
        "attempts": reply.attempts, "errors": reply.errors, "seconds": reply.seconds, "usage": reply.usage,
    }
    if reply.answer is not None:
        result["findings"] = anchor(reply.answer["findings"])
        result["checked"] = reply.answer["checked"]
        if "questions" in reply.answer:
            result["questions"] = reply.answer["questions"]
    return result


class Progress:
    """A tqdm bar for the person watching and `progress.json` for the record."""

    def __init__(self, total: int, out: Path, label: str) -> None:
        self.label = label
        self.total, self.done, self.failed = total, 0, 0
        self.path = out / "progress.json"
        self.started = time.monotonic()
        self.lock = threading.Lock()
        try:
            from tqdm import tqdm

            self.bar = tqdm(total=total, desc=label, unit="task")
        except ImportError:
            self.bar = None
        self.write()

    def advance(self, result: dict) -> None:
        with self.lock:
            self.done += 1
            self.failed += 0 if result["ok"] else 1
            if self.bar is not None:
                self.bar.set_postfix(failed=self.failed)
                self.bar.update(1)
            else:
                print(f"{self.label}: {self.done}/{self.total} ({result['task']}, failed {self.failed})", file=sys.stderr)
            self.write()

    def write(self) -> None:
        elapsed = time.monotonic() - self.started
        remaining = elapsed / self.done * (self.total - self.done) if self.done else None
        record = {"done": self.done, "total": self.total, "failed": self.failed, "elapsed_s": round(elapsed, 1)}
        record["eta_s"] = round(remaining, 1) if remaining is not None else None
        self.path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    def close(self) -> None:
        if self.bar is not None:
            self.bar.close()


def read_result(out: Path, task: Task, source_sha256: str) -> dict | None:
    """The task's output for this input; an output left by a run on another input does not count."""
    path = out / f"{task.name}.json"
    if not path.is_file():
        return None
    result = json.loads(path.read_text(encoding="utf-8"))
    return result if result.get("source_sha256") == source_sha256 else None


def merge_samples(task: Task, samples: list[dict]) -> dict:
    """One task output from its independent samples, in sample order.

    The task is valid only when every sample is; each finding and checked row
    keeps the number of the sample that wrote it, because two samples' ids collide.
    """
    merged = {
        "task": task.name, "unit": task.unit["id"], "perspective": task.perspective,
        "ok": all(sample["ok"] for sample in samples), "samples": len(samples),
        "attempts": sum(sample["attempts"] for sample in samples),
        "errors": [f"sample {n}: {error}" for n, sample in enumerate(samples, 1) for error in sample["errors"]],
        "seconds": max(sample["seconds"] for sample in samples),
        "usage": {key: sum(sample["usage"].get(key, 0) for sample in samples)
                  for key in USAGE_KEYS if any(key in sample["usage"] for sample in samples)},
    }
    if merged["ok"]:
        merged["findings"] = [{**finding, "sample": n} for n, sample in enumerate(samples, 1) for finding in sample["findings"]]
        merged["checked"] = [{**row, "sample": n} for n, sample in enumerate(samples, 1) for row in sample["checked"]]
        if any("questions" in sample for sample in samples):
            merged["questions"] = [{**row, "sample": n} for n, sample in enumerate(samples, 1) for row in sample.get("questions", [])]
    return merged


def failed_result(task: Task, error: BaseException) -> dict:
    """A sample that raised: kept as a failed output so the round still reports every task."""
    return {
        "task": task.name, "unit": task.unit["id"], "perspective": task.perspective, "ok": False, "attempts": 0,
        "errors": [f"the task raised {type(error).__name__}: {error}"], "seconds": 0.0,
        "usage": {"prompt_tokens": 0, "completion_tokens": 0},
    }


def load_design(directory: Path, plan: dict, source_sha256: str) -> tuple[dict[str, dict], dict] | str:
    """Every unit's change set and the perspective set `design.py` wrote for this diff, or what is missing."""
    def valid(path: Path) -> dict | None:
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
        return data if data and data.get("ok") and data.get("source_sha256") == source_sha256 else None

    designs = {u["id"]: valid(directory / f"{u['id']}.json") for u in plan["units"]}
    bare = [uid for uid, d in designs.items() if d is None]
    if bare:
        return f"units {bare} have no valid change set for this diff in {directory}, so no perspective judges their changes"
    perspectives = valid(directory / "perspectives.json")
    if perspectives is None:
        return f"{directory / 'perspectives.json'} holds no valid perspective set for this diff"
    return designs, perspectives


def run_sweep(options: argparse.Namespace) -> int:
    started = time.monotonic()
    plan = json.loads(Path(options.units).read_text(encoding="utf-8"))
    diff_text = Path(options.diff).read_text(encoding="utf-8")
    diff_sha256 = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    if diff_sha256 != plan["diff_sha256"]:
        print("sweep: the diff is not the one the unit plan was made from; rerun plan-units.py on this diff", file=sys.stderr)
        return 2
    loaded = load_design(Path(options.design), plan, diff_sha256)
    if isinstance(loaded, str):
        print(f"sweep: {loaded}. Run `design.py` on this unit plan and diff until it exits 0; do not run the round "
              "without them or write perspectives that skipped its coverage check.", file=sys.stderr)
        return 2
    designs, perspectives = loaded
    repo, out = Path(options.repo), Path(options.out)
    out.mkdir(parents=True, exist_ok=True)
    changes = {change.path: change for change in plan_units.parse_diff(diff_text)}
    context = {
        "brief": BRIEF_PATH.read_text(encoding="utf-8"),
        "plan": plan, "designs": designs, "perspectives": perspectives,
        "catalog": read_catalog(Path(options.catalog)),
        "pack": read_pack(Path(options.context), diff_sha256),
        "changes": changes,
        "repo": repo,
    }
    all_tasks = list_tasks(plan, designs, perspectives)
    tasks = [task for task in all_tasks if not options.only or task.name in options.only]
    missing = sorted({p["catalog"] for p in perspectives["perspectives"] if p["catalog"] not in context["catalog"]})
    if missing:
        print(f"sweep: perspectives were picked as catalog perspectives {missing} that are not in {options.catalog}; "
              "run design.py again with the same catalog", file=sys.stderr)
        return 2
    with reviewer.Jail(options, out / "sessions.jsonl") as jail:
        code = run_round(
            all_tasks, tasks,
            lambda task: build_messages(task, context),
            lambda findings: anchor_findings.anchor_findings(findings, repo),
            options, out, diff_sha256, started, "srv round 1", lambda task: task.name,
            lambda task: functools.partial(jail.call, tools=reviewer.REVIEW_TOOLS, label=task.name),
            validate_inspection, INSPECTION_SCHEMA,
        )
    return code


def run_round(
    all_tasks: list[Task], tasks: list[Task], build: Callable[[Task], list[dict]],
    anchor: Callable[[list[dict]], list[dict]], options: argparse.Namespace, out: Path, source_sha256: str, started: float,
    label: str, only_arg: Callable[[Task], str],
    call_for: Callable[[Task], Callable[..., tuple[str, dict, str]]] = lambda task: call_model,
    validate: Callable[[object], list[str]] = validate_answer, schema: dict = FINDINGS_SCHEMA,
) -> int:
    """Run `tasks` (`--samples` each, all at once), write one output per task, and report every task of `all_tasks`.

    Shared by srv round 1 and prv (`~/.agents/skills/prv/bin/sweep.py`); the caller decides the tasks, how a
    task's messages are built, how its findings are anchored, which input `source_sha256` names, the round's `label`
    for progress and messages, `only_arg`, the `--only` value that reruns a task in the caller's command, and
    and `call_for`, what sends a task's messages (by default one HTTP call per sample).
    Exit 0 when every task of `all_tasks` has a valid output for this input, 1 otherwise.
    """
    messages = {task.name: build(task) for task in tasks}
    progress = Progress(len(tasks), out, label)
    done: dict[str, dict[int, dict]] = {task.name: {} for task in tasks}
    with concurrent.futures.ThreadPoolExecutor(max_workers=options.max_concurrency) as pool:
        futures = {
            pool.submit(run_task, task, messages[task.name], anchor, options, call_for(task), validate, schema): (task, number)
            for task in tasks
            for number in range(1, options.samples + 1)
        }
        for future in concurrent.futures.as_completed(futures):
            task, number = futures[future]
            try:
                done[task.name][number] = future.result()
            except Exception as error:  # noqa: BLE001 - recorded as the sample's failure; the round must still report every task
                done[task.name][number] = failed_result(task, error)
            if len(done[task.name]) < options.samples:
                continue
            result = merge_samples(task, [done[task.name][n] for n in range(1, options.samples + 1)])
            result["source_sha256"] = source_sha256
            (out / f"{result['task']}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            progress.advance(result)
    progress.close()
    results = [read_result(out, task, source_sha256) for task in all_tasks]
    failed_tasks = [task for task, result in zip(all_tasks, results) if not (result and result["ok"])]
    failed = sorted(task.name for task in failed_tasks)
    results = [result for result in results if result]
    severities = {s: 0 for s in SEVERITIES}
    for result in results:
        for finding in result.get("findings", []):
            severities[finding["severity"]] += 1
    summary = {
        "tasks": len(all_tasks),
        "ok": len(all_tasks) - len(failed),
        "failed": failed,
        "wall_s": round(time.monotonic() - started, 1),
        "slowest_s": max((r["seconds"] for r in results), default=0),
        "this_run_tasks": len(tasks),
        "samples": options.samples,
        "prompt_tokens": sum(r["usage"]["prompt_tokens"] for r in results),
        "completion_tokens": sum(r["usage"]["completion_tokens"] for r in results),
        "tool_calls": sum(r["usage"].get("tool_calls", 0) for r in results),
        "findings_by_severity": severities,
        "model": options.model,
        "base_url": options.base_url,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary), file=sys.stderr)
    if failed:
        print(
            f"{label}: {len(failed)} tasks have no valid output ({', '.join(failed)}). What they cover is unreviewed "
            "from their perspective: read each task file's `errors`, fix the cause (endpoint, token limit, schema), "
            f"and rerun them with --only {' '.join(sorted(only_arg(task) for task in failed_tasks))}; "
            "do not drop them from the review or mark them reviewed.",
            file=sys.stderr,
        )
        return 1
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="srv round 1: --samples omp reviewer sessions per (unit, perspective), pooled.")
    parser.add_argument("--units", required=True, help="unit plan from rv/bin/plan-units.py")
    parser.add_argument("--diff", required=True, help="the diff the unit plan was made from")
    parser.add_argument("--repo", required=True, help="head worktree")
    parser.add_argument("--design", required=True, help="design directory that design.py wrote for this unit plan")
    parser.add_argument("--catalog", default=str(CATALOG), help="perspective catalog the design picked its perspectives from")
    parser.add_argument("--context", required=True, help="context directory that context.py wrote for this diff")
    parser.add_argument("--out", required=True, help="round directory for task outputs and summary.json")
    parser.add_argument("--base-url", required=True, help="OpenAI-compatible endpoint, ending in /v1")
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-key-env", help="environment variable holding the API key")
    parser.add_argument(
        "--samples", type=int, default=1,
        help="independent reviewer sessions per task, run at once, their findings pooled. Three samples was measured "
        "for calls without tools (PR #1415); with omp sessions that read and run, one sample per perspective held "
        "eight of eight first-review findings of PR #1470 in 369 s against 580 s for three samples (2026-11-24, one run "
        "each, the second also with 14 perspectives instead of 18)",
    )
    parser.add_argument(
        "--max-concurrency", type=int, default=128,
        help="sessions (srv) or requests (prv) this client keeps in flight, not the server's capacity: the server "
        "queues what it cannot take; at 128 round 1 on #1415 sent all 117 calls at once",
    )
    parser.add_argument("--max-tokens", type=int, default=65536, help="covers reasoning and answer tokens")
    parser.add_argument("--timeout", type=float, default=900, help="seconds per call or session (omp --max-time)")
    parser.add_argument("--reasoning-effort", default="high", help="empty string to omit")
    parser.add_argument("--only", nargs="+", help="task names `<unit>__<perspective>` to run, for a rerun of failed tasks")
    parser.add_argument("--sandbox-ro", action="append", default=[],
                        help="prepared dependency directory mounted read-only into counterexample runs")
    options = parser.parse_args(argv)
    if options.samples < 1:
        parser.error("--samples must be 1 or more: a task with no sample is a unit perspective nobody reviewed")
    return options


def main(argv: list[str]) -> int:
    options = parse_args(argv)
    try:
        return run_sweep(options)
    except (OSError, UnicodeDecodeError, ValueError, KeyError) as error:
        print(f"sweep: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
