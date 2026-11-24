#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["tqdm"]
# ///
"""srv design stage: derive the change set, then build the perspectives that cover it.

A perspective is a value-theoretic yardstick built for this change: a core value
that must hold, its breadth, the set of changes it judges, and its depth, the
level of abstraction at which the value is judged: `high` (structure) or `low`
(behaviour inside a function). The user's words (2026-11-24): "axiology에는 핵심
가치에 대한 정의, 그 가치를 검증할 깊이, 넓이를 한정하지 않으면 정교한 리뷰가
불가능해. 그래서 특정 PR에 있는 diff를 보고, 그 diff에 의해 일어나는 모든 변화를
커버할 수 있는 가치론적인 평가 잣대를 여러개 만들고, 그것이 내가 말한 "관점"이야";
on depth: "하이레벨 로우레벨을 말한거다."; and, confirming with "ㄱㄱ" that breadth
is the horizontal span of changes a yardstick takes, from one function to every file
and backend the change touches, not bound to the review units the diff was cut into.
How a check is decided (read, trace, or execute) is the check's means, not the depth.

So the stage has two steps:

1. Change set, per review unit: one omp session with read tools reads the unit's
   hunks (each labelled with a hunk id), its head files, the lines that call into it,
   and the repository's rules, and answers with the unit's changes, each with the
   structure it alters or why it alters none, the hunks that change no behaviour, and
   the repository rules it read (`check_changes`). Units run at once.
2. Perspectives, for the whole change: one omp session reads the change set of every
   unit (changes named `<unit>/E-<n>`), the rules, the requirement copies, and the
   value catalog (`references/values/*.md`), and answers with the perspectives, whose
   breadth may span units, and what it did with every catalog entry
   (`check_perspectives`).

Coverage is checked here, in code, not trusted to the model:

- every hunk is in some change or declared behaviour-free with a reason;
- every change states the structure it alters (a concept, data model, placement of a
  responsibility, or module boundary) or why it alters none;
- every change is in the breadth of some `low`-depth perspective, so the union of breadths is the change set;
- every change that alters a structure is also in the breadth of some `high`-depth
  perspective, because a structural defect seen at low level shows only its symptoms;
- every change that rests on an external program, service, or library is in the breadth of a
  perspective with an `execute` check, because reading the code that assumes a contract cannot
  decide whether the contract holds;
- every catalog entry is used as a source of some perspective or dismissed with a reason.

An answer that fails a check is sent back once with the problems listed. A unit or a
perspective set without a valid answer leaves changes nobody will review, so the
script exits 1.

Usage:
  uv run design.py --units units.json --diff diff.patch --repo HEAD_WORKTREE \
      --requirements FILE [FILE ...] --out design --base-url URL --model MODEL [--api-key-env NAME]
Writes design/<unit>.json (change sets), design/perspectives.json, and summary.json.
Exit codes: 0 the change set and the perspectives are valid, 1 some step failed, 2 bad input.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import functools
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

BIN = Path(__file__).resolve().parent
VALUES = BIN.parent / "references" / "values"
CHANGES_BRIEF = BIN.parent / "references" / "changes.md"
PERSPECTIVES_BRIEF = BIN.parent / "references" / "design.md"
CHANGE_KINDS = (
    "returned_value", "stored_data", "state_and_ownership", "failure_result", "resource_use",
    "interface_and_name", "documented_promise", "test_contract", "external_contract",
)
DEPTHS = ("high", "low")
MEANS = ("read", "trace", "execute")
PERSPECTIVES_FILE = "perspectives.json"

_STRINGS = {"type": "array", "items": {"type": "string"}}
CHANGES_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["changes", "behaviour_free", "rules"],
    "properties": {
        "changes": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "kind", "subject", "before", "after", "hunks", "structure"],
            "properties": {
                "id": {"type": "string"}, "kind": {"type": "string", "enum": list(CHANGE_KINDS)},
                "subject": {"type": "string"}, "before": {"type": "string"}, "after": {"type": "string"},
                "hunks": _STRINGS,
                "structure": {
                    "type": "object", "additionalProperties": False, "required": ["alters", "what"],
                    "properties": {"alters": {"type": "boolean"}, "what": {"type": "string"}},
                },
            },
        }},
        "behaviour_free": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["hunk", "reason"],
            "properties": {"hunk": {"type": "string"}, "reason": {"type": "string"}},
        }},
        "rules": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["source", "text"],
            "properties": {"source": {"type": "string"}, "text": {"type": "string"}},
        }},
    },
}
PERSPECTIVES_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["perspectives", "sources"],
    "properties": {
        "perspectives": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "value", "sources", "breadth", "depth", "checks"],
            "properties": {
                "id": {"type": "string"}, "value": {"type": "string"}, "sources": _STRINGS, "breadth": _STRINGS,
                "depth": {"type": "string", "enum": list(DEPTHS)},
                "checks": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False, "required": ["question", "means"],
                    "properties": {"question": {"type": "string"}, "means": {"type": "string", "enum": list(MEANS)}},
                }},
            },
        }},
        "sources": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["source", "use", "reason"],
            "properties": {
                "source": {"type": "string"}, "use": {"type": "string", "enum": ["used", "dismissed"]},
                "reason": {"type": "string"},
            },
        }},
    },
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolves annotations through sys.modules
    spec.loader.exec_module(module)
    return module


sweep = load_module("srv_sweep", BIN / "sweep.py")


def read_catalog(directory: Path) -> dict[str, str]:
    """The value catalog: each method file's id (its stem) and text."""
    return {path.stem: path.read_text(encoding="utf-8").strip() for path in sorted(directory.glob("*.md"))}


