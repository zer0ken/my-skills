#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["tqdm"]
# ///
"""srv rounds 2 and later: one omp reviewer session per follow-up question, answered in round 1's schema.

The operator writes the round's questions to `questions.json` after verifying the
previous round (`references/deepen.md`): each names the unit and the perspective it
serves and asks one narrow thing. Each question gets one session (`reviewer.py`), with
read tools on the head and `sandbox_run`, as every review session has; the
request is the follow-up brief, the perspective as round 1 showed it, the question,
the requirement copies, and the unit's hunks. The answer is round 1's findings schema,
so its lines are re-located from their anchors and the operator verifies it the same
way (`references/consolidate.md`).

questions.json: [{"id": "Q1", "unit": "U-1", "perspective": "K-3", "question": "..."}]

Usage:
  uv run followup.py --questions questions.json --units units.json --diff diff.patch --repo HEAD_WORKTREE \
      --design design --requirements FILE [FILE ...] --out round-2 --base-url URL --model MODEL [--api-key-env NAME]
Exit codes: 0 every question has a valid answer, 1 some failed, 2 bad input.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

BIN = Path(__file__).resolve().parent
BRIEF_PATH = BIN.parent / "references" / "deepen.md"
BRIEF_HEADING = "## Follow-up brief"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sweep = load_module("srv_sweep", BIN / "sweep.py")


def follow_up_brief() -> str:
    """The `## Follow-up brief` section of `references/deepen.md`, the part written for the reviewer."""
    text = BRIEF_PATH.read_text(encoding="utf-8")
    return text[text.index(BRIEF_HEADING):].strip()


def build_messages(question: dict, context: dict) -> list[dict]:
    unit = context["units"][question["unit"]]
    user = "\n\n".join([
        sweep.perspective_block(context["designs"][unit["id"]], question["perspective"], context["catalog"]),
        f"# Question {question['id']}\n\n{question['question']}",
        "# Requirement copies (what the change answers)\n\n" + context["requirements"],
        f"# Unit {unit['id']} ({unit['rule']}): its hunks\n\n```diff\n{sweep.unit_diff(context['changes'], unit)}\n```",
        "# Output JSON Schema\n\n```json\n" + json.dumps(sweep.FINDINGS_SCHEMA, indent=1) + "\n```",
    ])
    return [{"role": "system", "content": context["brief"]}, {"role": "user", "content": user}]


def read_questions(path: Path, units: dict, designs: dict) -> list[dict]:
    questions = json.loads(path.read_text(encoding="utf-8"))
    problems = []
    for q in questions:
        design = designs.get(q.get("unit"))
        if design is None:
            problems.append(f"{q.get('id')}: unit {q.get('unit')!r} has no valid design")
        elif q.get("perspective") not in {p["id"] for p in design["perspectives"]}:
            problems.append(f"{q.get('id')}: perspective {q.get('perspective')!r} is not one design.py built for {q['unit']}")
        if not str(q.get("question", "")).strip():
            problems.append(f"{q.get('id')}: empty question")
    if len({q.get("id") for q in questions}) != len(questions):
        problems.append("question ids are not unique")
    if problems:
        raise ValueError("questions.json: " + "; ".join(problems) + ". A question serves one designed perspective; "
                         "write it against the design files, not a perspective of your own")
    return questions


def run_followup(options: argparse.Namespace) -> int:
    started = time.monotonic()
    plan = json.loads(Path(options.units).read_text(encoding="utf-8"))
    diff_text = Path(options.diff).read_text(encoding="utf-8")
    diff_sha256 = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    if diff_sha256 != plan["diff_sha256"]:
        print("followup: the diff is not the one the unit plan was made from", file=sys.stderr)
        return 2
    units = {u["id"]: u for u in plan["units"]}
    designs = {}
    for unit_id in units:
        path = Path(options.design) / f"{unit_id}.json"
        design = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
        if design and design.get("ok") and design.get("source_sha256") == diff_sha256:
            designs[unit_id] = design
    questions = read_questions(Path(options.questions), units, designs)
    repo, out = Path(options.repo), Path(options.out)
    out.mkdir(parents=True, exist_ok=True)
    context = {
        "brief": follow_up_brief(), "units": units, "designs": designs,
        "catalog": {p.stem: p.read_text(encoding="utf-8").strip() for p in sorted(sweep.VALUES.glob("*.md"))},
        "requirements": "\n\n".join(Path(p).read_text(encoding="utf-8") for p in options.requirements),
        "changes": {c.path: c for c in sweep.plan_units.parse_diff(diff_text)},
    }
    by_task = {}
    tasks = []
    for q in questions:
        task = sweep.Task(units[q["unit"]], q["id"])
        by_task[task.name] = q
        tasks.append(task)
    only = [t for t in tasks if not options.only or t.perspective in options.only]
    with sweep.reviewer.Jail(options, out / "sessions.jsonl") as jail:
        code = sweep.run_round(
            tasks, only,
            lambda task: build_messages(by_task[task.name], context),
            lambda findings: sweep.anchor_findings.anchor_findings(findings, repo),
            options, out, diff_sha256, started, "srv follow-up", lambda task: task.perspective,
            lambda task: functools.partial(jail.call, tools=sweep.reviewer.REVIEW_TOOLS, label=task.name),
        )
    return code


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="srv follow-up round: one omp reviewer session per question.")
    parser.add_argument("--questions", required=True, help="questions.json written by the operator")
    parser.add_argument("--units", required=True)
    parser.add_argument("--diff", required=True)
    parser.add_argument("--repo", required=True, help="head worktree")
    parser.add_argument("--design", required=True)
    parser.add_argument("--requirements", required=True, nargs="+")
    parser.add_argument("--out", required=True, help="round directory, `round-<k>`")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-key-env")
    parser.add_argument("--samples", type=int, default=1, help="sessions per question; one, as deepen.md measured")
    parser.add_argument("--max-concurrency", type=int, default=64)
    parser.add_argument("--max-tokens", type=int, default=65536)
    parser.add_argument("--timeout", type=float, default=900, help="seconds per session")
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument("--sandbox-ro", action="append", default=[])
    parser.add_argument("--only", nargs="+", help="question ids to run again")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    options = parse_args(argv)
    try:
        return run_followup(options)
    except (OSError, ValueError, KeyError) as error:
        print(f"followup: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
