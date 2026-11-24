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
2. Perspectives, picked from srv's catalog (`references/perspectives.json`), never built (the user, 2026-11-24, after
   a lead had let code build a perspective per value source, 266 on PR #1726: "관점은 코드에서 찾는게 아니라 미리
   정해진 검토 관점 중에서 코드 변경에 관련된 걸 고르는거다."). Code picks every catalog perspective whose change
   kinds some change has (`stakes_by_kind`); a perspective with an `applies_when` condition gets one small call that
   keeps the changes of its kinds the condition holds for (`references/select.md`); one call attaches each repository
   rule the unit calls cited to the picked perspectives whose value it refines (`references/rules.md`), so a rule is a
   criterion of a picked perspective, never a perspective; and one call per picked perspective binds it to this change:
   the `broken_if` its frame takes here and the checks that decide it, one at least per attached rule
   (`references/bind.md`). Code then fixes the breadth: a `high` perspective takes its whole stake, a `low` one is cut
   into perspectives of at most `LOW_BREADTH_MAX` changes, because breadth and depth trade against each other (the
   user, 2026-11-24: "넓게 보려면 앝게 봐야돼. 좁게 보려면 깊게 봐야돼. 넓고 깊게 보라고 해봤자 어차피 못본다",
   "그러니까 관점이 필요한거라고").

Coverage is checked here, in code, not trusted to the model, and holds by construction because the catalog loader
(`sweep.read_catalog`) refuses a catalog whose unconditional perspectives miss a change kind at low depth, structure
at high depth, or external contracts under an `execute` perspective:

- every hunk is in some change or declared behaviour-free with a reason;
- every change states the structure it alters (a concept, data model, placement of a
  responsibility, or module boundary) or why it alters none;
- every change is in the breadth of some `low` perspective, and a `low` breadth holds at most `LOW_BREADTH_MAX`;
- every change that alters a structure is in the breadth of some `high` perspective, because a structural defect
  seen at low level shows only its symptoms;
- every external contract is in the breadth of a perspective with an `execute` check, because reading the code that
  assumes a contract cannot decide whether the contract holds;
