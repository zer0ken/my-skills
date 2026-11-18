---
name: prv
description: "Plan review (plan review): check a plan or design document before implementation with blind structured-output calls to the local model, one perspective each with a method checklist and several samples per perspective, then have one session of another model family verify every finding against the code and consolidate. Use when the user calls /prv or $prv, asks for a plan review or 계획 검수 (계획·설계 문서를 구현 전에 검수할 때), or when a my-workflow design stage reviews its design document. The session that owns the plan does not run it: it starts one operator session that runs every step and returns one consolidated file."
metadata:
  author: hrlee
  version: "1.11.1"
  domain: workflow
  triggers: prv, plan review, 계획 리뷰, 계획 검수, 설계 검수
  dependencies:
    - srv
    - sql-expert
    - parallel-expert
---

# prv

prv reviews a plan before any code exists. One model call per perspective and sample reads only the plan, what it answers, and the code the plan cites at the review base, and applies one perspective's checklist. One session of another model family then verifies every finding against the code, clusters them, and writes one table that the caller reads. The user's words (2026-11-14): "이 리뷰 방식을 plan review, 줄여서 prv 라는 이름의 스킬로 만들어줘", and on the method: "아무것도 모르고 계획 문서랑 코드만 가지고", "파이 에이전트로만 여러 개를 띄우는데 ... 다양한 관점을 프롬프트 주입해가지고 그 관점에 대해 리뷰하라고 하면 되지 않을까", "니 컨텍스트 낭비하지 말고, 블라인드 리뷰 끝나면 한 명이 정리하게 시켜".

The plan's owner does not run the reviewers or the consolidator or receive their notifications: one operator session runs the whole procedure and hands the owner only the verified result (section Caller and operator).

prv is not `rv`. `rv` is one adversarial review of a diff, a PR, or a document by a strong model; prv is a cheap, wide, blind sweep of a plan whose findings count only after verification. In a my-workflow run, prv is the gate of a `dev-plan` task.

## Concepts

| Name | Definition |
| --- | --- |
| caller | The session that owns the plan (its producer, or the my-workflow lead that gates it); it starts one operator and receives only the operator's closing reply and the consolidated file |
| operator | The one session that runs the Procedure: it creates the review workspace, runs the reviewers and launches the consolidator, waits for them, checks that the consolidated file exists, and archives what it created. It does not review, verify, re-grade, or edit anything |
| plan | The document under review: a design, implementation plan, or migration plan that decides structure before code changes |
| review base | The commit the plan applies to: the merge base of the working branch with the branch it targets (`git merge-base HEAD origin/HEAD`). Not the commit the work started on, which a rebase leaves behind |
| perspective | One review dimension defined by a method checklist file under `references/perspectives/`; a reviewer reports only defects inside it |
| reviewer | One structured-output call to the local model that applies one perspective to the plan (`bin/sweep.py`), blind to everything but its request |
| sample | One independent reviewer call for a perspective; a perspective runs `--samples` of them at once (default 3) and pools their findings, each marked with its sample number |
| consolidator | One session of another model family, launched by the operator, that verifies every finding and writes the consolidated table; verification is only its work |
| review workspace | The Paseo workspace one prv run creates in the operator's own project, whose directory is the review-base worktree; the consolidator runs in it, and the operator archives it when the run ends |
| confirmed cluster | A group of duplicate findings that the consolidator verified against the cited lines (CONFIRMED) |
| scope | The promise the plan answers, as rv's `## Scope of a finding` (`~/.agents/skills/rv/SKILL.md`) defines it for a change; a finding outside it is not a finding (verdict OUT-OF-SCOPE) |

## Caller and operator

The plan's owner holds the plan's context and must not spend it on raw reviews, so one session below it runs the whole review. The user's words (2026-11-17), after a lead started 18 reviewers itself and received their finish notifications: "prv를 왜 니가 받고있어 (…)", "인계해야지", "다른 세션 하나에 인계하고, 걔가 여러 세션을 띄워서 리뷰 하고, 걔가 결과 취합하고, 그걸 니가 받으라니까", and "스킬 확인하고 개선해".

