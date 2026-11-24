#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["tqdm"]
# ///
"""srv as one review team: every stage of a review in one command, so an omp operator runs it and reads one file.

The user's words (2026-11-24): "근데 리뷰하는 세션은 omp이고, 그걸 omp가 srv 절차를 따라서 리뷰를 잘 할 수
있어야돼.", "무작정 넓게가 아니라 정확한 관점과 타겟을 고정해서 그것들에 대하 리뷰하게 하라고 . 그에 필요한
저장소 전체 맥락을 정리해서 전달하고.", "하나의 리뷰 팀처럼 동작하라고.", "유기적으로.".

The team follows Fagan's inspection (Fagan 1976, IBM Systems Journal 15(3)): an overview educates the whole team
(`context.py`), inspectors each read from one perspective (Basili et al. 1996: "operational scenarios where members
of a review team read a document from a particular perspective"; "a combination of techniques provides coverage of
the entire document"), "Questions raised are pursued only to the point at which an error is recognized. It is noted
by the moderator", and the moderator reports. Mapping the moderator's routing to code is this skill's reading of
Fagan, not Fagan's words: an inspector's question about a change goes to the perspectives whose breadth holds that
change, and those inspectors answer it in the next round.

Stages, each timed, with the model server's prefill and decode seconds read from its metrics around it:
1. context: the shared pack (`context.py`).
2. design: change set per unit and the perspectives (`design.py`, structured-output calls).
3. inspect: one omp inspector session per perspective (`sweep.py`); each reports what it observed per check
   (`checked`), its findings, and questions about other changes.
4. judge: one structured-output call per perspective decides its value from the value, `broken_if`, and the
   observations only, never from an inspector's own conclusion. On PR #1726 an inspector observed a concept tested
   in five queries with no shared predicate and still called its value kept; given only the value and those
   observations, the same model said broken five times of five (~/agent-assets/rebot/srv-team-poc).
5. route: questions to the perspectives whose breadth holds their target, and each undecided perspective's
   `broken_if` back to it, answered by one omp session each (`followup.py`); the judge then runs again on them.
6. verify: findings clustered by location; a cluster is CONFIRMED only when its anchor is at the head and every
   one of `VERIFY_SAMPLES` structured-output calls, shown the head lines, confirms it; REJECTED or OUT-OF-SCOPE
   only when every call says so; anything else stays PLAUSIBLE, so what the team did not establish never becomes a
   confirmed defect or an acceptance.
7. verdict and document: `verdict.py` decides by rule; REVIEW.md is written from the records.

Usage:
  uv run team.py --units units.json --diff diff.patch --repo HEAD_WORKTREE --requirements FILE [FILE ...] \
      --out REVIEW_DIR --base-url URL --model MODEL [--api-key-env NAME] [--sandbox-ro DIR]
Exit codes: 0 the review is written, 1 a stage left part of the change unreviewed, 2 bad input.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

BIN = Path(__file__).resolve().parent
REFERENCES = BIN.parent / "references"
JUDGE_SAMPLES = 3
VERIFY_SAMPLES = 3
QUESTIONS_PER_PERSPECTIVE = 2  # a routed round answers at most this many questions per perspective
WINDOW = 20
METRICS = ("vllm:prompt_tokens_total", "vllm:generation_tokens_total", "vllm:request_prefill_time_seconds_sum",
           "vllm:request_decode_time_seconds_sum", "vllm:request_prefill_time_seconds_count")
LOCATION_RE = re.compile(r"([\w./-]+\.\w+):(\d+)")
ANCHORED = ("exact", "moved", "nearest")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, path
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sweep = load_module("srv_sweep", BIN / "sweep.py")
context_script = load_module("srv_context", BIN / "context.py")
design = load_module("srv_design", BIN / "design.py")
followup = load_module("srv_followup", BIN / "followup.py")
verdict = load_module("srv_verdict", BIN / "verdict.py")

JUDGE_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["verdict", "decisive", "reason"],
                "properties": {"verdict": {"enum": ["holds", "broken", "undecided"]},
                               "decisive": {"type": "array", "items": {"type": "integer"}},
                               "reason": {"type": "string"}}}
VERIFY_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["verdict", "severity", "reason"],
                 "properties": {"verdict": {"enum": ["CONFIRMED", "REJECTED", "PLAUSIBLE", "OUT-OF-SCOPE"]},
                                "severity": {"enum": list(sweep.SEVERITIES)}, "reason": {"type": "string"}}}
JUDGE_BRIEF = (
    "You decide whether one value holds over a code change, from observed facts only. The value, the state that "
    "breaks it, and its depth were fixed before the review; the facts were observed at the head by inspectors. "
    "broken: the facts show the state that breaks the value, or another state the value forbids. holds: the facts "
    "show the value kept at every place it is at stake. undecided: the facts do not reach a place where it is at "
    "stake. Judge the value as written, every clause of it; do not narrow it and do not accept a reason the value "
    "does not give. `decisive` lists the numbers of the facts the verdict rests on. Write `reason` in Korean. "
    "Answer with one JSON object."
)


def parallel(call, times: int) -> list:
    """`times` independent samples of one call, sent at once: the samples' wall time is one call's, not their sum."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=times) as pool:
        return list(pool.map(lambda _: call(), range(times)))


