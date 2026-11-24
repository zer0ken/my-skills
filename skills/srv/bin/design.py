#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["tqdm"]
# ///
"""srv design stage: derive each unit's change set and build the perspectives that cover it.

A perspective is a value-theoretic yardstick built for this change: a core value
that must hold, the breadth of changes it judges (a subset of the change set), and
the depth its verification reaches (read, trace, execute). The user's words
(2026-11-24): "axiology에는 핵심 가치에 대한 정의, 그 가치를 검증할 깊이, 넓이를
한정하지 않으면 정교한 리뷰가 불가능해. 그래서 특정 PR에 있는 diff를 보고, 그 diff에
의해 일어나는 모든 변화를 커버할 수 있는 가치론적인 평가 잣대를 여러개 만들고, 그것이
내가 말한 "관점"이야".

One omp reviewer session per review unit (`reviewer.py`), with read tools on the head, reads the unit's hunks (each labelled
with a hunk id), its head files, the lines that call into it, the requirement
copies, and the value catalog (`references/values/*.md`), opens what else it needs (the repository's rules,
callers beyond the request), and answers with
the change set, the hunks that change no behaviour, the perspectives, and what it
did with every catalog entry. Coverage is checked here, in code, not trusted to
the model (`check_design`):

- every hunk is in some change or declared behaviour-free with a reason;
- every change is in the breadth of some perspective (the union of breadths is the change set);
- every change that rests on an external program, service, or library is in an `execute` perspective;
- every catalog entry is used as a source of some perspective or dismissed with a reason.

An answer that fails a check is sent back once with the problems listed. A unit
without a valid design is a unit nobody will review, so the script exits 1.

Usage:
  uv run design.py --units units.json --diff diff.patch --repo HEAD_WORKTREE \
      --requirements FILE [FILE ...] --out design --base-url URL --model MODEL [--api-key-env NAME]
Exit codes: 0 every unit has a valid design, 1 some unit failed, 2 bad input.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

BIN = Path(__file__).resolve().parent
VALUES = BIN.parent / "references" / "values"
BRIEF_PATH = BIN.parent / "references" / "design.md"
CHANGE_KINDS = (
    "returned_value", "stored_data", "state_and_ownership", "failure_result", "resource_use",
    "interface_and_name", "documented_promise", "test_contract", "external_contract",
)
DEPTHS = ("read", "trace", "execute")
FREE_SOURCE_PREFIXES = ("requirement:", "rule:")

_STRINGS = {"type": "array", "items": {"type": "string"}}
DESIGN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["changes", "behaviour_free", "perspectives", "sources"],
    "properties": {
        "changes": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "kind", "subject", "before", "after", "hunks"],
            "properties": {
                "id": {"type": "string"}, "kind": {"type": "string", "enum": list(CHANGE_KINDS)},
                "subject": {"type": "string"}, "before": {"type": "string"}, "after": {"type": "string"},
                "hunks": _STRINGS,
            },
        }},
        "behaviour_free": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["hunk", "reason"],
            "properties": {"hunk": {"type": "string"}, "reason": {"type": "string"}},
        }},
        "perspectives": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "value", "sources", "breadth", "depth", "checks"],
            "properties": {
                "id": {"type": "string"}, "value": {"type": "string"}, "sources": _STRINGS, "breadth": _STRINGS,
                "depth": {"type": "string", "enum": list(DEPTHS)}, "checks": _STRINGS,
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


def hunk_ids(changes: dict, unit: dict) -> list[str]:
    """`H1`, `H2`, ... for the unit's hunks, in file then hunk order."""
    return [f"H{n}" for n in range(1, sum(len(changes[f["path"]].hunks) for f in unit["files"]) + 1)]


def labelled_unit_diff(changes: dict, unit: dict) -> str:
    """The unit's hunks as a unified diff, each hunk header followed by its hunk id."""
    parts, number = [], 0
    for file in unit["files"]:
        change = changes[file["path"]]
        parts.append(f"--- a/{change.old_path}\n+++ b/{change.path}  ({change.status})")
        for hunk in change.hunks:
            number += 1
            parts.append(f"{hunk.header}  [H{number}]")
            parts.extend(hunk.lines)
    return "\n".join(parts)


