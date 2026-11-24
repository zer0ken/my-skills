#!/usr/bin/env python3
"""Decide the review's verdict from the verified clusters, the questions to people, and the perspectives' checks.

The review returns one judgment J = (decision, confirmed counterexamples, questions
to people, residual risk), not a list of findings. The decision is a rule over what
the operator verified, not a model's or the operator's free choice, and what was not
established never becomes acceptance:

1. 차단: a CONFIRMED BLOCKER or MAJOR cluster (rv: "BLOCKER and MAJOR block approval").
2. 증거 부족: a PLAUSIBLE BLOCKER or MAJOR cluster, or a perspective with a check not
   decided by its means (rv: "If a core verification gap prevents judgment, the verdict is withheld").
3. 조건부 수용: a question only a person can answer, or any remaining MINOR or NIT cluster.
4. 수용: none of the above.

Every perspective `design.py` built must appear in the verdict file with `decided`
true (every check decided by its means) or false, so a perspective nobody accounted for cannot pass silently.

Usage: python3 -I verdict.py --design DESIGN_DIR --verdict verdict.json [--out judgment.json]
verdict.json: {"clusters": [{"id", "severity", "verdict": "CONFIRMED"|"PLAUSIBLE", "evidence"}],
               "questions": [{"id", "question", "options"}],
               "perspectives": [{"id": "<unit>/<perspective>", "decided": bool, "note"}],
               "risks": [str]}
Exit codes: 0 judged, 2 the verdict file does not account for every perspective or is malformed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BLOCKING = ("BLOCKER", "MAJOR")
VERDICTS = ("CONFIRMED", "PLAUSIBLE")


def designed_perspectives(design_dir: Path) -> list[str]:
    ids = []
    for path in sorted(design_dir.glob("*.json")):
        design = json.loads(path.read_text(encoding="utf-8"))
        if "unit" in design and design.get("ok"):
            ids += [f"{design['unit']}/{p['id']}" for p in design["perspectives"]]
    return ids


def problems_of(verdict: dict, designed: list[str]) -> list[str]:
    problems = []
    for cluster in verdict.get("clusters", []):
        if cluster.get("verdict") not in VERDICTS:
            problems.append(f"cluster {cluster.get('id')} verdict is not one of {VERDICTS}; REJECTED clusters are not listed")
        if cluster.get("severity") not in ("BLOCKER", "MAJOR", "MINOR", "NIT"):
            problems.append(f"cluster {cluster.get('id')} has no rv severity")
    stated = {p.get("id"): p for p in verdict.get("perspectives", [])}
    missing = [p for p in designed if p not in stated]
    if missing:
        problems.append(f"perspectives {missing} are not in the verdict file; state for each whether every check was decided by its means")
    unknown = sorted(set(stated) - set(designed))
    if unknown:
        problems.append(f"perspectives {unknown} were not built by design.py for this review")
    bad = [pid for pid, p in stated.items() if not isinstance(p.get("decided"), bool)]
    if bad:
        problems.append(f"perspectives {bad} have no boolean `decided`")
    return problems


def judge(verdict: dict) -> dict:
    clusters = verdict.get("clusters", [])
    blocking = [c["id"] for c in clusters if c["severity"] in BLOCKING and c["verdict"] == "CONFIRMED"]
    unsettled = [c["id"] for c in clusters if c["severity"] in BLOCKING and c["verdict"] == "PLAUSIBLE"]
    undecided = [p["id"] for p in verdict.get("perspectives", []) if not p["decided"]]
    questions = [q["id"] for q in verdict.get("questions", [])]
    minor = [c["id"] for c in clusters if c["severity"] not in BLOCKING]
    if blocking:
        decision, reason = "차단", f"확정된 차단 등급 반례 {blocking}"
    elif unsettled or undecided:
        decision, reason = "증거 부족", f"확정하지 못한 차단 등급 의심 {unsettled}, 점검을 다 판정하지 못한 관점 {undecided}"
    elif questions or minor:
        decision, reason = "조건부 수용", f"사람에게 묻는 항목 {questions}, 비차단 지적 {minor}"
    else:
        decision, reason = "수용", "확정된 반례, 질문, 미확인 관점이 없다"
    risks = list(verdict.get("risks", []))
    risks += [f"관점 {pid} 는 점검을 정한 수단으로 다 판정하지 못했다: {p.get('note', '')}".rstrip(": ")
              for p in verdict.get("perspectives", []) if not p["decided"] for pid in [p["id"]]]
    risks += [f"{c['id']} 는 발생 조건을 확정하지 못했다" for c in clusters if c["verdict"] == "PLAUSIBLE"]
    return {"decision": decision, "reason": reason, "confirmed": [c["id"] for c in clusters if c["verdict"] == "CONFIRMED"],
            "questions": questions, "residual_risk": risks}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Decide the srv verdict by rule.")
    parser.add_argument("--design", required=True, help="design directory of this review")
    parser.add_argument("--verdict", required=True, help="the operator's verified clusters, questions, perspectives, risks")
    parser.add_argument("--out", help="write the judgment JSON here as well")
    options = parser.parse_args(argv)
    try:
        verdict = json.loads(Path(options.verdict).read_text(encoding="utf-8"))
        designed = designed_perspectives(Path(options.design))
    except (OSError, ValueError, KeyError) as error:
        print(f"verdict: {error}", file=sys.stderr)
        return 2
    problems = problems_of(verdict, designed)
    if problems:
        print("verdict: " + "; ".join(problems) + ". The decision rests on every perspective and cluster being "
              "accounted for; add the missing rows with what was verified, do not drop a perspective to reach a decision.",
              file=sys.stderr)
        return 2
    judgment = judge(verdict)
    text = json.dumps(judgment, ensure_ascii=False, indent=2)
    if options.out:
        Path(options.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