1. Which role a session has. The session that produced or revised the plan, or that gates it, is the caller and runs no step of the Procedure. A session that is asked for prv and did not produce the plan, whether through the caller's operator brief or because the user called `/prv` in it, is the operator and runs the Procedure itself. The operator starts no further operator and does not hand the Procedure to another session; the consolidator is the only session it launches; the reviewers are model calls its script makes.
2. The caller's step, outside the Procedure. Start exactly one operator, in Paseo with `create_agent` and no `workspaceId`, so the operator is a subagent in the caller's own workspace. The agent and mode follow the caller's role rules; prv names none. The brief gives the operator the paths of the plan and the requirement copies, the review base (or the target branch to take it from), the perspectives to run beyond `trace` when the caller names them, the claim ledger and prior reviews when there are any, and the path of the consolidated file. It states that the operator ends its turn with the closing reply of Procedure step 5 and reports only when the run ends, when it reaches a question point, or when it is certain to exceed a time box the caller gave.
3. Who receives what. "Workspaces decide where work happens; agent parentage decides who owns the work" and "Paseo agents receive finish, error, and permission notifications by default" (https://paseo.sh/docs/mcp, checked 2026-11-17). The operator runs the reviewers and launches the consolidator, so the consolidator's notifications and questions reach the operator, and the caller receives only the operator's. The caller does not run reviewers, create the consolidator, read a reviewer file, or take a finding from any source but the consolidated file.
4. After the operator reports. A finish notification whose reply starts with `최종 보고가 아님` is not the result, and the caller does not act on it. The caller reads the closing reply and the consolidated file's top table, answers a question the operator ended its turn with, archives the operator once its report is read in full, and handles the confirmed and PLAUSIBLE clusters with the `response-rv` skill. Fixing a verified finding is the caller's; verifying one is the consolidator's.

## Inputs

1. The plan, copied into a review directory, so later edits of the plan do not change what was reviewed. Record its sha256.
2. What the plan answers (requirements, issue body and decisive comments), copied the same way.
3. A detached worktree of the repository at the review base. When the plan cites lines of uncommitted or later work, name that commit so the consolidator reads it with `git show <commit>:<path>`; the reviewers see the cited files at the review base only.
4. The perspective method files, by absolute path.
5. The plan owner's claim ledger, when there is one: each claim the plan rests on, the observation that would show it wrong, and where the owner checked it, as a my-workflow `dev-plan` record holds in its `## 주장` section. It goes to the consolidator only, which checks every cited location and names, per confirmed cluster, the ledger line it refutes or the claim the ledger missed, so the owner learns which of its checks failed instead of having the review do them.

Reviewers get nothing else: no producer conversation, no earlier review, no gate verdict, no claim ledger, which would point them at the claims the owner chose. An earlier review is given only to the consolidator, to mark what is new.

## Perspectives

Choose the perspectives the plan touches; `trace` always runs.

| Id | File | Covers |
| --- | --- | --- |
| P1 | `references/perspectives/trace.md` | Requirement-plan traceability, the solution the requirements state and the smallest mechanism, concept definitions and identity, claims about existing code, repository rules |
| P2 | `references/perspectives/query.md` | Queries, indexes, readers and writers of changed stored units (`sql-expert` DM-Querying, DM-Processing) |
| P3 | `references/perspectives/concurrency.md` | Transactions, concurrency, failure and recovery (`parallel-expert`, `sql-expert` DM-Internals) |
| P4 | `references/perspectives/backends.md` | Equivalence across storage backends and test fakes |
| P5 | `references/perspectives/ops.md` | Lifecycle of new state, background tasks, migration, public contract |
| P6 | `references/perspectives/perf.md` | Hot paths, budgets, measurement on realistic data |

A perspective is a checklist, not a persona. The user's words (2026-11-12): "전문 작업에서는 '역할극'이 아니라, 메소돌로지를 적용해야돼." A new perspective is a new method file whose items come from a field's sources or its `-expert` skill.

## Review workspace

prv runs all its sessions in a review workspace of its own and archives it when the run ends. The user's words (2026-11-14): "Prv는 호출된 파세오 프로젝트 안에 새 워크스페이스를 만들고 그 안에 필요한 세션들을 모두 소환해줘" and "그리고 끝나면 자동으로 워크스페이스를 보관햐줘".

1. Find the project: the operator's own `workspaceId` is in `get_agent_status` for its own agent id (confirm the snapshot is its own, because `PASEO_AGENT_ID` can name the session that launched it), and that workspace's `projectId` is in `list_workspaces`. The operator runs in the caller's workspace, so this is the caller's project.
2. Create the review workspace with `create_workspace`: `isolation: "local"`, `path` the review-base worktree, `projectId` the project of step 1, `title` `prv <plan name> <run number>`. Pass the `projectId` explicitly: a local workspace on a subdirectory is otherwise registered as a project of its own. Local isolation adopts the directory, so a session created there starts in the review-base worktree, which is the current directory the brief assumes.
3. Create the consolidator with `create_agent` and `workspaceId` the review workspace. A session placed in another workspace stays the operator's subagent (Paseo docs, MCP "Mental model": "Passing a `workspaceId` places that subagent in another workspace without detaching it from its parent."), so finish notifications reach the operator and stop there.
4. When the run ends, whether finished or abandoned, the operator confirms that no session in the review workspace has a running turn (`get_agent_status`), then `archive_workspace` it, which archives the sessions it owns and reports them in `archivedAgentIds`. Archiving a local workspace leaves its directory (`removedDirectory: false`), and the review files live outside it, so remove the review-base worktree afterwards with `git worktree remove`. The operator never archives the workspace it runs in: that is the caller's, and the caller archives the operator.

Outside Paseo there is no workspace to create; launch the sessions as the harness allows and skip this section.

## Procedure

The operator runs every step and waits inside its turn. Each end of an operator turn sends the caller a finish notification (the first smoke run ended a turn after every launch, and the caller was woken for each), so the operator ends its turn only with the closing reply of step 5 or with a question. While the reviewers run, it waits for their exit-code file; while the consolidator runs, it waits with `paseo wait <id> --timeout <seconds>` ("Block until an agent finishes its current task", https://paseo.sh/docs/cli, checked 2026-11-17), one session after another and repeating the call when it returns on the timeout, with the timeout inside its shell tool's limit. A turn it must end before the run is over starts with `최종 보고가 아님` and says what remains.

1. Prepare the review directory: the two copies, the review-base worktree, and the review workspace on it.
2. Check the local model server before loading it: no measurement is running on it (no open `run-*` terminal of another session that calls it, as the harness instructions require), and it answers (`curl -sS -m 5 <server>/v1/models`). When a measurement is running or the server does not answer, the operator launches nothing, does not stop or restart the server, and ends its turn with that as the question to the caller.
3. Run the reviewers: `uv run ~/.agents/skills/prv/bin/sweep.py --plan <plan copy> --requirements <copies> --repo <review-base worktree> --perspectives ~/.agents/skills/prv/references/perspectives --only <perspective ids> --out reviewers --base-url <server>/v1 --model <model> --api-key-env <variable>` in a Paseo terminal of the operator's workspace named `run-prv-<plan name>-<run number>`, ending the command line with the exit code written to a file, as the harness instructions require for a long run. The script finds the plan's `path` and `path:line` citations, reads those files at the review base (the lines around each citation, or the whole file when it is short) with the AGENTS.md files on their paths, and sends one structured-output request per perspective and sample, all at once, with the brief `references/call-brief.md`; each answer is validated, retried once when invalid, and re-located from its anchors, and each perspective writes `reviewers/plan__<perspective>.json`. A reviewer session with tools spent most of its time finding the code the plan already names, and the calls finish in the time of the slowest one (Limits). Three samples is the default because on the third trial's inputs the confirmed clusters grew 11, 16, 21 with the first, second, and third sample; raise it only with a measurement that a further sample still adds them. When a perspective fails (exit 1, `summary.json` lists it under `failed` and its file's `errors` says why), the operator reruns that perspective once with `--only`; if it fails again, it goes on with the others and names the failed perspective in its closing reply.
4. When the reviewers have finished, launch one consolidator in the review workspace (it also merges the duplicates the samples of a perspective produce), with `<REVIEW_FILES>` the `reviewers/plan__<perspective>.json` files, of another family, a Claude session on opus at high thinking (reviews go to Claude; the user's words, 2026-11-18: "모두 코덱스를 클로드로 전환해라") with `references/consolidate.md` filled, `<CLAIM_LEDGER>` included when the plan owner gave one. It verifies, clusters, and writes the consolidated file. The operator checks only that the consolidated file exists with the top section `## 현재 계획에 남은 확정 결함` (and `## 주장 원장 점검` when a ledger was given) and takes the counts from the consolidator's closing reply; it does not read, re-grade, drop, or add a cluster. A consolidator that fails twice at the same point is reported as failed, with no consolidated file; the operator passes no reviewer finding to the caller in its place.
5. Archive the review workspace and remove the review-base worktree, as step 4 of the review workspace section says, then end the turn with the closing reply, under 4,000 characters: the path of the consolidated file, the counts of confirmed clusters from the consolidator's reply, the perspectives that ran and failed with the reviewers' wall time from `summary.json`, the model-server state, and the archive result. The reply is the turn's last response; the operator sends the caller no other message.

The caller takes the confirmed clusters as findings to fix. PLAUSIBLE clusters are questions for the plan owner, not defects. REJECTED findings are dropped with the consolidator's cited line, and OUT-OF-SCOPE findings with the open issue or the review-base line it cited; neither is a finding to fix. The caller handles the confirmed and PLAUSIBLE clusters as one round of findings with the `response-rv` skill, so each fix lands on the plan node that caused it. A criticism of the consolidated file itself is also handled with `response-rv`, and when its root cause lies in this procedure or its references, fix prv so the same defect does not recur.

In a my-workflow run, the gate's judge session is the operator, the review directory is `<run root>/artifacts/<task id>-prv/` and the consolidated file is `<run root>/artifacts/<task id>-prv.md`, where `<task id>` is the `dev-plan` task the gate judges, such as `T2`.

## Limits

Agreement is not evidence. In the first trial all four blind reviewers raised the same finding (C05), and in the third four sessions shared one false premise (C18); the verifier rejected both against the code. Clusters raised by two or more sessions were confirmed more often (75-100%) than those raised by one (48.6%), but count a cluster by its verification, never by how many raised it.

Local-model severity is not used. The consolidator re-grades every finding.

A stale base produces false findings that verification does not catch. In the first trial the reviewers and the verifier all read the commit the work began on after the branch had been rebased, so a finding that called an existing table new (C01) was confirmed. Give every session the review base.

Precision varies by reviewer and is low enough that unverified findings must not reach the plan owner. First trial (#1303 r2, 2026-11-14, blind, one shared brief, no perspectives, `artifacts/blind-review-1/VERIFY-1.md`): CONFIRMED / findings per reviewer, against that stale base, were pi 9/17, pi 6/22, Hermes 4/15, Hermes 4/14, and the four together found 7 confirmed clusters that the Claude `rv` design review of the same document had not raised. Second trial (six pi reviewers, one perspective each, review base 466912e55, `artifacts/blind-review-2/CONSOLIDATED-1.md`): precision 57.14% (20/35) against 37.70% (23/61) in the first; per perspective P1 trace 5/6, P2 query 4/7, P3 concurrency 1/5, P4 backends 4/7, P5 ops 2/5, P6 perf 4/5. It recovered 15 of the first trial's 23 confirmed findings (5 of its 10 confirmed clusters; C01 did not recur at the right base) and found 9 confirmed clusters neither earlier review had raised, 8 of which still applied to the revised design. The two trials differ in perspectives and finding counts, so these numbers compare the two setups on one document, not model quality. P3's checklist produced the lowest precision; sharpen it before relying on it. Third trial (three pi sessions per perspective, the same document and base, `artifacts/blind-review-3/CONSOLIDATED-1.md`): unique confirmed clusters across the six perspectives grew 18 → 24 → 32 with the first, second, and third session; averaged over every ordering, the second session added 1.72 confirmed clusters per perspective and the third 1.28 (about 2 for P1 trace and P2 query, about 0.33 for P3 concurrency and P6 perf). Precision was 66.7% (64/96; 51.2% of all 125 findings counting PLAUSIBLE), and it recovered 16 of the second trial's 17 confirmed clusters. The added sessions cost only local GPU time, which is why three is the default.

One-call reviewers on the third trial's inputs (2026-11-18, `deepseek-v4-flash-test` on 100.99.0.1:8000, the same document, requirements, base, and method files; three samples per perspective; raw output and verification in the operator session's measurement directory): five perspectives ran together in 401.4 s (read from that run's `summary.json` before the rerun overwrote it; the slowest perspective file records 350.1 s) and `trace` in 212.5 s after its first answer stopped at 65,536 tokens, which is why the default is 131,072; each request held about 139,000 prompt tokens. The 68 findings were matched blind by an independent Claude session against the third trial's 31 confirmed clusters outside K04: they named 15 of them (K02, K03, K05, K06, K08, K09, K11-K13, K15-K17, N04, N09, N10) and 6 confirmed clusters outside that set, 21 confirmed clusters against the third trial's 32, and 35 of the 55 findings judged CONFIRMED, matched, or REJECTED were right (63.6%, against 66.7% for the third trial). So one call per perspective and sample found 15 of the 31 known clusters and 6 new ones at about the same precision in two runs of 401.4 s and 212.5 s, where the eighteen sessions with tools wrote their last output about 23 minutes after the brief (file times 04:30 to 04:53 on 2026-11-14; launch times were not recorded). It did not report K01, K07, K10, K14, N01-N03, N05-N08, or N11-N15.
