---
name: swarm-review
description: "Swarm review (srv) of a code change: the change is split into review units by a script, independent structured-output calls to the self-hosted model (three samples by default) review each unit from each perspective built from rv's review items, one operator session verifies every suggestion against the code, sends narrow follow-up questions to new reviewer sessions for further rounds, and returns one review document. Use when the user calls /srv, /swarm-review, $srv, or $swarm-review, or asks for a swarm review of a PR, branch, or commit range (코드 변경을 여러 리뷰어 세션으로 훑어 리뷰할 때)."
metadata:
  author: hrlee
  version: "0.6.2"
  domain: workflow
  triggers: srv, swarm-review, swarm review, 스웜 리뷰
  dependencies:
    - rv
    - prv
---

# swarm-review (srv)

srv reviews a code change with a swarm. A script splits the change into review units, and one call to the self-hosted model per unit and perspective reads only that unit's hunks and head files, the lines that call into it, and what the change answers; one operator session verifies every suggestion against the code, digs further with follow-up rounds, and hands one review document to the caller. The user's words (2026-11-15): "이거 /prv 참고해서, /prv와 같은 방법으로 pi 세션 많이 띄워서 코드에 대해 /rv하게 만들어. 그리고 들어오는 제안은 코덱스가 정리하고, 더 자세히 파기 위해 추가로 리뷰를 계속 해서, 결과적으로 하나의 리뷰 문서를 너한테 가져오라고 해. 이 과정을 /swarm-review , 줄여서 /srv라는 스킬로 저장해. 코덱스 세션 띄우는거 말고 그 다음 부분부터".

The skill's directory is `srv` and its `name` is `swarm-review`, so Claude Code takes both `/swarm-review` and `/srv`: "In a personal or project skill directory, `name` sets the command that the `/` menu shows and that you type, unless another command already uses that name. The directory name also invokes the skill." (https://code.claude.com/docs/en/skills, "How a skill gets its command name").

The skill starts where the operator session starts: the caller opening that session is the caller's step and is outside this skill. srv names no agent for the operator; asked who the operator should be, the user answered (2026-11-15): "이건 특정 에이전트를 위한 스킬이 아니다." The session that runs srv is the operator, whichever agent the caller chose under its own role rules.

## Relation to prv and rv

prv reviews a plan before code exists; srv reviews a code change (a PR, a branch, or a commit range) the same way, with perspectives taken from rv instead of plan checklists. `rv` is one exhaustive adversarial review by one strong reviewer, item by item in consecutive turns with an item ledger; srv is a wide, cheap, blind sweep whose suggestions count only after the operator verifies them. srv does not replace rv: the caller may run srv first and give its review document to an rv review as an earlier review, the way prv runs before the rv design review.

## Concepts

| Name | Definition |
| --- | --- |
| change | The code under review: the diff from the merge base to the head commit |
| head | The commit under review, checked out as a detached worktree that every session reads |
| merge base | `git merge-base <head> <target branch>`; the diff is taken from it, not from the commit the work started on |
| perspective | One review dimension defined by a method file under `references/perspectives/`, made of named rv review items and `-expert` sections; a reviewer reports only defects inside it. The file's frontmatter `match-*` lines decide which units it applies to |
| review unit | A group of changed files reviewed together, decided by `~/.agents/skills/rv/bin/plan-units.py`; every hunk of the change is in exactly one unit, and `units.json` lists them with the perspectives each matched |
| task | One review unit and one perspective it matched; round 1 has one task per pair |
| sample | One independent round-1 call for a task; a task runs `--samples` of them at once (default 3) and pools their findings, each marked with its sample number |
| reviewer | In round 1, one structured-output model call that reviews one task, one of its samples (`bin/sweep.py`); in later rounds, a self-hosted-model session that answers one follow-up question. Each is blind to everything but its inputs |
| anchor | The verbatim head line a finding points at; `bin/anchor-findings.py` re-locates the finding's line from it |
| operator | The session that runs srv: prepares inputs, launches reviewers, verifies and clusters every suggestion, writes follow-up questions, and writes the review document |
| suggestion | One finding a reviewer reports; it is not a defect until the operator verifies it |
| scope | The promise of the change, as rv's `## Scope of a finding` (`~/.agents/skills/rv/SKILL.md`) defines it; a suggestion outside it is not a finding (verdict OUT-OF-SCOPE) |
| cluster | A group of suggestions the operator judged to describe the same defect, with one verdict: CONFIRMED, PLAUSIBLE, or REJECTED |
| round | One launch of reviewers followed by the operator's verification of their output; round 1 is the task sweep, later rounds answer follow-up questions |
| follow-up question | A narrow question the operator writes from a verified round, sent to new reviewers to dig into one place |
| review document | The one Markdown file srv returns to the caller |