def check_changes(answer: object, hunks: list[str]) -> list[str]:
    """Problems of one unit's change set; empty when its schema and its hunk coverage hold."""
    if not isinstance(answer, dict) or set(answer) != set(CHANGES_SCHEMA["required"]):
        return [f"the answer is not an object with exactly {CHANGES_SCHEMA['required']}"]
    problems: list[str] = []
    changes = {c.get("id"): c for c in answer["changes"] if isinstance(c, dict)}
    if len(changes) != len(answer["changes"]):
        problems.append("change ids are not unique")
    assigned = {h for c in changes.values() for h in c.get("hunks", [])}
    assigned |= {row.get("hunk") for row in answer["behaviour_free"] if isinstance(row, dict) and str(row.get("reason", "")).strip()}
    unknown_hunks = sorted(assigned - set(hunks) - {None})
    if unknown_hunks:
        problems.append(f"hunk ids {unknown_hunks} are not hunks of this unit")
    missing_hunks = [h for h in hunks if h not in assigned]
    if missing_hunks:
        problems.append(
            f"hunks {missing_hunks} are in no change and not declared behaviour-free with a reason; give each the "
            "change it makes, or say why it changes no behaviour"
        )
    for cid, change in changes.items():
        structure = change.get("structure")
        if not isinstance(structure, dict) or not isinstance(structure.get("alters"), bool) or not str(structure.get("what", "")).strip():
            problems.append(
                f"{cid} has no `structure` with a boolean `alters` and a `what`: state the concept, data model, "
                "responsibility, or module boundary the change alters, or why it alters none"
            )
    for row in answer["rules"]:
        if not isinstance(row, dict) or not str(row.get("source", "")).startswith("rule:") or not str(row.get("text", "")).strip():
            problems.append(f"rule {row!r} is not `rule: <path>:<line>` with the text of the line you read")
    return problems


