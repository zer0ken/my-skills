---
name: prv
description: "Plan review (plan review): check a plan or design document before implementation with several blind local-model reviewers, one perspective each with a method checklist, then have one session of another model family verify every finding against the code and consolidate. Use when the user calls /prv or $prv, asks for a plan review or 계획 검수 (계획·설계 문서를 구현 전에 검수할 때), or when a my-workflow design stage reviews its design document."
metadata:
  author: hrlee
  version: "1.0.0"
  domain: workflow
  triggers: prv, plan review, 계획 리뷰, 계획 검수, 설계 검수
  dependencies:
    - sql-expert
    - parallel-expert
---

# prv

prv reviews a plan before any code exists. Several reviewer sessions each read only the plan, what it answers, and the code at the review base, and each applies one perspective's checklist. One session of another model family then verifies every finding against the code, clusters them, and writes one table that the caller reads. The user's words (2026-11-14): "이 리뷰 방식을 plan review, 줄여서 prv 라는 이름의 스킬로 만들어줘", and on the method: "아무것도 모르고 계획 문서랑 코드만 가지고", "파이 에이전트로만 여러 개를 띄우는데 ... 다양한 관점을 프롬프트 주입해가지고 그 관점에 대해 리뷰하라고 하면 되지 않을까", "니 컨텍스트 낭비하지 말고, 블라인드 리뷰 끝나면 한 명이 정리하게 시켜".

prv is not `rv`. `rv` is one adversarial review of a diff, a PR, or a document by a strong model; prv is a cheap, wide, blind sweep of a plan whose findings count only after verification. In a my-workflow design stage both run: prv first, so the design the `rv` design review reads already has prv's confirmed defects fixed.

## Concepts

| Name | Definition |
| --- | --- |
| plan | The document under review: a design, implementation plan, or migration plan that decides structure before code changes |
| review base | The commit the plan applies to: the merge base of the working branch with the branch it targets (`git merge-base HEAD origin/HEAD`; in my-workflow, `review_base` of `wf stage --json`). Not the commit the work started on, which a rebase leaves behind |
| perspective | One review dimension defined by a method checklist file under `references/perspectives/`; a reviewer reports only defects inside it |
| reviewer | A local-model session that applies one perspective to the plan, blind to everything but its inputs |
| consolidator | One session of another model family that verifies every finding and writes the consolidated table |
| confirmed cluster | A group of duplicate findings that the consolidator verified against the cited lines (CONFIRMED) |

## Inputs

1. The plan, copied into a review directory, so later edits of the plan do not change what was reviewed. Record its sha256.
2. What the plan answers (requirements, issue body and decisive comments), copied the same way.
3. A detached worktree of the repository at the review base. When the plan cites lines of uncommitted or later work, name that commit so reviewers read it with `git show <commit>:<path>`.
4. The perspective method files, by absolute path.

Reviewers get nothing else: no producer conversation, no earlier review, no gate verdict. An earlier review is given only to the consolidator, to mark what is new.

## Perspectives

Choose the perspectives the plan touches; `trace` always runs.

| Id | File | Covers |
| --- | --- | --- |
| P1 | `references/perspectives/trace.md` | Requirement-plan traceability, concept definitions and identity, claims about existing code, repository rules |
| P2 | `references/perspectives/query.md` | Queries, indexes, readers and writers of changed stored units (`sql-expert` DM-Querying, DM-Processing) |
| P3 | `references/perspectives/concurrency.md` | Transactions, concurrency, failure and recovery (`parallel-expert`, `sql-expert` DM-Internals) |
| P4 | `references/perspectives/backends.md` | Equivalence across storage backends and test fakes |
| P5 | `references/perspectives/ops.md` | Lifecycle of new state, background tasks, migration, public contract |
| P6 | `references/perspectives/perf.md` | Hot paths, budgets, measurement on realistic data |

A perspective is a checklist, not a persona. The user's words (2026-11-12): "전문 작업에서는 '역할극'이 아니라, 메소돌로지를 적용해야돼." A new perspective is a new method file whose items come from a field's sources or its `-expert` skill.

## Procedure

1. Prepare the review directory: the two copies, the review-base worktree, and one brief from `references/brief.md` with its placeholders filled. Check the brief for unfilled `<...>` before launching.
2. Check the local model server before loading it: no measurement is running on it (no open `run-*` terminal of another session that calls it, as the harness instructions require), and it answers (`curl -sS -m 5 <server>/v1/models`).
3. Launch one reviewer per perspective as a Paseo pi session (`create_agent`, provider pi, the local model, thinking high), with the brief path, the perspective's method file, and its output file `P<n>-<perspective>.md`. At most four sessions of one provider run at a time (harness Delegation practice), so launch in waves of four and start the next as one finishes. Each reviewer ends its turn with its counts and output path; do not read the review bodies.
4. When every reviewer has finished, launch one consolidator of another family (Codex by default) with `references/consolidate.md` filled. It verifies, clusters, and writes the consolidated file. Read only its top table `## 현재 계획에 남은 확정 결함` and its closing reply.
5. Hand the confirmed clusters to whoever owns the plan as findings to fix. PLAUSIBLE clusters are questions for the plan owner, not defects. REJECTED findings are dropped with the consolidator's cited line.

In a my-workflow run, the review directory is `<root>/artifacts/<P>-prv/` and the consolidated file is `<root>/artifacts/<P>-prv.md`, where `<P>` is the stage's artifact prefix (`N1` for feature-1-design).

## Limits

Agreement is not evidence. In the first trial all four blind reviewers raised the same finding (C05) and the verifier rejected it against the code; count a cluster by its verification, never by how many raised it.

Local-model severity is not used. The consolidator re-grades every finding.

A stale base produces false findings that verification does not catch. In the first trial the reviewers and the verifier all read the commit the work began on after the branch had been rebased, so a finding that called an existing table new (C01) was confirmed. Give every session the review base.

Precision varies by reviewer and is low enough that unverified findings must not reach the plan owner. First trial (#1303 r2, 2026-11-14, blind, one shared brief, no perspectives, `artifacts/blind-review-1/VERIFY-1.md`): CONFIRMED / findings per reviewer, against that stale base, were pi 9/17, pi 6/22, Hermes 4/15, Hermes 4/14, and the four together found 7 confirmed clusters that the Claude `rv` design review of the same document had not raised. Second trial (six pi reviewers, one perspective each, `artifacts/blind-review-2/CONSOLIDATED-1.md`): pending; update this paragraph from its numbers.