## Inputs

1. The head commit and the target branch (or merge base). Create a detached worktree of the head, save `git diff <merge base>...<head>` as `diff.patch` in the review directory, and record its sha256.
2. What the change answers: the issue body and the decisive comments and user decisions, copied into the review directory, so later edits do not change what was reviewed.
3. The perspective method files, by absolute path.

Reviewers get nothing else: no PR body, no PR reviews or replies, no design documents or measurements of the producer, no conversation. The producer's conclusions break the blindness. Earlier reviews of the same change go only to the operator, to mark which clusters are new.

## Perspectives

A perspective groups rv review items (`~/.agents/skills/rv/references/items.md`) and `-expert` sections so that one reviewer covers it in one turn; the swarm, not per-item turns, carries the thoroughness. Asked how pi reviewers should apply rv, the user chose (2026-11-15) "rv 항목을 관점으로": each perspective is a few rv items, and a reviewer reviews only its perspective. Round 1 reviews each perspective once per unit, in one call per task; `## Limits` records what that round found on a measured change. rv's item ledger and one-item-per-turn rule belong to rv's own reviewing session, not to srv reviewers.

Which perspectives a unit gets is decided by the frontmatter of each method file, not by the operator: `match: always` (`trace`, `design`, `correctness`, `tests`), `match-path` globs, `match-status` (added, deleted, renamed), and `match-line` regular expressions over the changed lines of code files (prose files, `.md`, `.mdx`, `.rst`, `.txt`, `.adoc`, get their perspectives by path only). `units.json` records the matched rule for every unit and perspective. The column below names what the patterns describe.

| Id | File | rv items and sources | Matches |
| --- | --- | --- | --- |
| trace | `references/perspectives/trace.md` | U0 problem modeling, U3-claims, repository rules | always |
| design | `references/perspectives/design.md` | U2-concepts, U2-structure, U2-quality; `python-expert` Software Design | always |
| correctness | `references/perspectives/correctness.md` | U3-safety, U3-failure, U3-security; `python-expert` 4.4.5 | always |
| tests | `references/perspectives/tests.md` | U3-tests; `python-expert` Software Testing | always |
| layout | `references/perspectives/layout.md` | U1-import, U1-layout, U1-names, U1-leftovers, U1-precedent | modules, files, or names added, moved, or renamed |
| growth | `references/perspectives/growth.md` | U1-size, U1-split, U3-reuse | new units or dependencies |
| db | `references/perspectives/db.md` | U3-db; `sql-expert` DM-Querying, DM-Processing, DM-Internals | queries, schema, storage backends |
| concurrency | `references/perspectives/concurrency.md` | U3 failure and recovery tracing; `parallel-expert` | tasks, workers, locks, retries, recovery |
| llm | `references/perspectives/llm.md` | `llm-expert` structured output, prompt engineering, diagnosis, serving | prompts, model calls, output contracts |
| cost | `references/perspectives/cost.md` | U3-cost; prv perf | hot paths, batch work, model or DB calls per unit |
| docs | `references/perspectives/docs.md` | U3-docs; `sucks` | documents, docstrings, or user-facing text |

A perspective is a checklist, not a persona. The user's words (2026-11-12): "전문 작업에서는 '역할극'이 아니라, 메소돌로지를 적용해야돼." A new perspective is a new method file whose items name their source (an rv item, an `-expert` section, or a repository rule).

## Procedure