def check_perspectives(answer: object, changes: dict[str, dict], catalog: list[str]) -> list[str]:
    """Problems of the perspective set over the whole change set (`<unit>/E-<n>` ids); empty when coverage holds."""
    if not isinstance(answer, dict) or set(answer) != set(PERSPECTIVES_SCHEMA["required"]):
        return [f"the answer is not an object with exactly {PERSPECTIVES_SCHEMA['required']}"]
    problems: list[str] = []
    perspectives = [p for p in answer["perspectives"] if isinstance(p, dict)]
    if len({p.get("id") for p in perspectives}) != len(answer["perspectives"]):
        problems.append("perspective ids are not unique")
    covered: dict[str, set[str]] = {depth: set() for depth in DEPTHS}
    executed: set[str] = set()
    used_sources: set[str] = set()
    for p in perspectives:
        pid = p.get("id")
        if not str(p.get("value", "")).strip():
            problems.append(f"{pid} has no value")
        if p.get("depth") not in DEPTHS:
            problems.append(f"{pid} depth is not one of {DEPTHS}")
        checks = [c for c in p.get("checks", []) if isinstance(c, dict)]
        if not checks or len(checks) != len(p.get("checks", [])):
            problems.append(f"{pid} has no checks, or a check that is not a question with its means")
        elif any(c.get("means") not in MEANS or not str(c.get("question", "")).strip() for c in checks):
            problems.append(f"{pid} has a check without a question or with a means that is not one of {MEANS}")
        if not p.get("breadth"):
            problems.append(f"{pid} has an empty breadth")
        unknown = sorted(set(p.get("breadth", [])) - set(changes))
        if unknown:
            problems.append(f"{pid} breadth names {unknown}, which are not change ids `<unit>/E-<n>`")
        covered.setdefault(p.get("depth"), set()).update(p.get("breadth", []))
        if any(c.get("means") == "execute" for c in checks):
            executed.update(p.get("breadth", []))
        if not p.get("sources"):
            problems.append(f"{pid} has no source")
        for source in p.get("sources", []):
            entry = sweep.catalog_id(source, catalog)
            if entry:
                used_sources.add(entry)
            elif not str(source).startswith(sweep.RECORD_SOURCE_PREFIXES):
                problems.append(f"{pid} source {source!r} is neither `catalog: <id>` of {catalog} nor `requirement: ...` / `rule: ...`")
    uncovered = [c for c in changes if c not in covered["low"]]
    if uncovered:
        problems.append(
            f"changes {uncovered} are in no `low`-depth perspective's breadth; every change needs a yardstick that judges "
            "its behaviour inside the functions it touches"
        )
    unstructured = [cid for cid, c in changes.items() if c["structure"]["alters"] and cid not in covered["high"]]
    if unstructured:
        problems.append(
            f"changes {unstructured} alter a structure but are in no `high`-depth perspective's breadth; a structural "
            "defect judged only at low level shows as its symptoms, so give them a yardstick on the structure itself"
        )
    unexecuted = [cid for cid, c in changes.items() if c["kind"] == "external_contract" and cid not in executed]
    if unexecuted:
        problems.append(
            f"external contracts {unexecuted} are in no breadth of a perspective with an `execute` check; what an "
            "external program, service, or library does is decided by running the code against a fake built from "
            "its documentation, not by reading the code that assumes it"
        )
    dispositions = {sweep.catalog_id(row.get("source"), catalog): row for row in answer["sources"] if isinstance(row, dict)}
    for source in catalog:
        row = dispositions.get(source)
        if row is None:
            problems.append(f"catalog entry {source!r} has no row in `sources`; use it in a perspective or dismiss it with a reason")
        elif row.get("use") == "used" and source not in used_sources:
            problems.append(f"catalog entry {source!r} is marked used but no perspective names it as a source")
        elif row.get("use") == "dismissed" and (source in used_sources or not str(row.get("reason", "")).strip()):
            problems.append(f"catalog entry {source!r} is dismissed but is a perspective's source or has no reason")
    return problems


def change_set(designs: dict[str, dict]) -> dict[str, dict]:
    """Every unit's changes under their global ids `<unit>/E-<n>`, in unit order."""
    return {f"{uid}/{c['id']}": {**c, "unit": uid} for uid, d in designs.items() for c in d["changes"]}


def change_set_text(changes: dict[str, dict], plan: dict) -> str:
    files = {u["id"]: ", ".join(f["path"] for f in u["files"]) for u in plan["units"]}
    rows = []
    for gid, c in changes.items():
        structure = ("alters: " if c["structure"]["alters"] else "no structure: ") + c["structure"]["what"]
        rows.append(f"- {gid} [{c['kind']}] {c['subject']}: {c['before']} -> {c['after']} "
                    f"(hunks {', '.join(c['hunks'])} of {files[c['unit']]}; {structure})")
    return "\n".join(rows)


def build_change_messages(unit: dict, context: dict) -> list[dict]:
    user = "\n\n".join([
        "# Requirement copies (what the change answers)\n\n" + context["requirements"],
        f"# Unit {unit['id']} ({unit['rule']}): its hunks, each labelled with its hunk id\n\n```diff\n"
        + sweep.labelled_diff(context["changes"], unit) + "\n```",
        "# Unit files at the head (line number, `|`, then the line)\n\n"
        + sweep.numbered_head_files(context["repo"], context["changes"], unit),
        "# Lines elsewhere at the head that name a changed symbol\n\n" + context["callers"][unit["id"]],
        sweep.change_files(context["changes"]),
        "# Output JSON Schema\n\n```json\n" + json.dumps(CHANGES_SCHEMA, indent=1) + "\n```",
    ])
    return [{"role": "system", "content": context["changes_brief"]}, {"role": "user", "content": user}]