- every catalog perspective is picked or left with the reason (no change of its kinds, or its condition holds for none);
- every check asks its perspective's catalog value or one rule attached to it, and every cited rule is attached or
  left with a reason, except a rule whose directory holds a changed file, which only the review may find kept (run
  13i left out the one-backend docstring rule that rv R-007 of PR #1726 rests on).

`check_perspectives` asserts this on the assembled set. Every call is sent back once with the problems its own check
finds. A unit or a perspective set without a valid answer leaves changes nobody will review, so the script exits 1.

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
    from sweep import CatalogPerspective

BIN = Path(__file__).resolve().parent
CHANGES_BRIEF = BIN.parent / "references" / "changes.md"
SELECT_BRIEF = BIN.parent / "references" / "select.md"
RULES_BRIEF = BIN.parent / "references" / "rules.md"
BIND_BRIEF = BIN.parent / "references" / "bind.md"
MEANS = ("read", "trace", "execute")
PERSPECTIVES_FILE = "perspectives.json"
# A low perspective judges behaviour inside functions, line by line, so it must stay narrow. On PR #1470 every low
# perspective had at most 8 changes and round 1 held all eight first-review findings; on PR #1726 low perspectives
# spanned up to 42 changes over 24 units, sessions ran up to 287 s, and findings were missed (2026-11-24 designs,
# ~/agent-assets/rebot/srv-measure-8, -9). The cap is that measured bound, not a tuned optimum.
LOW_BREADTH_MAX = 8

def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolves annotations through sys.modules
    spec.loader.exec_module(module)
    return module


sweep = load_module("srv_sweep", BIN / "sweep.py")
CHANGE_KINDS, STAKE_KINDS, DEPTHS = sweep.CHANGE_KINDS, sweep.STAKE_KINDS, sweep.DEPTHS
PERSPECTIVE_KEYS = ("id", "catalog", "value", "broken_if", "breadth", "depth", "checks", "rules")


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


def check_perspectives(answer: object, changes: dict[str, dict], catalog: dict[str, CatalogPerspective],
                       rules: list[str]) -> list[str]:
    """Problems of the picked perspective set over the whole change set (`<unit>/E-<n>` ids, each with its `files`);
    empty when every perspective is a catalog perspective bound to this change and coverage holds. `rules` are the
    repository rules (`rule: <path>:<line>`) the change-set step cited, once per text."""
    if not isinstance(answer, dict) or set(answer) != {"perspectives", "unpicked", "rules"}:
        return ["the answer is not an object with exactly `perspectives`, `unpicked`, `rules`"]
    problems: list[str] = []
    perspectives = [p for p in answer["perspectives"] if isinstance(p, dict) and set(p) == set(PERSPECTIVE_KEYS)]
    if len(perspectives) != len(answer["perspectives"]):
        problems.append(f"a perspective is not an object with exactly {PERSPECTIVE_KEYS}")
    if len({p["id"] for p in perspectives}) != len(perspectives):
        problems.append("perspective ids are not unique")
    covered: dict[str, set[str]] = {depth: set() for depth in DEPTHS}
    executed: set[str] = set()
    for p in perspectives:
        pid, picked = p["id"], catalog.get(p["catalog"])
        if picked is None:
            problems.append(f"{pid} names {p['catalog']!r}, which is not a catalog perspective; perspectives are picked "
                            "from the catalog, never made for the change")
            continue
        if p["value"] != picked.value or p["depth"] != picked.depth:
            problems.append(f"{pid} changes the value or depth of {picked.id}; the catalog fixes both")
        if not str(p["broken_if"]).strip():
            problems.append(f"{pid} has no `broken_if` bound to this change")
        breadth = p["breadth"]
        if not breadth or set(breadth) - set(changes):
            problems.append(f"{pid} breadth is empty or names ids that are not change ids `<unit>/E-<n>`")
        if p["depth"] == "low" and len(breadth) > LOW_BREADTH_MAX:
            problems.append(f"{pid} is `low` with {len(breadth)} changes, over {LOW_BREADTH_MAX}: a perspective that "
                            "reads behaviour line by line must stay narrow")
        attached = {row["rule"] for row in p["rules"]}
        sources = {str(c.get("source", "")) for c in p["checks"] if isinstance(c, dict)}
        if (not p["checks"] or any(not isinstance(c, dict) or c.get("means") not in MEANS
                                   or not str(c.get("question", "")).strip() for c in p["checks"])):
            problems.append(f"{pid} has no checks, or a check without a question or a means of {MEANS}")
        if sources - {picked.id} - attached:
            problems.append(f"{pid} has checks asking {sorted(sources - {picked.id} - attached)}, which are neither its "
                            f"catalog value {picked.id} nor a rule attached to it; one perspective judges one value")
        if attached - sources:
            problems.append(f"{pid} has rules {sorted(attached - sources)} attached that no check asks")
        covered[p["depth"]].update(breadth)
        if any(c.get("means") == "execute" for c in p["checks"] if isinstance(c, dict)):
            executed.update(breadth)
    if uncovered := [c for c in changes if c not in covered["low"]]:
        problems.append(f"changes {uncovered} are in no `low` perspective's breadth; every change needs a yardstick that "
                        "judges its behaviour inside the functions it touches")
    if unstructured := [cid for cid, c in changes.items() if c["structure"]["alters"] and cid not in covered["high"]]:
        problems.append(f"changes {unstructured} alter a structure but are in no `high` perspective's breadth; a "
                        "structural defect judged only at low level shows as its symptoms")
    if unexecuted := [cid for cid, c in changes.items() if c["kind"] == "external_contract" and cid not in executed]:
        problems.append(f"external contracts {unexecuted} are in no breadth of a perspective with an `execute` check; what "
                        "an external program does is decided by running against a fake built from its documentation")
    picked_ids = {p["catalog"] for p in perspectives}
    left = {row.get("catalog") for row in answer["unpicked"] if isinstance(row, dict) and str(row.get("reason", "")).strip()}
    if missing := [pid for pid in catalog if pid not in picked_ids and pid not in left]:
        problems.append(f"catalog perspectives {missing} are neither picked nor left with a reason")
    rows = {rule_id(row.get("rule"), rules): row for row in answer["rules"] if isinstance(row, dict)}
    if missing := [rule for rule in rules if rule not in rows]:
        problems.append(f"rules {missing} have no row; attach each to the picked perspectives it refines, or give the reason")
    for rule, row in rows.items():
        if rule is None:
            problems.append("a rules row names no rule the change-set step cited")
            continue
        if not row.get("perspectives") and governs_changed_file(rule, changes):
            problems.append(f"{rule} is attached to no perspective, but its document governs files the change touches "
                            f"under {rule_scope(rule)!r}; whether those changes keep it is what the review decides")
    return problems


def governs_changed_file(rule: str, changes: dict[str, dict]) -> bool:
    """A rule in a subdirectory's rule document governs a changed file under that directory. A rule of the root
    document governs every file, and the review may leave it as context: run 13l kept all 61 root rules, each a
    perspective of its own."""
    scope = rule_scope(rule)
    return bool(scope) and any(path.startswith(scope) for c in changes.values() for path in c["files"])


def rule_id(source: object, rules: list[str]) -> str | None:
    """The rule of the request's list a source names, as `rule: <path>:<line>` or the bare `<path>:<line>`."""
    text = str(source or "").strip()
    rule = text if text.startswith("rule:") else f"rule: {text}"
    return rule if rule in rules else None


def change_set(designs: dict[str, dict], hunk_paths: dict[str, dict[str, str]]) -> dict[str, dict]:
    """Every unit's changes under their global ids `<unit>/E-<n>`, in unit order, each with the files its hunks are in
    (`hunk_paths`: per unit, hunk id to path)."""
    return {f"{uid}/{c['id']}": {**c, "unit": uid, "files": sorted({hunk_paths[uid][h] for h in c["hunks"]})}
            for uid, d in designs.items() for c in d["changes"]}


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


_CHECKS = {"type": "array", "items": {
    "type": "object", "additionalProperties": False, "required": ["question", "means", "source"],
    "properties": {"question": {"type": "string"}, "means": {"type": "string", "enum": list(MEANS)},
                   "source": {"type": "string"}},
}}
SELECT_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["changes", "reason"],
    "properties": {"changes": _STRINGS, "reason": {"type": "string"}},
}
RULES_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["rules"],
    "properties": {"rules": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["rule", "perspectives", "reason"],
        "properties": {"rule": {"type": "string"}, "perspectives": _STRINGS, "reason": {"type": "string"}},
    }}},
}
BIND_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["broken_if", "checks"],
    "properties": {"broken_if": {"type": "string"}, "checks": _CHECKS},
}