1. Prepare the review directory: the head worktree, `diff.patch` with its sha256, and the requirement copies. Resolve the merge base with `git merge-base` and write the full SHA the command printed, never a hand-copied one: in the first run a mistyped 41-character SHA stopped a reviewer. Plan the units with `python3 -I ~/.agents/skills/rv/bin/plan-units.py --diff diff.patch --repo <head worktree> --perspectives ~/.agents/skills/srv/references/perspectives --out units.json`, and read its summary line (units, files, excluded, tasks) before going on; an excluded file is listed with its reason and is not reviewed.
2. Before loading the model server, check that it answers (`curl -sS -m 5 <server>/v1/models`) and whether another session is measuring on it (an open `run-*` terminal of another session that calls it, as the harness instructions require). Launch only when the check succeeded, chaining the launch on its exit code: in the first run a failed check did not stop the launch. When a measurement is running, ask the user whether to launch now and wait for the answer; the answer covers that run only. Asked whether srv should get a standing exception from the harness's measurement check, the user answered (2026-11-15) "앞으로도 확인하고 나한테 물어보도록 해 그럼", which replaced the earlier answer "항상 응답 확인만". Record in the procedure log the server state (for vLLM, `vllm:num_requests_running` and `vllm:num_requests_waiting` from `/metrics`), the user's answer, and how many requests or sessions were launched at what time, so a measurement on that server can account for the load.
3. Round 1: run `uv run ~/.agents/skills/srv/bin/sweep.py --units units.json --diff diff.patch --repo <head worktree> --perspectives ~/.agents/skills/srv/references/perspectives --requirements <copies> --out round-1 --base-url <server>/v1 --model <model> --api-key-env <variable>` in a Paseo terminal of the operator's workspace named `run-srv-<target>-<run number>`, ending the command line with the exit code written to a file, as the harness instructions require for a long run. It sends `--samples` independent structured-output requests per task (default 3), all in parallel up to `--max-concurrency` (default 128, the value of the measured round), because on enterprise-memory#1415 two extra samples of one unit found three causes the first sample missed while an added perspective found none. Each request carries the brief `references/brief.md`, the perspective method, the requirement copies, the unit's hunks, the unit's head files with line numbers, and the lines elsewhere at the head that name a symbol the unit changes. Each answer is validated against its JSON Schema, retried once when invalid, and its lines are re-located from their anchors; a task is valid only when every sample is, and each task writes `round-1/<unit>__<perspective>.json`, and the run writes `summary.json` (tasks, failures, wall time, slowest call, tokens, findings per severity) and `progress.json`.
4. `sweep.py` exits 1 when a task has no valid output, because that unit is then unreviewed for that perspective. Read the task file's `errors`, remove the cause (endpoint, token limit, schema), and rerun only those tasks with `--only <unit>__<perspective>`; the summary then counts every task of the plan again. A failed task is never dropped from the review or treated as reviewed.
5. Verify the round by `references/consolidate.md`: take the suggestions from the task files, open every cited `file:line` at the head (the line `anchor-findings.py` re-located; `anchor_status` says how), give each suggestion a verdict, cluster, and re-grade severity. Agreement is not evidence: judge a cluster by the code, never by how many tasks raised it.
6. Write follow-up questions by `references/deepen.md` and launch round `k` (k ≥ 2): one new reviewer session per question in a review workspace on the head worktree, created and archived exactly as prv's `## Review workspace` section describes (title `srv <target> <run number>`), with the head worktree's pyright and Serena configs prepared as the `code-analysis-tools` skill says (in the first run the unprepared worktree under the ignored `.worktrees/` path made every reviewer fall back to text search). Each session gets the blind inputs, the question, and the follow-up brief in `references/deepen.md`, and writes `round-<k>/Q<n>-result.md`. Verify the round as in step 5, merging its suggestions into the existing clusters.
7. Stop when a round adds no new CONFIRMED cluster, or after round 3, whichever comes first.
8. Write the review document `REVIEW.md` in the review directory, in the format of `references/consolidate.md`, and `procedure-log.md` beside it: steps, round 1's `summary.json` numbers, sessions per later round with launch and finish times, server state, blockers and what was changed. A time box given to a reviewer is recorded against its actual finish time; it is not a stop, and an overrun is written, not hidden.
9. When later rounds ran, confirm that no session in the review workspace has a running turn (an idle or closed session has none), archive the workspace, and remove the head worktree with `git worktree remove`, as prv's review workspace section says.
10. End the operator's turn with the counts of confirmed clusters per severity, the count of new confirmed clusters per round, the precision per round, and the path of `REVIEW.md`, under 4,000 characters. An OUT-OF-SCOPE suggestion reaches the caller only as a count. The caller reads `REVIEW.md`; accepting, rejecting, posting, and fixing are the caller's, and the caller handles the confirmed and PLAUSIBLE clusters as one round of findings with the `response-rv` skill. A criticism of `REVIEW.md` itself (a wrong verdict, a missed cluster, weak evidence) is also handled with `response-rv`, and when its root cause lies in this procedure or its references, fix srv so the same defect does not recur.

