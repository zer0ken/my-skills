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

1. Change set, per review unit: one structured-output call reads the review's context
   pack (`context.py`: requirements, the documents on the change's paths, callers, and
   where each name the diff adds occurs), the unit's hunks (each labelled with a hunk
   id), and its head files, and answers with the unit's changes, each with the
   structure it alters or why it alters none, the hunks that change no behaviour, and
   the repository rules it cites from the pack (`check_changes`). Units run at once.
   No exploration is left to it: the pack already holds what a session would search
   for, so the call is one request, not an agent session (the user, 2026-11-24:
   "단발 구조화 출력은 좋지. 필요하면 그렇게 해.").
2. Perspectives, for the whole change: one structured-output call reads the change set of every
   unit (changes named `<unit>/E-<n>`), the rules, the requirement copies, and the
   value catalog (`references/values/*.md`, one item per numbered check, `<file>#<n>`), and
   answers with the perspectives, whose breadth may span units and each of whose checks names
   the one source it asks about, and the catalog items it dismissed with a reason
   (`check_perspectives`).

Coverage is checked here, in code, not trusted to the model:

- every hunk is in some change or declared behaviour-free with a reason;
- every change states the structure it alters (a concept, data model, placement of a
  responsibility, or module boundary) or why it alters none;
- every change is in the breadth of some `low`-depth perspective, so the union of breadths is the change set;
- a `low` perspective's breadth holds at most `LOW_BREADTH_MAX` changes, because breadth and depth trade
  against each other (the user, 2026-11-24: "넓게 보려면 앝게 봐야돼. 좁게 보려면 깊게 봐야돼. 넓고 깊게
  보라고 해봤자 어차피 못본다", "그러니까 관점이 필요한거라고");
- every perspective states `broken_if`, the observable state that lowers its value, so the value is decided
  from what the reviewers observe, not from each reviewer's own reading of the value;
- every change that alters a structure is also in the breadth of some `high`-depth
  perspective, because a structural defect seen at low level shows only its symptoms;
- every change that rests on an external program, service, or library is in the breadth of a
  perspective with an `execute` check, because reading the code that assumes a contract cannot
  decide whether the contract holds;
- every catalog item is asked by some perspective's check or dismissed with a reason. Coverage is per item, not per
  file: on PR #1726 the `growth` file counted as used for added routers alone, and its reuse item, which held two
  missed defects, was never asked (2026-11-25 attribution, ~/agent-assets/rebot/REPORT-srv-team.md).

Before the checks, a `high` perspective that asks a source with a stake is widened in code to the changes of that
stake no perspective asking it holds (`widen_to_stakes`): a `high` breadth has no cap, so the addition is bookkeeping
the model has shown it does not finish over a hundred changes (run 13f). An answer that fails a check is sent back
once with the problems listed. A unit or a
perspective set without a valid answer leaves changes nobody will review, so the
script exits 1.

Usage:
  uv run design.py --units units.json --diff diff.patch --repo HEAD_WORKTREE \
      --context CONTEXT_DIR --out design --base-url URL --model MODEL [--api-key-env NAME]
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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sweep import CatalogItem

BIN = Path(__file__).resolve().parent
CHANGES_BRIEF = BIN.parent / "references" / "changes.md"
PERSPECTIVES_BRIEF = BIN.parent / "references" / "design.md"
CHANGE_KINDS = (
    "returned_value", "stored_data", "state_and_ownership", "failure_result", "resource_use",
    "interface_and_name", "documented_promise", "test_contract", "external_contract",
)
DEPTHS = ("high", "low")
MEANS = ("read", "trace", "execute")
PERSPECTIVES_FILE = "perspectives.json"
# A low perspective judges behaviour inside functions, line by line, so it must stay narrow. On PR #1470 every low
# perspective had at most 8 changes and round 1 held all eight first-review findings; on PR #1726 low perspectives
# spanned up to 42 changes over 24 units, sessions ran up to 287 s, and findings were missed (2026-11-24 designs,
# ~/agent-assets/rebot/srv-measure-8, -9). The cap is that measured bound, not a tuned optimum.
LOW_BREADTH_MAX = 8

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
    "required": ["perspectives", "dismissed", "rules"],
    "properties": {
        "perspectives": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "value", "broken_if", "breadth", "depth", "checks"],
            "properties": {
                "id": {"type": "string"}, "value": {"type": "string"}, "broken_if": {"type": "string"},
                "breadth": _STRINGS,
                "depth": {"type": "string", "enum": list(DEPTHS)},
                "checks": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False, "required": ["question", "means", "source"],
                    "properties": {"question": {"type": "string"}, "means": {"type": "string", "enum": list(MEANS)},
                                   "source": {"type": "string"}},
                }},
            },
        }},
        "dismissed": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["item", "reason"],
            "properties": {"item": {"type": "string"}, "reason": {"type": "string"}},
        }},
        "rules": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["rule", "kinds", "under", "reason"],
            "properties": {
                "rule": {"type": "string"}, "kinds": {"type": "array", "items": {"type": "string", "enum": list(CHANGE_KINDS)}},
                "under": {"type": "string"}, "reason": {"type": "string"},
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


def check_perspectives(answer: object, changes: dict[str, dict], catalog: dict[str, CatalogItem],
                       rules: list[str]) -> list[str]:
    """Problems of the perspective set over the whole change set (`<unit>/E-<n>` ids, each with its `files`); empty
    when coverage holds. `rules` are the repository rules (`rule: <path>:<line>`) the change-set step cited."""
    if not isinstance(answer, dict) or set(answer) != set(PERSPECTIVES_SCHEMA["required"]):
        return [f"the answer is not an object with exactly {PERSPECTIVES_SCHEMA['required']}"]
    problems: list[str] = []
    perspectives = [p for p in answer["perspectives"] if isinstance(p, dict)]
    if len({p.get("id") for p in perspectives}) != len(answer["perspectives"]):
        problems.append("perspective ids are not unique")
    covered: dict[str, set[str]] = {depth: set() for depth in DEPTHS}
    executed: set[str] = set()
    asked: dict[str, set[str]] = {}  # source -> the changes in the breadth of a perspective with a check naming it
    for p in perspectives:
        pid = p.get("id")
        if not str(p.get("value", "")).strip():
            problems.append(f"{pid} has no value")
        if not str(p.get("broken_if", "")).strip():
            problems.append(
                f"{pid} has no `broken_if`: state the observable state at its depth that lowers the value, so a judge "
                "can decide it from the facts the reviewers report"
            )
        if p.get("depth") == "low" and len(p.get("breadth", [])) > LOW_BREADTH_MAX:
            problems.append(
                f"{pid} is `low` with {len(p.get('breadth', []))} changes in its breadth, over {LOW_BREADTH_MAX}: a "
                "perspective that reads behaviour line by line must be narrow, so split it into narrower `low` "
                "perspectives, or judge the shared concept in a `high` perspective instead"
            )
        if p.get("depth") not in DEPTHS:
            problems.append(f"{pid} depth is not one of {DEPTHS}")
        checks = [c for c in p.get("checks", []) if isinstance(c, dict)]
        if not checks or len(checks) != len(p.get("checks", [])):
            problems.append(f"{pid} has no checks, or a check that is not a question with its means and source")
        elif any(c.get("means") not in MEANS or not str(c.get("question", "")).strip() for c in checks):
            problems.append(f"{pid} has a check without a question or with a means that is not one of {MEANS}")
        for check in checks:
            source = str(check.get("source") or "").strip()
            key = sweep.catalog_id(source, catalog) or rule_id(source, rules)
            if key:
                asked.setdefault(key, set()).update(p.get("breadth", []))
            elif not source.startswith("requirement:"):
                problems.append(
                    f"{pid} check source {source!r} is neither a catalog item `catalog: <file>#<n>`, a rule of the "
                    "request's rule list `rule: <path>:<line>`, nor `requirement: ...`; a whole catalog file is not a "
                    "source, name the numbered item the check asks"
                )
        if not p.get("breadth"):
            problems.append(f"{pid} has an empty breadth")
        unknown = sorted(set(p.get("breadth", [])) - set(changes))
        if unknown:
            problems.append(f"{pid} breadth names {unknown}, which are not change ids `<unit>/E-<n>`")
        covered.setdefault(p.get("depth"), set()).update(p.get("breadth", []))
        if any(c.get("means") == "execute" for c in checks):
            executed.update(p.get("breadth", []))
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
    dismissed: set[str] = set()
    for row in answer["dismissed"]:
        item = sweep.catalog_id(row.get("item") if isinstance(row, dict) else None, catalog)
        if item is None:
            problems.append(f"dismissed row {row!r} does not name a catalog item `<file>#<n>`")
        elif item in asked:
            problems.append(f"catalog item {item!r} is dismissed but a check asks it; keep one of the two")
        elif not str(row.get("reason", "")).strip():
            problems.append(f"catalog item {item!r} is dismissed without a reason")
        else:
            dismissed.add(item)
    stakes = source_stakes(answer, changes, catalog, rules)
    for item, staked in stakes.items():
        if staked and item in dismissed:
            problems.append(f"catalog item {item!r} is dismissed but is at stake in changes {sorted(staked)} by its kinds")
    unasked = [item for item in catalog if item not in asked and item not in dismissed and not catalog[item].stakes]
    if unasked:
        problems.append(
            f"catalog items {unasked} are asked by no check and not dismissed; an item left out is a defect class the "
            "review never looks for, so give each a check in the perspective whose value it serves (a new perspective "
            "when none fits, within the breadth caps), or dismiss it with the reason no change has it at stake"
        )
    rows = {}
    for row in answer["rules"]:
        rule = rule_id(row.get("rule") if isinstance(row, dict) else None, rules)
        if rule is None:
            problems.append(f"rules row {row!r} does not name a rule of the request's rule list")
            continue
        rows[rule] = row
        kinds, under = [k for k in row.get("kinds") or [] if k in CHANGE_KINDS], str(row.get("under") or "")
        if len(kinds) != len(row.get("kinds") or []):
            problems.append(f"{rule} names kinds outside {CHANGE_KINDS}")
        if not kinds:
            if not str(row.get("reason", "")).strip():
                problems.append(f"{rule} has no kinds and no reason; give the change kinds it is at stake in, or why none")
            elif rule in asked:
                problems.append(f"{rule} is dismissed but a check asks it; give the kinds it is at stake in")
            continue
        if not stakes.get(rule):
            problems.append(f"{rule} is at stake in kinds {kinds} under {under!r}, but no change is; "
                            "fix its kinds or scope, or give no kinds and the reason")
    missing_rules = [rule for rule in rules if rule not in rows]
    if missing_rules:
        problems.append(
            f"rules {missing_rules} have no row in `rules`; a repository rule is a value source like a catalog item, "
            "so give each the change kinds and the path prefix it is at stake in, or no kinds and the reason"
        )
    for source, staked in stakes.items():
        unjudged = sorted(staked - asked.get(source, set()))
        if unjudged:
            problems.append(
                f"{source} is at stake in changes {unjudged}, which are in the breadth of no perspective with a check "
                "naming it; a source asked over some of its changes leaves the rest unreviewed, so add the check to the "
                "perspectives that already hold those changes, or to a `high` perspective over all of them"
            )
    return problems


def source_stakes(answer: dict, changes: dict[str, dict], catalog: dict[str, CatalogItem],
                  rules: list[str]) -> dict[str, set[str]]:
    """The stake of every source that has one: for a catalog item with stake kinds, every change of those kinds; for a
    rule whose `rules` row gives kinds, every change of those kinds with a file under the row's path prefix."""
    stakes = {item: {cid for cid, c in changes.items() if c["kind"] in entry.stakes}
              for item, entry in catalog.items() if entry.stakes}
    for row in answer.get("rules") or []:
        rule = rule_id(row.get("rule") if isinstance(row, dict) else None, rules)
        kinds = set(row.get("kinds") or []) & set(CHANGE_KINDS) if rule else set()
        if rule and kinds:
            under = str(row.get("under") or "")
            stakes[rule] = {cid for cid, c in changes.items()
                            if c["kind"] in kinds and any(path.startswith(under) for path in c["files"])}
    return stakes


def widen_to_stakes(answer: object, changes: dict[str, dict], catalog: dict[str, CatalogItem],
                    rules: list[str]) -> list[dict]:
    """Add to a `high` perspective that asks a source the changes of the source's stake that no perspective asking it
    holds, and return what was added. A `high` breadth has no cap, so this is bookkeeping, not a judgment: the model
    chose the value and the check, and the stake is fixed by kinds. On PR #1726 (run 13f, 2026-11-25) the perspective
    answer failed twice because a reuse check and a repository rule, each asked in a `high` perspective, left 15 and
    28 of their changes out of its breadth."""
    if not isinstance(answer, dict) or not isinstance(answer.get("perspectives"), list):
        return []
    asking: dict[str, list[dict]] = {}
    for p in answer["perspectives"]:
        if isinstance(p, dict) and isinstance(p.get("breadth"), list) and isinstance(p.get("checks"), list):
            for check in p["checks"]:
                source = check.get("source") if isinstance(check, dict) else None
                if key := sweep.catalog_id(source, catalog) or rule_id(source, rules):
                    asking.setdefault(key, []).append(p)
    widened = []
    for source, staked in source_stakes(answer, changes, catalog, rules).items():
        holders = list({id(p): p for p in asking.get(source, [])}.values())
        unjudged = sorted(staked - {cid for p in holders for cid in p["breadth"]})
        high = [p for p in holders if p.get("depth") == "high"]
        if unjudged and high:
            target = max(high, key=lambda p: len(p["breadth"]))
            target["breadth"].extend(unjudged)
            widened.append({"perspective": target.get("id"), "source": source, "changes": unjudged})
    return widened


def rule_id(source: object, rules: list[str]) -> str | None:
    """The rule of the request's list a source names, as `rule: <path>:<line>` or the bare `<path>:<line>`."""
    text = str(source or "").strip()
    rule = text if text.startswith("rule:") else f"rule: {text}"
    return rule if rule in rules else None


def read_checked_catalog(directory: Path) -> dict[str, CatalogItem]:
    """The value catalog, with every stake a change kind; a misspelled kind would leave its changes unchecked."""
    catalog = sweep.read_catalog(directory)
    wrong = {item: entry.stakes for item, entry in catalog.items() if set(entry.stakes) - set(CHANGE_KINDS)}
    if wrong:
        raise ValueError(f"catalog items {wrong} name stakes outside the change kinds {CHANGE_KINDS}; fix the tag in "
                         "the method file, since an unknown kind matches no change and silently drops the item's stake")
    return catalog


def change_set(designs: dict[str, dict], hunk_paths: dict[str, dict[str, str]]) -> dict[str, dict]:
    """Every unit's changes under their global ids `<unit>/E-<n>`, in unit order, each with the files its hunks are in
    (`hunk_paths`: per unit, hunk id to path)."""
    return {f"{uid}/{c['id']}": {**c, "unit": uid, "files": sorted({hunk_paths[uid][h] for h in c["hunks"]})}
            for uid, d in designs.items() for c in d["changes"]}


def rule_ids(designs: dict[str, dict]) -> list[str]:
    """The repository rules the change-set step cited, once each."""
    return sorted({r["source"] for d in designs.values() for r in d["rules"]})


def change_set_text(changes: dict[str, dict]) -> str:
    rows = []
    for gid, c in changes.items():
        structure = ("alters: " if c["structure"]["alters"] else "no structure: ") + c["structure"]["what"]
        rows.append(f"- {gid} [{c['kind']}] {c['subject']}: {c['before']} -> {c['after']} "
                    f"(hunks {', '.join(c['hunks'])} of {', '.join(c['files'])}; {structure})")
    return "\n".join(rows)


def build_change_messages(unit: dict, context: dict) -> list[dict]:
    user = "\n\n".join([
        context["pack"],
        f"# Unit {unit['id']} ({unit['rule']}): its hunks, each labelled with its hunk id\n\n```diff\n"
        + sweep.labelled_diff(context["changes"], unit) + "\n```",
        "# Unit files at the head (line number, `|`, then the line)\n\n"
        + sweep.numbered_head_files(context["repo"], context["changes"], unit),
        "# Output JSON Schema\n\n```json\n" + json.dumps(CHANGES_SCHEMA, indent=1) + "\n```",
    ])
    return [{"role": "system", "content": context["changes_brief"]}, {"role": "user", "content": user}]


def build_perspective_messages(designs: dict[str, dict], changes: dict[str, dict], context: dict) -> list[dict]:
    catalog = sweep.catalog_text(context["catalog"], context["catalog"])
    rules = sorted({(r["source"], r["text"]) for d in designs.values() for r in d["rules"]})
    user = "\n\n".join([
        context["pack"],
        "# Value catalog (universal value sources; a check names an item as `catalog: <file>#<n>`)\n\n" + catalog,
        "# Repository rules the change-set step cited (each needs a `rules` row)\n\n"
        + ("\n".join(f"- {source}: {text}" for source, text in rules) or "(none read)"),
        "# Change set of the whole change (`<unit>/E-<n>`)\n\n" + change_set_text(changes),
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
        "catalog": read_checked_catalog(Path(options.values)),
        "pack": sweep.read_pack(Path(options.context), diff_sha256),
        "changes": changes,
        "repo": repo,
    }
    # A unit's change set written for this diff and valid is kept; --only runs named units again.
    rerun = [u for u in plan["units"] if u["id"] in (options.only or [])
             or not read_valid(out / f"{u['id']}.json", diff_sha256)]
    progress = sweep.Progress(len(rerun) + 1, out, "srv design")
    with concurrent.futures.ThreadPoolExecutor(max_workers=options.max_concurrency) as pool:
        futures = {pool.submit(ask, build_change_messages(unit, context),
                               functools.partial(check_changes, hunks=sweep.hunk_ids(changes, unit)),
                               CHANGES_SCHEMA, "srv-changes", options, sweep.call_model): unit for unit in rerun}
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
            # The perspective call works from the pack, the change set, and the rules the unit calls cited.
            ready = {uid: d for uid, d in designs.items() if d is not None}
            all_changes = change_set(ready, {u["id"]: sweep.hunk_files(changes, u) for u in plan["units"]})
            rules = rule_ids(ready)
            widened: list[dict] = []

            def validate(answer: object) -> list[str]:
                widened[:] = widen_to_stakes(answer, all_changes, context["catalog"], rules)
                return check_perspectives(answer, all_changes, context["catalog"], rules)

            try:
                perspectives = ask(build_perspective_messages(ready, all_changes, context), validate,
                                   PERSPECTIVES_SCHEMA, "srv-perspectives", options, sweep.call_model)
                perspectives["widened"] = widened
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
    parser.add_argument("--values", default=str(sweep.VALUES), help="value catalog directory")
    parser.add_argument("--context", required=True, help="context directory that context.py wrote for this diff")
    parser.add_argument("--out", required=True, help="design directory, one file per unit and summary.json")
    parser.add_argument("--base-url", required=True, help="OpenAI-compatible endpoint, ending in /v1")
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-key-env", help="environment variable holding the API key")
    parser.add_argument("--max-concurrency", type=int, default=128, help="requests this client keeps in flight")
    # On PR #1726 the perspective answer with item stakes stopped at 65,536 tokens (replay 13a, 2026-11-25); the
    # server's context holds 393,216.
    parser.add_argument("--max-tokens", type=int, default=131072, help="covers reasoning and answer tokens")
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