def distinct_rules(designs: dict[str, dict]) -> tuple[dict[str, str], dict[str, str]]:
    """The cited rules once per text, as (rule id -> text, alias id -> the id kept for its text). Unit calls cite one
    rule text under several ids (a root rule file and its copy in a package), and each id would otherwise become a
    perspective of its own for the same value."""
    texts: dict[str, str] = {}
    for d in designs.values():
        for row in d["rules"]:
            texts.setdefault(row["source"], row["text"].strip())
    kept: dict[str, str] = {}
    aliases: dict[str, str] = {}
    for rule in sorted(texts):
        first = next((k for k, text in kept.items() if text == texts[rule]), None)
        if first:
            aliases[rule] = first
        else:
            kept[rule] = texts[rule]
    return kept, aliases


def rule_scope(rule: str) -> str:
    """The path prefix a rule's document governs: the directory the document sits in (`""` for the repository root)."""
    path = rule.removeprefix("rule:").strip().rsplit(":", 1)[0]
    directory = path.rsplit("/", 1)[0] if "/" in path else ""
    return f"{directory}/" if directory else ""


def stakes_by_kind(catalog: dict[str, CatalogPerspective], changes: dict[str, dict]) -> dict[str, list[str]]:
    """Every catalog perspective's stake: the changes, in change-set order, whose kind is one of its kinds, or that alter
    a structure when `structure` is one of them. The changes are indexed by kind once, so each perspective reads only
    the lists of its own kinds."""
    by_kind: dict[str, list[str]] = {kind: [] for kind in STAKE_KINDS}
    for cid, c in changes.items():
        by_kind[c["kind"]].append(cid)
        if c["structure"]["alters"]:
            by_kind["structure"].append(cid)
    order = {cid: n for n, cid in enumerate(changes)}
    return {pid: sorted({cid for kind in p.kinds for cid in by_kind[kind]}, key=order.__getitem__)
            for pid, p in catalog.items()}