def strip(text: str) -> str:
    return sweep.strip_frontmatter(text).strip()


# ---------------------------------------------------------------- server metrics


def server_metrics(urls: list[str], model: str) -> dict[str, float]:
    """The counters for `model` (its `model_name` label), summed over every metrics URL and label set; empty when one
    URL does not answer, because a partial sum would read as a drop. A server behind a load balancer answers each
    read from one replica, so its replicas' own metrics URLs are passed (`--metrics-url`), not the balancer's."""
    values: dict[str, float] = {}
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                text = response.read().decode("utf-8", errors="replace")
        except OSError:
            return {}
        add_metrics(values, text, model)
    return values


def add_metrics(values: dict[str, float], text: str, model: str) -> None:
    for line in text.splitlines():
        name = line.split("{", 1)[0].split(" ", 1)[0]
        if name in METRICS and f'model_name="{model}"' in line:
            values[name] = values.get(name, 0.0) + float(line.rsplit(" ", 1)[1])
    return values


def metric_delta(before: dict[str, float], after: dict[str, float]) -> dict[str, float]:
    """After minus before; a counter that went down was reset between the reads, so its delta is not known."""
    return {name.removeprefix("vllm:"): round(after[name] - before[name], 1)
            for name in METRICS if name in before and name in after and after[name] >= before[name]}


class Stages:
    """Wall time and server work of each stage, written to `team-summary.json` as each stage ends."""

    def __init__(self, out: Path, urls: list[str], model: str) -> None:
        self.out, self.urls, self.model, self.rows = out, urls, model, []

    def run(self, name: str, work):
        before, started = server_metrics(self.urls, self.model), time.monotonic()
        try:
            return work()
        finally:
            self.rows.append({"stage": name, "seconds": round(time.monotonic() - started, 1),
                              "server": metric_delta(before, server_metrics(self.urls, self.model))})
            self.write()

    def write(self, **extra) -> None:
        summary = {"stages": self.rows, "total_s": round(sum(r["seconds"] for r in self.rows), 1), **extra}
        (self.out / "team-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- judge


def facts_of(results: list[dict]) -> list[dict]:
    """Every observation inspectors reported for one perspective, in round and sample order."""
    return [{"location": row["location"], "observation": row["result"]} for result in results for row in result.get("checked", [])]


def judge_messages(perspective: dict, facts: list[dict]) -> list[dict]:
    checks = "\n".join(f"- {c['question']}" for c in perspective["checks"])
    listed = "\n".join(f"{n}. {f['location']}: {f['observation']}" for n, f in enumerate(facts, 1))
    user = (f"Value ({perspective['depth']}): {perspective['value']}\n\nBroken if: {perspective['broken_if']}\n\n"
            f"Checks the inspectors answered:\n{checks}\n\nFacts:\n{listed or '(none reported)'}")
    return [{"role": "system", "content": JUDGE_BRIEF}, {"role": "user", "content": user}]


def majority(verdicts: list[str]) -> str:
    """The verdict more than half of the samples gave; `undecided` when none has a majority."""
    value, count = Counter(verdicts).most_common(1)[0] if verdicts else ("undecided", 0)
    return value if count * 2 > len(verdicts) else "undecided"


def judge_perspectives(perspectives: list[dict], results: dict[str, list[dict]], options) -> dict[str, dict]:
    """One judgment per perspective from `JUDGE_SAMPLES` calls, run all at once."""
    def one(perspective: dict) -> dict:
        facts = facts_of(results.get(perspective["id"], []))
        if not facts:
            return {"verdict": "undecided", "facts": [], "decisive": [], "reasons": ["관찰이 보고되지 않았다"]}
        messages = judge_messages(perspective, facts)
        replies = parallel(lambda: sweep.request_json(messages, options, lambda a: [], JUDGE_SCHEMA, "srv-judge"), JUDGE_SAMPLES)
        answers = [r.answer for r in replies if r.answer]
        decided = majority([a["verdict"] for a in answers])
        decisive = sorted({n for a in answers if a["verdict"] == decided for n in a["decisive"] if 1 <= n <= len(facts)})
        return {"verdict": decided, "facts": facts, "decisive": decisive,
                "reasons": [a["reason"] for a in answers if a["verdict"] == decided]}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(perspectives))) as pool:
        return dict(zip((p["id"] for p in perspectives), pool.map(one, perspectives)))