The operator edits nothing but the review directory and the ignored analysis configs of the head worktree it created: no tracked-file edits, commits, pushes, PR or issue comments, posted reviews, or messages to people. Follow-up reviewers do not start other sessions; their brief says so. The operator does not stop or restart a model server.

## Limits

Measured on one change so far: PR #1415 of graphai-repository/enterprise-memory, head a68100c, whose seven known causes (four BLOCKER, one MAJOR, two NIT) come from a blind comparison of an rv review and the first srv run (`review-compare-1/COMPARE.md` of that run, 2026-11-15). One change does not set defaults; it shows where the procedure stands.

Round 1 with one sample per task (2026-11-18, `deepseek-v4-flash-test` on 100.99.0.1:8000, server otherwise idle): 6 units, 40 tasks, 40 valid on the first call with no retry, 230.7 s wall time, set by the slowest call (230.5 s), so every task ran at once. Per task the median prompt was 15,894 tokens and the median completion 13,217 (largest 35,496). The 58 suggestions (12 MAJOR, 32 MINOR, 14 NIT) all kept their anchors exactly. An independent session verified them against the code: 21 CONFIRMED, 32 REJECTED, 1 PLAUSIBLE, 4 duplicates, so precision was 39.6%. The 21 formed 20 clusters (1 MAJOR, 2 MINOR, 17 NIT), and only the MAJOR matched a known cause: the no_fact link across a chunk boundary. The three causes inside `judge_chunk.py` lines 320-330 were in one unit and its tasks did not report them.

Two more samples of that unit's eight tasks found three causes the first sample missed (D1, D5, D7), and a perspective that traced boundary scenarios found none, so a task now runs three samples. Round 1 with three samples (same day and server; 39 tasks, because prose files no longer match code perspectives): 117 calls all valid, 470.5 s wall time at `--max-concurrency 128` (slowest task 468.4 s; up to 95 requests ran at once), 188 suggestions. Verified the same way, counting each repeat with the verdict of the suggestion it repeats: 68 CONFIRMED, 111 REJECTED, 9 PLAUSIBLE, precision 38.0%; 22 distinct confirmed clusters, among them a MAJOR outside the seven known causes (an excluded heading's label lands on the next section's sentence, `judge_chunk.py:328-330`, run on the head code). It found four known causes (D1, D2, D5, D6), but the verifier rejected the D6 suggestion, and D7, found by both extra samples before, was not reported this time. Precision per perspective ranged from 7/10 (layout) to 2/13 (correctness) and 10/50 (design).

The first run, with fifteen agent sessions and tools in round 1, took 46 min 37 s for 54 suggestions at 34.1% precision and four confirmed clusters, and its two follow-up rounds added one cluster each, six of the seven causes in about 91 minutes. So the one-call round 1 with three samples reported four known causes and confirmed three (D1, D2, D5), where the first run's round 1 confirmed four (D3, D5, D6, D7), at about the same precision in a sixth of the time; with one sample it was twelve times faster but found one. Follow-up questions sent as one-call tasks instead of tool sessions (same day; one question per verified cluster of the three-sample round, built from its place alone, three samples each): 72 calls, 630.6 s with other sessions loading the server, 187 suggestions, and none of D3, D4, D7 reported at their lines, so follow-up rounds stay tool sessions. Rounds 2 and 3 with tool sessions have not been measured on this procedure.

Two settings come from this run. `--max-tokens` counts reasoning tokens: at 16,384 a quarter of the tasks stopped at the limit with empty or cut JSON, so the default is 65,536 and an answer cut at the limit is recorded instead of retried. A unit shows whole files, smallest first, up to 60,000 characters and the rest as the lines around their changes, because whole manuals made one prompt 166,000 tokens.

Precision is CONFIRMED / (CONFIRMED + REJECTED) per suggestion; it measures how often a suggestion was true, not how many defects the review found.

Unmeasured: whether the follow-up rounds of this procedure recover the causes the first run found, and the effect of a prepared analysis config on reviewer precision. prv's plan trials agree on one point: agreement among reviewers was not evidence.