def build_perspective_messages(designs: dict[str, dict], plan: dict, context: dict) -> list[dict]:
    catalog = "\n\n".join(f"## {name}\n\n{text}" for name, text in context["catalog"].items())
    rules = sorted({(r["source"], r["text"]) for d in designs.values() for r in d["rules"]})
    user = "\n\n".join([
        "# Value catalog (universal value sources; cite an entry as `catalog: <id>`)\n\n" + catalog,
        "# Requirement copies (what the change answers)\n\n" + context["requirements"],
        "# Repository rules the change-set sessions read\n\n"
        + ("\n".join(f"- {source}: {text}" for source, text in rules) or "(none read)"),
        "# Change set of the whole change (`<unit>/E-<n>`)\n\n" + change_set_text(change_set(designs), plan),
        "# Output JSON Schema\n\n```json\n" + json.dumps(PERSPECTIVES_SCHEMA, indent=1) + "\n```",
    ])
    return [{"role": "system", "content": context["perspectives_brief"]}, {"role": "user", "content": user}]


def retry_messages(messages: list[dict], content: str, problems: list[str]) -> list[dict]:
    """The request again, with the invalid answer and the checks it failed."""
    return [*messages[:2], {"role": "assistant", "content": content}, {"role": "user", "content": (
        "The answer failed these checks:\n" + "\n".join(f"- {p}" for p in problems)
        + "\nAnswer again with the whole JSON object, fixing every problem."
    )}]


def ask(messages: list[dict], validate, schema: dict, name: str, options: argparse.Namespace, call) -> dict:
    reply = sweep.request_json(messages, options, validate, schema, name, retry_messages, call)
    result = {"ok": reply.answer is not None, "attempts": reply.attempts, "errors": reply.errors,
              "seconds": reply.seconds, "usage": reply.usage}
    if reply.answer is not None:
        result.update(reply.answer)
    return result


def failed(error: BaseException) -> dict:
    return {"ok": False, "errors": [f"raised {type(error).__name__}: {error}"], "seconds": 0.0,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0}}