def judged_findings(perspectives: dict[str, dict], judgments: dict[str, dict], repo: Path) -> list[dict]:
    """A broken value becomes a finding at its first decisive location, so the structure it names is verified and
    reported like any inspector's finding; its other decisive locations stay in the evidence."""
    findings = []
    for pid, judgment in judgments.items():
        if judgment["verdict"] != "broken":
            continue
        decisive = [judgment["facts"][n - 1] for n in judgment["decisive"]] or judgment["facts"]
        located = [m for f in decisive for m in LOCATION_RE.finditer(f["location"])]
        if not located:
            continue
        path, line = located[0].group(1), int(located[0].group(2))
        lines = sweep.anchor_findings.head_lines(repo, path) or []
        anchor = lines[line - 1].strip() if 0 < line <= len(lines) else ""
        findings.append(sweep.anchor_findings.anchor_finding({
            "id": f"J-{pid}", "severity": "MAJOR", "file": path, "line": line, "anchor": anchor,
            "condition": judgment["reasons"][0] if judgment["reasons"] else perspectives[pid]["broken_if"],
            "evidence": "; ".join(f"{f['location']}: {f['observation']}" for f in decisive),
            "fix": "", "perspective": pid,
        }, repo))
    return findings


# ---------------------------------------------------------------- route


def route_questions(perspectives: list[dict], results: dict[str, list[dict]], judgments: dict[str, dict]) -> list[dict]:
    """The routed round: each question about a change goes to the perspectives whose breadth holds it (an inverted
    index from change id to perspectives), and each undecided perspective gets its own `broken_if` back; at most
    `QUESTIONS_PER_PERSPECTIVE` per perspective, the undecided one first."""
    holders: dict[str, list[str]] = {}
    for p in perspectives:
        for change in p["breadth"]:
            holders.setdefault(change, []).append(p["id"])
    by_id = {p["id"]: p for p in perspectives}
    queued: dict[str, list[str]] = {}
    for pid, judgment in judgments.items():
        if judgment["verdict"] == "undecided":
            queued.setdefault(pid, []).append(
                f"이 관점의 가치가 깨지는 상태는 다음이다: {by_id[pid]['broken_if']} 넓이의 변화마다 이 상태가 있는지를 "
                "head 에서 보고, 본 위치와 관찰을 checked 에 적어라.")
    for pid, rows in results.items():
        for result in rows:
            for q in result.get("questions", []):
                for target in holders.get(q["about"].strip(), []):
                    if target != pid and q["question"] not in queued.get(target, []):
                        queued.setdefault(target, []).append(f"({pid} 의 질문, {q['about']}) {q['question']}")
    questions, number = [], 0
    for pid in by_id:
        for text in queued.get(pid, [])[:QUESTIONS_PER_PERSPECTIVE]:
            number += 1
            questions.append({"id": f"Q{number}", "perspective": pid, "question": text})
    return questions


# ---------------------------------------------------------------- verify


def head_window(repo: Path, path: str, line: int, radius: int) -> str:
    lines = sweep.anchor_findings.head_lines(repo, path)
    if not lines:
        return f"### {path} (not at the head)"
    spans = sweep.line_windows([(line, line)], len(lines), radius)
    return f"### {path}\n" + (sweep.numbered_lines(lines, spans) if spans else "(the line is past the end of the file)")