def check_design(answer: object, hunks: list[str], catalog: list[str]) -> list[str]:
    """Problems of a parsed design answer; empty when its schema and its coverage hold."""
    if not isinstance(answer, dict) or set(answer) != set(DESIGN_SCHEMA["required"]):
        return [f"the answer is not an object with exactly {DESIGN_SCHEMA['required']}"]
    problems: list[str] = []
    changes = {c.get("id"): c for c in answer["changes"] if isinstance(c, dict)}
    if len(changes) != len(answer["changes"]):
        problems.append("change ids are not unique")
    perspectives = [p for p in answer["perspectives"] if isinstance(p, dict)]
    if len({p.get("id") for p in perspectives}) != len(answer["perspectives"]):
        problems.append("perspective ids are not unique")
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
    covered: set[str] = set()
    used_sources: set[str] = set()
    for p in perspectives:
        pid = p.get("id")
        if not str(p.get("value", "")).strip():
            problems.append(f"{pid} has no value")
        if not p.get("checks"):
            problems.append(f"{pid} has no checks")
        if not p.get("breadth"):
            problems.append(f"{pid} has an empty breadth")
        unknown = sorted(set(p.get("breadth", [])) - set(changes))
        if unknown:
            problems.append(f"{pid} breadth names {unknown}, which are not change ids")
        covered |= set(p.get("breadth", []))
        if not p.get("sources"):
            problems.append(f"{pid} has no source")
        for source in p.get("sources", []):
            if source in catalog:
                used_sources.add(source)
            elif not str(source).startswith(FREE_SOURCE_PREFIXES):
                problems.append(f"{pid} source {source!r} is neither a catalog id {catalog} nor `requirement: ...` / `rule: ...`")
    uncovered = [c for c in changes if c not in covered]
    if uncovered:
        problems.append(f"changes {uncovered} are in no perspective's breadth; every change needs a perspective that judges it")
    executed = {e for p in perspectives if p.get("depth") == "execute" for e in p.get("breadth", [])}
    unexecuted = [cid for cid, c in changes.items() if c.get("kind") == "external_contract" and cid not in executed]
    if unexecuted:
        problems.append(
            f"external contracts {unexecuted} are in no `execute` perspective's breadth; what an external program, "
            "service, or library does is decided by running it against a fake built from its documentation, not by "
            "reading the code that assumes it"
        )
    dispositions = {row.get("source"): row for row in answer["sources"] if isinstance(row, dict)}
    for source in catalog:
        row = dispositions.get(source)
        if row is None:
            problems.append(f"catalog entry {source!r} has no row in `sources`; use it in a perspective or dismiss it with a reason")
        elif row.get("use") == "used" and source not in used_sources:
            problems.append(f"catalog entry {source!r} is marked used but no perspective names it as a source")
        elif row.get("use") == "dismissed" and (source in used_sources or not str(row.get("reason", "")).strip()):
            problems.append(f"catalog entry {source!r} is dismissed but is a perspective's source or has no reason")
    return problems


def build_messages(unit: dict, context: dict) -> list[dict]:
    catalog = "\n\n".join(f"## {name}\n\n{text}" for name, text in context["catalog"].items())
    user = "\n\n".join([
        "# Value catalog (universal value sources; each `## id` is a catalog id)\n\n" + catalog,
        "# Requirement copies (what the change answers)\n\n" + context["requirements"],
        f"# Unit {unit['id']} ({unit['rule']}): its hunks, each labelled with its hunk id\n\n```diff\n"
        + labelled_unit_diff(context["changes"], unit) + "\n```",
        "# Unit files at the head (line number, `|`, then the line)\n\n"
        + sweep.numbered_head_files(context["repo"], context["changes"], unit),
        "# Lines elsewhere at the head that name a changed symbol\n\n" + context["callers"][unit["id"]],
        "# Output JSON Schema\n\n```json\n" + json.dumps(DESIGN_SCHEMA, indent=1) + "\n```",
    ])
    return [{"role": "system", "content": context["brief"]}, {"role": "user", "content": user}]


def retry_messages(messages: list[dict], content: str, problems: list[str]) -> list[dict]:
    """The request again, with the invalid answer and the checks it failed."""
    return [*messages[:2], {"role": "assistant", "content": content}, {"role": "user", "content": (
        "The answer failed these checks:\n" + "\n".join(f"- {p}" for p in problems)
        + "\nAnswer again with the whole JSON object, fixing every problem."
    )}]