def check_select(answer: object, stake: list[str]) -> list[str]:
    """Problems of one condition answer: it keeps a subset of the perspective's stake, with a reason."""
    if not isinstance(answer, dict) or set(answer) != set(SELECT_SCHEMA["required"]):
        return [f"the answer is not an object with exactly {SELECT_SCHEMA['required']}"]
    problems = []
    if unknown := sorted(set(answer["changes"]) - set(stake)):
        problems.append(f"changes {unknown} are not among the listed changes; keep only listed ids, copied exactly")
    if not str(answer["reason"]).strip():
        problems.append("`reason` is empty")
    return problems


def check_rules(answer: object, rules: list[str], picked: list[str], changes: dict[str, dict]) -> list[str]:
    """Problems of the rule answer: one row per rule, naming only picked perspectives, a reason for a rule left
    unattached, and no rule left unattached whose directory holds a changed file (`governs_changed_file`)."""
    if not isinstance(answer, dict) or not isinstance(answer.get("rules"), list):
        return ["the answer is not an object with a `rules` list"]
    problems, rows = [], {}
    for row in answer["rules"]:
        rule = rule_id(row.get("rule") if isinstance(row, dict) else None, rules)
        if rule is None:
            problems.append(f"rules row {row!r} names no rule of the request")
            continue
        rows[rule] = row
        if unknown := sorted(set(row["perspectives"]) - set(picked)):
            problems.append(f"{rule} names {unknown}, which are not picked perspective ids")
        if not row["perspectives"]:
            if governs_changed_file(rule, changes):
                problems.append(f"{rule} is attached to nothing, but its document governs files the change touches "
                                f"under {rule_scope(rule)!r}; attach it to the perspective whose value it refines")
            elif not str(row["reason"]).strip():
                problems.append(f"{rule} is attached to nothing and has no reason")
    if missing := [rule for rule in rules if rule not in rows]:
        problems.append(f"rules {missing} have no row")
    return problems


def check_bind(answer: object, perspective: CatalogPerspective, attached: list[str]) -> list[str]:
    """Problems of one binding: a `broken_if` for this change, checks that each ask the perspective's value or one
    attached rule, at least one check per attached rule and one for the value, and an `execute` check when the
    catalog perspective requires a run."""
    if not isinstance(answer, dict) or set(answer) != set(BIND_SCHEMA["required"]):
        return [f"the answer is not an object with exactly {BIND_SCHEMA['required']}"]
    problems = [] if str(answer["broken_if"]).strip() else ["`broken_if` is empty"]
    checks = answer["checks"] if isinstance(answer["checks"], list) else []
    if not checks or any(not isinstance(c, dict) or c.get("means") not in MEANS or not str(c.get("question", "")).strip()
                         for c in checks):
        problems.append(f"checks must be questions, each with a means of {MEANS} and a source")
        return problems
    sources = [bind_source(c["source"], perspective, attached) for c in checks]
    if None in sources:
        problems.append(f"a check's source is neither `{perspective.id}` nor one of the attached rules {attached}")
    if perspective.id not in sources:
        problems.append(f"no check asks the perspective's own value; give one with source `{perspective.id}`")
    if missing := [rule for rule in attached if rule not in sources]:
        problems.append(f"attached rules {missing} are asked by no check; give each its own check, so its observations "
                        "stay apart from the value's")
    if perspective.execute and not any(c["means"] == "execute" for c in checks):
        problems.append("this perspective is decided by a run; give an `execute` check naming the input to run and the "
                        "result that would show the value lowered")
    return problems