def verify_messages(group: list[dict], repo: Path, pack: str, brief: str, changes: dict) -> list[dict]:
    claims = "\n\n".join(
        f"- {f['id']} [{f['severity']}] {f['file']}:{f['line']} `{f['anchor']}`\n  condition: {f['condition']}\n"
        f"  evidence: {f['evidence']}" for f in group)
    places = {(f["file"], f["line"]) for f in group}
    for f in group:
        places |= {(m.group(1), int(m.group(2))) for m in LOCATION_RE.finditer(f["evidence"])}
    shown = "\n\n".join(head_window(repo, path, line, WINDOW if (path, line) == (group[0]["file"], group[0]["line"]) else 4)
                        for path, line in sorted(places)[:12])
    files = [{"path": path} for path in sorted({path for path, _ in places}) if path in changes]
    hunks = sweep.labelled_diff(changes, {"files": files}) if files else "(the change does not touch these files)"
    user = (f"{pack}\n\n# Claims about one place\n\n{claims}\n\n# Head lines they cite (line number, `|`, then the line)"
            f"\n\n{shown}\n\n# What the change did to these files\n\n```diff\n{hunks}\n```")
    return [{"role": "system", "content": brief}, {"role": "user", "content": user}]


def decide_cluster(group: list[dict], answers: list[dict]) -> tuple[str, str]:
    """CONFIRMED only when the claim's line is at the head and every verify call confirms it; REJECTED or OUT-OF-SCOPE
    only when every call says so; anything else stays PLAUSIBLE. The severity is the most common one the confirming
    calls gave, the higher on a tie."""
    verdicts = [a["verdict"] for a in answers]
    anchored = any(f.get("anchor_status") in ANCHORED for f in group)
    if len(answers) == VERIFY_SAMPLES and len(set(verdicts)) == 1 and (verdicts[0] != "CONFIRMED" or anchored):
        decided = verdicts[0]
    else:
        decided = "PLAUSIBLE"
    pool = [a["severity"] for a in answers if a["verdict"] == decided] or [a["severity"] for a in answers] or ["MINOR"]
    counts = Counter(pool)
    severity = min(counts, key=lambda s: (-counts[s], sweep.SEVERITIES.index(s)))
    return decided, severity


def candidates(findings: list[dict]) -> list[dict]:
    """One unverified cluster per finding. Two defects at neighbouring lines are different defects, so findings are
    not grouped by place (run 10a: a wording defect and a missing-result defect two lines apart became one cluster);
    `merge` joins duplicates by meaning."""
    return [{"id": f"R-{n:03d}", "verdict": "PENDING", "severity": f["severity"], "evidence": "read",
             "file": f["file"], "line": f["line"], "anchor": f["anchor"],
             "members": [f"{f.get('perspective', '')}:{f['id']}"], "finding": f,
             "condition": f["condition"], "fix": f["fix"], "reasons": []} for n, f in enumerate(findings, 1)]


def verify(clusters: list[dict], repo: Path, pack: str, changes: dict, options) -> None:
    """Set each given cluster's verdict and severity from `VERIFY_SAMPLES` calls on its finding, all at once."""
    brief = strip((REFERENCES / "verify.md").read_text(encoding="utf-8"))

    def one(cluster: dict) -> list[dict]:
        messages = verify_messages([cluster["finding"]], repo, pack, brief, changes)
        return [r.answer for r in parallel(lambda: sweep.request_json(messages, options, lambda a: [], VERIFY_SCHEMA,
                                                                      "srv-verify"), VERIFY_SAMPLES) if r.answer]

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(clusters))) as pool:
        for cluster, answers in zip(clusters, pool.map(one, clusters)):
            cluster["verdict"], cluster["severity"] = decide_cluster([cluster["finding"]], answers)
            cluster["reasons"] = [a["reason"] for a in answers]