def design_unit(unit: dict, context: dict, options: argparse.Namespace, call) -> dict:
    hunks = hunk_ids(context["changes"], unit)
    catalog = list(context["catalog"])
    reply = sweep.request_json(
        build_messages(unit, context), options, lambda answer: check_design(answer, hunks, catalog),
        DESIGN_SCHEMA, "srv-design", retry_messages, call,
    )
    result = {
        "unit": unit["id"], "ok": reply.answer is not None, "hunks": hunks, "attempts": reply.attempts,
        "errors": reply.errors, "seconds": reply.seconds, "usage": reply.usage,
    }
    if reply.answer is not None:
        result.update(reply.answer)
    return result


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
        "brief": BRIEF_PATH.read_text(encoding="utf-8"),
        "catalog": read_catalog(Path(options.values)),
        "requirements": "\n\n".join(Path(path).read_text(encoding="utf-8") for path in options.requirements),
        "changes": changes,
        "repo": repo,
        "callers": {u["id"]: sweep.find_callers(repo, u, sweep.changed_symbols(repo, changes, u)) for u in plan["units"]},
    }
    units = [u for u in plan["units"] if not options.only or u["id"] in options.only]
    progress = sweep.Progress(len(units), out, "srv design")
    with sweep.reviewer.Jail(options) as jail, concurrent.futures.ThreadPoolExecutor(max_workers=options.max_concurrency) as pool:
        futures = {pool.submit(design_unit, unit, context, options, jail.call): unit for unit in units}
        for future in concurrent.futures.as_completed(futures):
            unit = futures[future]
            try:
                result = future.result()
            except Exception as error:  # noqa: BLE001 - recorded as the unit's failure; every unit must be reported
                result = {"unit": unit["id"], "ok": False, "errors": [f"raised {type(error).__name__}: {error}"],
                          "seconds": 0.0, "usage": {"prompt_tokens": 0, "completion_tokens": 0}}
            result["source_sha256"] = diff_sha256
            (out / f"{unit['id']}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            progress.advance({**result, "task": unit["id"]})
        jail.write_log(out / "sessions.json")
    progress.close()
    results = [read_design(out, u["id"], diff_sha256) for u in plan["units"]]
    failed = [u["id"] for u, r in zip(plan["units"], results) if not (r and r["ok"])]
    done = [r for r in results if r]
    summary = {
        "units": len(plan["units"]), "ok": len(plan["units"]) - len(failed), "failed": failed,
        "wall_s": round(time.monotonic() - started, 1), "slowest_s": max((r["seconds"] for r in done), default=0),
        "changes": sum(len(r.get("changes", [])) for r in done),
        "perspectives": sum(len(r.get("perspectives", [])) for r in done),
        "depths": {d: sum(1 for r in done for p in r.get("perspectives", []) if p["depth"] == d) for d in DEPTHS},
        "prompt_tokens": sum(r["usage"]["prompt_tokens"] for r in done),
        "completion_tokens": sum(r["usage"]["completion_tokens"] for r in done),
        "tool_calls": sum(r["usage"].get("tool_calls", 0) for r in done),
        "model": options.model, "base_url": options.base_url,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary), file=sys.stderr)
    if failed:
        print(
            f"design: units {failed} have no valid design, so no perspective covers their changes and the sweep would "
            "not review them. Read each unit file's `errors` (coverage problems are listed there), fix the cause "
            f"(endpoint, token limit, an unclear hunk), and rerun them with --only {' '.join(failed)}; do not sweep "
            "without them or write their perspectives by hand without the coverage check.",
            file=sys.stderr,
        )
        return 1
    return 0


def read_design(out: Path, unit_id: str, source_sha256: str) -> dict | None:
    """The unit's design for this diff; a design left by a run on another diff does not count."""
    path = out / f"{unit_id}.json"
    if not path.is_file():
        return None
    result = json.loads(path.read_text(encoding="utf-8"))
    return result if result.get("source_sha256") == source_sha256 else None


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="srv design: change set and perspectives per unit, coverage checked.")
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
    parser.add_argument("--only", nargs="+", help="unit ids to run, for a rerun of failed units")
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