def run_design(options: argparse.Namespace) -> int:
    started = time.monotonic()
    plan = json.loads(Path(options.units).read_text(encoding="utf-8"))
    diff_text = Path(options.diff).read_text(encoding="utf-8")
    diff_sha256 = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    if diff_sha256 != plan["diff_sha256"]:
        print("design: the diff is not the one the unit plan was made from; rerun plan-units.py on this diff", file=sys.stderr)
        return 2
    repo, out = Path(options.repo), Path(options.out)
    out.mkdir(parents=True, exist_ok=True)
    changes = {change.path: change for change in sweep.plan_units.parse_diff(diff_text)}
    context = {
        "changes_brief": CHANGES_BRIEF.read_text(encoding="utf-8"),
        "perspectives_brief": PERSPECTIVES_BRIEF.read_text(encoding="utf-8"),
        "catalog": read_catalog(Path(options.values)),
        "requirements": "\n\n".join(Path(path).read_text(encoding="utf-8") for path in options.requirements),
        "changes": changes,
        "repo": repo,
        "callers": {u["id"]: sweep.find_callers(repo, u, sweep.changed_symbols(repo, changes, u)) for u in plan["units"]},
    }
    # A unit's change set written for this diff and valid is kept; --only runs named units again.
    rerun = [u for u in plan["units"] if u["id"] in (options.only or [])
             or not read_valid(out / f"{u['id']}.json", diff_sha256)]
    progress = sweep.Progress(len(rerun) + 1, out, "srv design")
    with sweep.reviewer.Jail(options, out / "sessions.jsonl") as jail, concurrent.futures.ThreadPoolExecutor(max_workers=options.max_concurrency) as pool:
        # Change-set sessions read the repository's rules and callers; they run nothing.
        unit_call = functools.partial(jail.call, tools=sweep.reviewer.DESIGN_TOOLS, label="changes")
        futures = {pool.submit(ask, build_change_messages(unit, context),
                               functools.partial(check_changes, hunks=sweep.hunk_ids(changes, unit)),
                               CHANGES_SCHEMA, "srv-changes", options, unit_call): unit for unit in rerun}
        for future in concurrent.futures.as_completed(futures):
            unit = futures[future]
            try:
                result = future.result()
            except Exception as error:  # noqa: BLE001 - recorded as the unit's failure; every unit must be reported
                result = failed(error)
            result.update({"unit": unit["id"], "hunks": sweep.hunk_ids(changes, unit), "source_sha256": diff_sha256})
            (out / f"{unit['id']}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            progress.advance({**result, "task": unit["id"]})
        designs = {u["id"]: read_valid(out / f"{u['id']}.json", diff_sha256) for u in plan["units"]}
        failed_units = [uid for uid, d in designs.items() if d is None]
        perspectives = None
        if not failed_units:
            # The perspective session works from the change set and the rules the unit sessions read; it opens
            # nothing itself, so its answer rests only on what this request shows.
            all_changes = change_set(designs)
            try:
                perspectives = ask(build_perspective_messages(designs, plan, context),
                                   functools.partial(check_perspectives, changes=all_changes, catalog=list(context["catalog"])),
                                   PERSPECTIVES_SCHEMA, "srv-perspectives", options,
                                   functools.partial(jail.call, tools=(), label="perspectives"))
            except Exception as error:  # noqa: BLE001 - recorded as the step's failure
                perspectives = failed(error)
            perspectives["source_sha256"] = diff_sha256
            (out / PERSPECTIVES_FILE).write_text(json.dumps(perspectives, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            progress.advance({**perspectives, "task": "perspectives"})
    progress.close()
    done = [d for d in designs.values() if d]
    valid_perspectives = perspectives if perspectives and perspectives["ok"] else None
    summary = {
        "units": len(plan["units"]), "ok": len(done), "failed": failed_units,
        "perspectives_ok": valid_perspectives is not None,
        "wall_s": round(time.monotonic() - started, 1),
        "changes": sum(len(d["changes"]) for d in done),
        "structural_changes": sum(1 for d in done for c in d["changes"] if c["structure"]["alters"]),
        "perspectives": len(valid_perspectives["perspectives"]) if valid_perspectives else 0,
        "depths": {v: sum(1 for p in (valid_perspectives or {}).get("perspectives", []) if p["depth"] == v) for v in DEPTHS},
        "prompt_tokens": sum(r["usage"]["prompt_tokens"] for r in [*done, *([perspectives] if perspectives else [])]),
        "completion_tokens": sum(r["usage"]["completion_tokens"] for r in [*done, *([perspectives] if perspectives else [])]),
        "model": options.model, "base_url": options.base_url,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary), file=sys.stderr)
    if failed_units:
        print(
            f"design: units {failed_units} have no valid change set, so their changes would be judged by no "
            "perspective and the sweep would not review them. Read each unit file's `errors`, fix the cause "
            f"(endpoint, token limit, an unclear hunk), and rerun with --only {' '.join(failed_units)}; do not sweep "
            "without them or write their changes by hand around the coverage check.",
            file=sys.stderr,
        )
        return 1
    if valid_perspectives is None:
        print(
            f"design: {out / PERSPECTIVES_FILE} has no valid perspective set, so some change has no yardstick. Read "
            "its `errors` (the coverage problems are listed there), fix the cause, and rerun design.py; the valid "
            "unit change sets are kept and only the perspective step runs again.",
            file=sys.stderr,
        )
        return 1
    return 0


def read_valid(path: Path, source_sha256: str) -> dict | None:
    """A design file written for this diff and valid; one left by a run on another diff, or invalid, does not count."""
    if not path.is_file():
        return None
    result = json.loads(path.read_text(encoding="utf-8"))
    return result if result.get("ok") and result.get("source_sha256") == source_sha256 else None


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="srv design: change set per unit, perspectives over the whole change, coverage checked.")
    parser.add_argument("--units", required=True, help="unit plan from rv/bin/plan-units.py")
    parser.add_argument("--diff", required=True, help="the diff the unit plan was made from")
    parser.add_argument("--repo", required=True, help="head worktree")
    parser.add_argument("--values", default=str(VALUES), help="value catalog directory")
    parser.add_argument("--requirements", required=True, nargs="+", help="requirement copies")
    parser.add_argument("--out", required=True, help="design directory, one file per unit and summary.json")
    parser.add_argument("--base-url", required=True, help="OpenAI-compatible endpoint, ending in /v1")
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-key-env", help="environment variable holding the API key")
    parser.add_argument("--max-concurrency", type=int, default=128, help="requests this client keeps in flight")
    parser.add_argument("--max-tokens", type=int, default=65536, help="covers reasoning and answer tokens")
    parser.add_argument("--timeout", type=float, default=900, help="seconds per call")
    parser.add_argument("--reasoning-effort", default="high", help="empty string to omit")
    parser.add_argument("--only", nargs="+", help="unit ids whose change set to run again; units with a valid change set "
                        "for this diff are kept, and the perspective step always runs on the whole change set")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    options = parse_args(argv)
    try:
        return run_design(options)
    except (OSError, UnicodeDecodeError, ValueError, KeyError) as error:
        print(f"design: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