def settle(clusters: list[dict], repo: Path, pack: str, changes: dict, options) -> list[dict]:
    """Verify the clusters `merge` kept; a kept cluster that is not CONFIRMED has its merged findings verified too,
    because one of them may state the same defect so that the head lines confirm it. A confirmed duplicate confirms
    the defect it joined and lends it its severity; under a REJECTED or OUT-OF-SCOPE cluster it stands on its own."""
    kept = [c for c in clusters if "merged_into" not in c]
    verify(kept, repo, pack, changes, options)
    by_id = {c["id"]: c for c in clusters}
    unsettled = [by_id[m] for c in kept if c["verdict"] != "CONFIRMED" for m in c.get("symptoms", [])]
    verify(unsettled, repo, pack, changes, options)
    for member in unsettled:
        owner = by_id[member["merged_into"]]
        if member["verdict"] != "CONFIRMED":
            continue
        if owner["verdict"] == "PLAUSIBLE":
            owner["verdict"], owner["severity"] = "CONFIRMED", member["severity"]
        elif owner["verdict"] in ("REJECTED", "OUT-OF-SCOPE"):
            del member["merged_into"]
            owner["symptoms"].remove(member["id"])
    for c in kept:
        for m in c.get("symptoms", []):
            if by_id[m]["verdict"] == "CONFIRMED" and c["verdict"] == "CONFIRMED" and \
                    sweep.SEVERITIES.index(by_id[m]["severity"]) < sweep.SEVERITIES.index(c["severity"]):
                c["severity"] = by_id[m]["severity"]
    for c in clusters:
        c.pop("finding", None)
    return clusters


# ---------------------------------------------------------------- merge high to low

MERGE_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["same_as", "reason"],
                "properties": {"same_as": {"type": "string"}, "reason": {"type": "string"}}}
MERGE_BRIEF = (
    "You decide whether one finding of a code review is already covered by findings kept before it. Covered means "
    "it is a symptom of a kept finding (the kept finding names the structure or cause, this one a place where it "
    "shows) or the same defect at another place; then `same_as` is that kept finding's id. A finding with its own "
    "cause, one that fixing the kept finding would not remove, is not covered: `same_as` is the empty string. "
    "Write `reason` in Korean. Answer with one JSON object."
)


def merge_order(clusters: list[dict], depth_of: dict[str, str]) -> list[dict]:
    """Clusters to keep, high-level first: a cluster is high when a member comes from a `high` perspective. Only
    CONFIRMED and PLAUSIBLE clusters take part; within a level the more severe come first."""
    live = [c for c in clusters if c["verdict"] not in ("REJECTED", "OUT-OF-SCOPE")]
    level = lambda c: 0 if any(depth_of.get(m.split(":", 1)[0]) == "high" for m in c["members"]) else 1  # noqa: E731
    return sorted(live, key=lambda c: (level(c), sweep.SEVERITIES.index(c["severity"]), c["verdict"] != "CONFIRMED"))


def merge(clusters: list[dict], depth_of: dict[str, str], options) -> list[dict]:
    """The user's words (2026-11-24): "계획 이후 리뷰는 병렬로 수행하되, 끝나고 하이레벨 -> 로우레벨 순으로 검토해서
    중복 없는 지적사항만 남겨." Clusters are ordered high-level first (`merge_order`); each is compared with every
    cluster before it, all comparisons at once, by the majority of `JUDGE_SAMPLES` calls. A cluster that is a
    symptom or a duplicate of an earlier one joins the cluster that earlier one finally belongs to
    (`merged_into`), so only clusters with their own cause remain."""
    ordered = merge_order(clusters, depth_of)

    def compare(index: int) -> str:
        cluster, earlier = ordered[index], ordered[:index]
        listed = "\n".join(f"- {k['id']} [{k['severity']}] {k['file']}:{k['line']}: {k['condition']}" for k in earlier)
        user = (f"Kept findings:\n{listed}\n\nFinding to decide:\n- {cluster['id']} [{cluster['severity']}] "
                f"{cluster['file']}:{cluster['line']}: {cluster['condition']}")
        messages = [{"role": "system", "content": MERGE_BRIEF}, {"role": "user", "content": user}]
        replies = parallel(lambda: sweep.request_json(messages, options, lambda a: [], MERGE_SCHEMA, "srv-merge"), JUDGE_SAMPLES)
        ids = {k["id"] for k in earlier}
        target = majority([r.answer["same_as"] if r.answer and r.answer["same_as"] in ids else "" for r in replies])
        return target if target in ids else ""

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(ordered))) as pool:
        targets = list(pool.map(compare, range(1, len(ordered))))
    by_id = {c["id"]: c for c in ordered}
    for cluster, target in zip(ordered[1:], targets):
        while target and "merged_into" in by_id[target]:
            target = by_id[target]["merged_into"]
        if target:
            cluster["merged_into"] = target
            by_id[target].setdefault("symptoms", []).append(cluster["id"])
    return clusters


