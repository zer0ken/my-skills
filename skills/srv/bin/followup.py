#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["tqdm"]
# ///
"""srv rounds 2 and later: one omp reviewer session per follow-up question, answered in round 1's schema.

`team.py` writes the round's questions to `questions.json` after judging the
previous round (`references/deepen.md`): each names the perspective it
serves and asks one narrow thing. Each question gets one session (`reviewer.py`), with
read tools on the head and `sandbox_run`, as every review session has; the
request is the shared context pack, the follow-up brief, the perspective as round 1 showed it, the
question, and the hunks of the perspective's breadth. The answer is round 1's inspection schema,
so its lines are re-located from their anchors and team.py judges and verifies it the same way.

questions.json: [{"id": "Q1", "perspective": "K-3", "question": "..."}]

Usage:
  uv run followup.py --questions questions.json --units units.json --diff diff.patch --repo HEAD_WORKTREE \
      --design design --context context --out round-2 --base-url URL --model MODEL [--api-key-env NAME]
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
    perspective = next(p for p in context["perspectives"]["perspectives"] if p["id"] == question["perspective"])
    view = sweep.perspective_view(context["plan"], context["designs"], perspective)
    user = "\n\n".join([
        context["pack"],
        sweep.perspective_block(context["perspectives"], context["designs"], question["perspective"], context["catalog"]),
        f"# Question {question['id']}\n\n{question['question']}",
        f"# The hunks of the breadth (`<unit>/H<n>`)\n\n```diff\n{sweep.breadth_diff(context['changes'], context['plan'], view)}\n```",
        "# Output JSON Schema\n\n```json\n" + json.dumps(sweep.INSPECTION_SCHEMA, indent=1) + "\n```",
    ])
    return [{"role": "system", "content": context["brief"]}, {"role": "user", "content": user}]


def read_questions(path: Path, perspectives: dict) -> list[dict]:
    questions = json.loads(path.read_text(encoding="utf-8"))
    built = {p["id"] for p in perspectives["perspectives"]}
    problems = []
    for q in questions:
        if q.get("perspective") not in built:
            problems.append(f"{q.get('id')}: perspective {q.get('perspective')!r} is not one design.py built")
        if not str(q.get("question", "")).strip():
            problems.append(f"{q.get('id')}: empty question")
    if len({q.get("id") for q in questions}) != len(questions):
        problems.append("question ids are not unique")
    if problems:
        raise ValueError("questions.json: " + "; ".join(problems) + ". A question serves one designed perspective; "
                         "write it against design/perspectives.json, not a perspective of your own")
    return questions


def run_followup(options: argparse.Namespace) -> int:
    started = time.monotonic()
    plan = json.loads(Path(options.units).read_text(encoding="utf-8"))
    diff_text = Path(options.diff).read_text(encoding="utf-8")
    diff_sha256 = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    if diff_sha256 != plan["diff_sha256"]:
        print("followup: the diff is not the one the unit plan was made from", file=sys.stderr)
        return 2
    loaded = sweep.load_design(Path(options.design), plan, diff_sha256)
    if isinstance(loaded, str):
        print(f"followup: {loaded}; run design.py until it exits 0", file=sys.stderr)
        return 2
    designs, perspectives = loaded
    questions = read_questions(Path(options.questions), perspectives)
    repo, out = Path(options.repo), Path(options.out)
    out.mkdir(parents=True, exist_ok=True)
    context = {
        "brief": follow_up_brief(), "plan": plan, "designs": designs, "perspectives": perspectives,
        "catalog": sweep.read_catalog(),
        "pack": sweep.read_pack(Path(options.context), diff_sha256),
        "changes": {c.path: c for c in sweep.plan_units.parse_diff(diff_text)},
    }
    by_task = {}
    tasks = []
    for q in questions:
        perspective = next(p for p in perspectives["perspectives"] if p["id"] == q["perspective"])
        task = sweep.Task(sweep.perspective_view(plan, designs, perspective), q["id"])
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
            sweep.validate_inspection, sweep.INSPECTION_SCHEMA,
        )
    return code


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="srv follow-up round: one omp reviewer session per question.")
    parser.add_argument("--questions", required=True, help="questions.json written by the operator")
    parser.add_argument("--units", required=True)
    parser.add_argument("--diff", required=True)
    parser.add_argument("--repo", required=True, help="head worktree")
    parser.add_argument("--design", required=True)
    parser.add_argument("--context", required=True, help="context directory that context.py wrote for this diff")
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