def bind_source(source: object, perspective: CatalogPerspective, attached: list[str]) -> str | None:
    """A check's source as the perspective's catalog id or an attached rule id; None for anything else."""
    text = str(source or "").strip().removeprefix("catalog:").strip()
    return text if text == perspective.id else rule_id(text, attached)


def chunks(ids: list[str], size: int) -> list[list[str]]:
    return [ids[n:n + size] for n in range(0, len(ids), size)]


def user_message(context: dict, *parts: str, schema: dict) -> str:
    return "\n\n".join([context["pack"], *parts, "# Output JSON Schema\n\n```json\n" + json.dumps(schema, indent=1) + "\n```"])


def build_perspectives(designs: dict[str, dict], changes: dict[str, dict], context: dict, options: argparse.Namespace,
                       pool: concurrent.futures.Executor) -> dict:
    """The perspective set, picked from the catalog and bound to this change: code picks by change kind, one call per
    conditional perspective keeps the changes its condition holds for, one call attaches the cited rules to the picked
    perspectives, one call per picked perspective binds its `broken_if` and checks, and code fixes the breadth (a `high`
    perspective over its whole stake, `low` ones over at most `LOW_BREADTH_MAX` changes each)."""
    catalog = context["catalog"]
    rule_text, aliases = distinct_rules(designs)
    rules = list(rule_text)
    started, calls = time.monotonic(), []

    def call(messages, validate, schema, name):
        result = ask(messages, validate, schema, name, options, sweep.call_model)
        calls.append(result)
        return result

    def listing(ids) -> str:
        return "\n".join(f"- {cid} [{changes[cid]['kind']}{', alters structure' if changes[cid]['structure']['alters'] else ''}] "
                         f"{changes[cid]['subject']}: {changes[cid]['before']} -> {changes[cid]['after']} "
                         f"({', '.join(changes[cid]['files'])})" for cid in ids)

    def message(brief: str, *parts: str, schema: dict) -> list[dict]:
        return [{"role": "system", "content": context[brief]}, {"role": "user", "content": user_message(context, *parts, schema=schema)}]

    stakes = stakes_by_kind(catalog, changes)
    unpicked = {pid: f"no change of kinds {', '.join(catalog[pid].kinds)}" for pid, ids in stakes.items() if not ids}
    conditional = [pid for pid in catalog if pid not in unpicked and catalog[pid].applies_when]
    futures = {pid: pool.submit(call, message("select_brief", "# Perspective\n\n" + sweep.catalog_text(catalog, [pid]),
                                              "# Changes of its kinds\n\n" + listing(stakes[pid]), schema=SELECT_SCHEMA),
                                functools.partial(check_select, stake=stakes[pid]), SELECT_SCHEMA, "srv-select")
               for pid in conditional}
    errors = []
    for pid, future in futures.items():
        answer = future.result()
        if not answer["ok"]:
            errors += [f"select {pid}: {e}" for e in answer["errors"]]
        elif answer["changes"]:
            stakes[pid] = [cid for cid in stakes[pid] if cid in set(answer["changes"])]
        else:
            unpicked[pid] = f"applies when {catalog[pid].applies_when}: {answer['reason']}"
    if errors:
        return {"ok": False, "errors": errors, "calls": calls}
    picked = [pid for pid in catalog if pid not in unpicked]
    attached: dict[str, list[str]] = {pid: [] for pid in picked}
    rule_rows = []
    if rules:
        answer = call(message("rules_brief", "# Picked perspectives\n\n" + sweep.catalog_text(catalog, picked),
                              "# Repository rules\n\n" + "\n".join(f"- {rule}: {text}" for rule, text in rule_text.items()),
                              schema=RULES_SCHEMA),
                      functools.partial(check_rules, rules=rules, picked=picked, changes=changes), RULES_SCHEMA, "srv-rules")
        if not answer["ok"]:
            return {"ok": False, "errors": ["rules: " + e for e in answer["errors"]], "calls": calls}
        for rule, row in {rule: row for row in answer["rules"] if (rule := rule_id(row["rule"], rules))}.items():
            rule_rows.append({"rule": rule, "perspectives": row["perspectives"], "reason": row["reason"]})
            for pid in row["perspectives"]:
                attached[pid].append(rule)

    def bind_messages(pid: str) -> list[dict]:
        rule_part = "\n".join(f"- {rule}: {rule_text[rule]}" for rule in attached[pid]) or "(none)"
        return message("bind_brief", "# Perspective\n\n" + sweep.catalog_text(catalog, [pid]),
                       "# Repository rules attached to it\n\n" + rule_part,
                       "# Changes in its breadth\n\n" + listing(stakes[pid]), schema=BIND_SCHEMA)

    futures = {pid: pool.submit(call, bind_messages(pid),
                                functools.partial(check_bind, perspective=catalog[pid], attached=attached[pid]),
                                BIND_SCHEMA, "srv-bind")
               for pid in picked}
    perspectives = []
    for pid, future in futures.items():
        answer = future.result()
        if not answer["ok"]:
            errors += [f"bind {pid}: {e}" for e in answer["errors"]]
            continue
        p = catalog[pid]
        checks = [{"question": c["question"], "means": c["means"], "source": bind_source(c["source"], p, attached[pid])}
                  for c in answer["checks"]]
        groups = [stakes[pid]] if p.depth == "high" else chunks(stakes[pid], LOW_BREADTH_MAX)
        perspectives += [{"catalog": pid, "value": p.value, "broken_if": answer["broken_if"], "breadth": group,
                          "depth": p.depth, "checks": checks,
                          "rules": [{"rule": rule, "text": rule_text[rule]} for rule in attached[pid]]} for group in groups]
    if errors:
        return {"ok": False, "errors": errors, "calls": calls}
    answer = {
        "perspectives": [{"id": f"K-{n}", **p} for n, p in enumerate(perspectives, 1)],
        "unpicked": [{"catalog": pid, "reason": reason} for pid, reason in unpicked.items()],
        "rules": rule_rows,
    }
    answer["perspectives"] = [{key: p[key] for key in PERSPECTIVE_KEYS} for p in answer["perspectives"]]
    problems = check_perspectives(answer, changes, catalog, rules)
    return {"ok": not problems, "errors": problems, "calls": calls, **answer, "aliases": aliases,
            "seconds": round(time.monotonic() - started, 1)}


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
        "select_brief": SELECT_BRIEF.read_text(encoding="utf-8"),
        "rules_brief": RULES_BRIEF.read_text(encoding="utf-8"),
        "bind_brief": BIND_BRIEF.read_text(encoding="utf-8"),
        "catalog": sweep.read_catalog(Path(options.catalog)),
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
            ready = {uid: d for uid, d in designs.items() if d is not None}
            all_changes = change_set(ready, {u["id"]: sweep.hunk_files(changes, u) for u in plan["units"]})
            try:
                perspectives = build_perspectives(ready, all_changes, context, options, pool)
            except Exception as error:  # noqa: BLE001 - recorded as the step's failure
                perspectives = failed(error)
            calls = perspectives.pop("calls", [])
            perspectives["usage"] = {key: sum(c["usage"].get(key, 0) for c in calls) for key in ("prompt_tokens", "completion_tokens")}
            perspectives["call_counts"] = {"calls": len(calls), "attempts": sum(c.get("attempts", 0) for c in calls)}
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
    parser.add_argument("--catalog", default=str(sweep.CATALOG), help="perspective catalog the perspectives are picked from")
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