# ---------------------------------------------------------------- records and document


def round_results(directory: Path) -> dict[str, list[dict]]:
    """Valid task outputs of one round, by perspective."""
    results: dict[str, list[dict]] = {}
    for path in sorted(directory.glob("change__*.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        if result.get("ok"):
            results.setdefault(result["perspective"], []).append(result)
    return results


def ran_counterexample(out: Path, questions: list[dict]) -> set[str]:
    """Perspectives whose inspector sessions called `sandbox_run`, read from the rounds' session logs."""
    owner = {f"change__{q['id']}": q["perspective"] for q in questions}
    ran = set()
    for log in (out / "round-1" / "sessions.jsonl", out / "round-2" / "sessions.jsonl"):
        for line in log.read_text(encoding="utf-8").splitlines() if log.is_file() else []:
            row = json.loads(line)
            if row.get("event") == "session" and any(c.get("tool") == "sandbox_run" for c in row.get("tools", [])):
                label = row["label"]
                ran.add(owner.get(label, label.removeprefix("change__")))
    return ran


def decided(perspective: dict, judgment: dict, ran: set[str]) -> bool:
    """A perspective is decided when the judge said holds or broken and, if a check's means is `execute`, an
    inspector of it ran a counterexample: a value whose deciding run never happened is residual risk, not a pass."""
    needs_run = any(c["means"] == "execute" for c in perspective["checks"])
    return judgment.get("verdict") in ("holds", "broken") and (not needs_run or perspective["id"] in ran)


def findings_of(results: dict[str, list[dict]]) -> list[dict]:
    return [{**f, "id": f"{r['task']}/{f['id']}", "perspective": pid}
            for pid, rows in results.items() for r in rows for f in r.get("findings", [])]


def write_document(out: Path, clusters: list[dict], judgment: dict, perspectives: list[dict], judgments: dict,
                   summary: dict, head: str) -> None:
    confirmed = [c for c in clusters if c["verdict"] == "CONFIRMED" and "merged_into" not in c]
    counts = Counter(c["severity"] for c in confirmed)
    rows = "\n".join(f"| {c['id']} | {c['severity']} | `{c['file']}:{c['line']}` | {c['condition']}{' (같은 결함: ' + ', '.join(c['symptoms']) + ')' if c.get('symptoms') else ''} | {c['evidence']} | {c['fix']} |"
                     for c in confirmed)
    plausible = "\n".join(f"- {c['id']} [{c['severity']}] `{c['file']}:{c['line']}`: {c['condition']}"
                          for c in clusters if c["verdict"] == "PLAUSIBLE" and "merged_into" not in c)
    rejected = "\n".join(f"- {c['id']} `{c['file']}:{c['line']}`: {c['reasons'][0] if c['reasons'] else ''}"
                         for c in clusters if c["verdict"] in ("REJECTED", "OUT-OF-SCOPE"))
    lenses = "\n".join(f"| {p['id']} | {p['depth']} | {p['value']} | {p['broken_if']} | {len(p['breadth'])} | "
                       f"{judgments.get(p['id'], {}).get('verdict', '-')} |" for p in perspectives)
    stages = "\n".join(f"| {s['stage']} | {s['seconds']} | {s['server'].get('request_prefill_time_seconds_sum', '-')} | "
                       f"{s['server'].get('request_decode_time_seconds_sum', '-')} |" for s in summary["stages"])
    text = f"""# srv 리뷰

## 확정 결함

결정: **{judgment['decision']}** ({judgment['reason']}). head `{head}`. 확정 {len(confirmed)}묶음
({', '.join(f'{s} {counts[s]}' for s in sweep.SEVERITIES if counts[s])}).

| id | 심각도 | 위치 | 발생 조건과 결과 | 근거 등급 | 고칠 방향 |
| --- | --- | --- | --- | --- | --- |
{rows}

## 잔여 위험

{chr(10).join('- ' + r for r in judgment['residual_risk']) or '없음'}

{plausible}

## 관점

| id | 깊이 | 가치 | 깨지는 상태 | 넓이(변화 수) | 판정 |
| --- | --- | --- | --- | --- | --- |
{lenses}

## 기각한 제안

{rejected or '없음'}

## 단계별 시간

| 단계 | 초 | 서버 prefill 초 합 | 서버 decode 초 합 |
| --- | --- | --- | --- |
{stages}

## 검증 범위

묶음 판정은 구조화 출력 호출 {VERIFY_SAMPLES}회가 모두 같을 때만 확정이나 기각이 되고, 나머지는 미확정으로 남는다.
근거 등급 `read` 는 head 의 줄을 읽어 판정했다는 뜻이다. 리뷰어가 `sandbox_run` 으로 돌린 반례를 이 스크립트가
다시 돌리지는 않는다.
"""
    (out / "REVIEW.md").write_text(text, encoding="utf-8")


# ---------------------------------------------------------------- the run


def call_main(main, argv: list[str]) -> int:
    code = main(argv)
    if code:
        raise StageFailed(code)
    return code


class StageFailed(Exception):
    pass


def run_team(options: argparse.Namespace) -> int:
    out = Path(options.out)
    out.mkdir(parents=True, exist_ok=True)
    repo = Path(options.repo)
    diff_sha256 = hashlib.sha256(Path(options.diff).read_bytes()).hexdigest()
    stages = Stages(out, options.metrics_url or [options.base_url.rstrip("/").removesuffix("/v1") + "/metrics"], options.model)
    model = ["--base-url", options.base_url, "--model", options.model,
             *(["--api-key-env", options.api_key_env] if options.api_key_env else [])]
    common = ["--units", options.units, "--diff", options.diff, "--repo", options.repo]
    sandbox = [part for d in options.sandbox_ro for part in ("--sandbox-ro", d)]
    inspect = ["--reasoning-effort", options.inspect_effort, "--timeout", str(options.inspect_timeout)]
    context_dir, design_dir = str(out / "context"), str(out / "design")
    try:
        stages.run("context", lambda: call_main(context_script.main, [*common, "--requirements", *options.requirements, "--out", context_dir]))
        stages.run("design", lambda: call_main(design.main, [*common, "--context", context_dir, "--out", design_dir,
                                                             "--reasoning-effort", options.design_effort,
                                                             *(["--pick-effort", options.pick_effort] if options.pick_effort is not None else []),
                                                             *model]))
        stages.run("inspect", lambda: call_main(sweep.main, [*common, "--design", design_dir, "--context", context_dir,
                                                             "--out", str(out / "round-1"), *inspect, *sandbox, *model]))
    except StageFailed as failure:
        print(f"team: a stage exited {failure.args[0]}; its own message above names the unreviewed part and the "
              "rerun. Rerun team.py after fixing it; finished stages are kept where their scripts keep them.", file=sys.stderr)
        return 1
    plan = json.loads(Path(options.units).read_text(encoding="utf-8"))
    _, design_set = sweep.load_design(Path(design_dir), plan, diff_sha256)
    perspectives = design_set["perspectives"]
    by_id = {p["id"]: p for p in perspectives}
    pack = sweep.read_pack(Path(context_dir), diff_sha256)
    judge_options = argparse.Namespace(**{**vars(options), "reasoning_effort": options.judge_effort,
                                          "max_tokens": 16384, "timeout": 300})
    results = round_results(out / "round-1")
    judgments = stages.run("judge", lambda: judge_perspectives(perspectives, results, judge_options))
    questions = route_questions(perspectives, results, judgments)
    (out / "round-2").mkdir(exist_ok=True)
    (out / "round-2" / "questions.json").write_text(json.dumps(questions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if questions:
        def routed() -> int:
            return followup.main(["--questions", str(out / "round-2" / "questions.json"), *common, "--design", design_dir,
                                  "--context", context_dir, "--out", str(out / "round-2"), *inspect, *sandbox, *model])
        stages.run("route", routed)
        second = {}
        for path in sorted((out / "round-2").glob("change__Q*.json")):
            result = json.loads(path.read_text(encoding="utf-8"))
            question = next(q for q in questions if f"change__{q['id']}" == result["task"])
            if result.get("ok"):
                second.setdefault(question["perspective"], []).append(result)
        again = [by_id[pid] for pid in second]
        merged = {pid: results.get(pid, []) + second.get(pid, []) for pid in by_id}
        judgments.update(stages.run("judge-2", lambda: judge_perspectives(again, merged, judge_options)))
        results = merged
    (out / "judgments.json").write_text(json.dumps(judgments, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    findings = findings_of(results) + judged_findings(by_id, judgments, repo)
    verify_options = argparse.Namespace(**{**vars(judge_options), "reasoning_effort": options.verify_effort})
    changes = {c.path: c for c in sweep.plan_units.parse_diff(Path(options.diff).read_text(encoding="utf-8"))}
    # The user's order (2026-11-24, "끝나고 하이레벨 -> 로우레벨 순으로 검토해서 중복 없는 지적사항만 남겨"): merge
    # first, so verification runs once per remaining defect instead of once per duplicate.
    depth_of = {p["id"]: p["depth"] for p in perspectives}
    merge_options = argparse.Namespace(**{**vars(judge_options), "reasoning_effort": options.merge_effort})
    clusters = stages.run("merge", lambda: merge(candidates(findings), depth_of, merge_options))
    clusters = stages.run("verify", lambda: settle(clusters, repo, pack, changes, verify_options))
    (out / "clusters.json").write_text(json.dumps(clusters, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ran = ran_counterexample(out, questions)
    record = {
        "clusters": [{k: c[k] for k in ("id", "severity", "verdict", "evidence")} for c in clusters
                     if c["verdict"] in verdict.VERDICTS and "merged_into" not in c],
        "questions": [],
        "perspectives": [{"id": pid, "decided": decided(by_id[pid], judgments.get(pid, {}), ran),
                          "note": "; ".join(judgments.get(pid, {}).get("reasons", [])[:1])} for pid in by_id],
        "risks": [],
    }
    (out / "verdict.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    problems = verdict.problems_of(record, list(by_id))
    if problems:
        print("team: " + "; ".join(problems), file=sys.stderr)
        return 1
    judgment = verdict.judge(record)
    (out / "judgment.json").write_text(json.dumps(judgment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stages.write(decision=judgment["decision"])
    summary = json.loads((out / "team-summary.json").read_text(encoding="utf-8"))
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    write_document(out, clusters, judgment, perspectives, judgments, summary, head)
    print(json.dumps({"decision": judgment["decision"], "confirmed": len(judgment["confirmed"]),
                      "total_s": summary["total_s"], "review": str(out / "REVIEW.md")}, ensure_ascii=False))
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="srv: one review team, every stage in one command.")
    parser.add_argument("--units", required=True, help="unit plan from rv/bin/plan-units.py")
    parser.add_argument("--diff", required=True)
    parser.add_argument("--repo", required=True, help="head worktree")
    parser.add_argument("--requirements", required=True, nargs="+", help="requirement copies")
    parser.add_argument("--out", required=True, help="review directory")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-key-env")
    parser.add_argument("--sandbox-ro", action="append", default=[])
    parser.add_argument("--metrics-url", action="append", default=[],
                        help="a Prometheus metrics URL of the model server; repeat it for each replica behind a load "
                        "balancer (default: the base URL's /metrics)")
    parser.add_argument("--design-effort", default="high")
    parser.add_argument("--inspect-effort", default="medium", help="omp --thinking of the inspector sessions; on PR #1470 "
                        "medium held eight of eight in 201 s of inspection (run 10c) where high took 438 s (run 11b)")
    parser.add_argument("--inspect-timeout", type=float, default=900, help="omp --max-time of each inspector session")
    # Measured on the rounds of run 11b (PR #1470, replays 12a and 12b, ~/agent-assets/rebot/srv-measure-11): with
    # reasoning off ("none"), judge and verify kept all eight findings and verify fell from 108 s to 5 s; merge without
    # reasoning joined defects with different causes and hid two findings, so merge keeps the server's default.
    parser.add_argument("--pick-effort", help="reasoning effort of the perspective step's condition, rule, and "
                        "binding calls; default the design effort")
    parser.add_argument("--judge-effort", default="none", help="reasoning effort of the judge calls; empty omits it")
    parser.add_argument("--verify-effort", default="none", help="reasoning effort of the verify calls")
    parser.add_argument("--merge-effort", default="", help="reasoning effort of the merge calls; empty omits it")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    options = parse_args(argv)
    try:
        return run_team(options)
    except (OSError, ValueError, KeyError) as error:
        print(f"team: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
