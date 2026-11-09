---
name: rv
description: "Apply when the user asks for a review or calls /rv or $rv. Read all project rules and review procedures first and consult osiri and refactor together. Prefer the project's result format; if there is none, follow this skill's format."
metadata:
  author: hrlee
  version: "2.4.1"
  domain: workflow
  triggers: 리뷰, review, rv, 코드 리뷰
  dependencies:
    - osiri
    - refactor
    - sucks
---

# rv

Apply this procedure when the user asks for a review or calls `/rv` or `$rv`. The agent first reads all project rules closely and consults the project review rules, `osiri`, and `refactor` together. Consulting `osiri` happens inside this review procedure that the user allowed, and `teqr` is not applied without a direct call. The result format prefers the project rules.

Assume defects exist and find every defect in the review scope. Look for inputs and execution orders that refute the behavior and completion claims, and when you find a defect, trace the paths along which the same cause propagates. Prove each finding with its occurrence condition and a reachable execution path.

This skill is divided into seven units (U0-U6). A single agent runs them in sequence, or an agent that distributes work starts workers per unit. The agent that distributes work is called the coordinator. Each unit has defined inputs and outputs, so it can run independently. Sections are ordered from the cheapest review onward.

## Input contract

Values the caller provides. If a required value is missing, stop and report. Do not ask the caller questions during the run.

| Item | Description | Required |
|---|---|---|
| repo | Repository path or GitHub URL | yes |
| target | PR number, branch name, list of file paths, or description of the comparison target | yes |
| head | Commit SHA under review (for git targets) | conditional |
| merge_base | Comparison base commit SHA (for git targets) | conditional |
| prior_ids | List of R-IDs from previous reviews (empty for a first review) | yes |
| approval_scope | Whether posting, editing, DB runs, model runs, and benchmark runs are each allowed | no |
| rule_paths | List of project rule file paths | no |
| expert_hints | Mapping hints of expert types per area | no |

head and merge_base are required when the target produces a git diff, such as a PR, branch, or file paths. They are unnecessary for targets without a diff, such as skill comparisons or document reviews.

The default of approval_scope is to disallow everything. If posting is not allowed, report the result only in the conversation.

When the user calls `/rv` directly, the agent fills head, merge_base, and target automatically from the current repository and branch. prior_ids are collected from existing review comments.

Without a checkout, read files, diffs, and metadata pinned to the head SHA through the connected repository tools (GitHub API, gh CLI).

When several agents fetch in one repository they overwrite each other's `FETCH_HEAD`, so take the review target by SHA or with `git fetch origin <branch>:refs/review/<name>`. Write the commit SHA actually reviewed at the top of the result document.

## Finding schema

One row is one finding.

| Field | Value | Description |
|---|---|---|
| id | R-nnn | Sequence number within the section |
| severity | BLOCKER, MAJOR, MINOR, NIT | Severity |
| evidence_class | Project classification, or 재현, 관찰, 추론 | Kind of evidence |
| condition | Sentence | Occurrence condition and result |
| file | file:line | Location in head |
| action | Sentence | Action |
| propagation | List of file paths or "확인 완료" | Locations where the same cause propagates |
| verdict | CONFIRMED, PLAUSIBLE, REJECTED | U4 verification result (BLOCKER and MAJOR only) |

Use the project's classification for evidence_class if it has one. Otherwise use three classes by default, written in Korean in the result: 재현 (confirmed by running or measuring), 관찰 (confirmed directly in code or documents), 추론 (inferred from evidence, or an unverified hypothesis).

For MINOR and NIT findings, the agent that produced them sets the verdict to CONFIRMED or PLAUSIBLE by self-verification.

## Unit structure

```
U0 prepare ─→ U1 codebase review ─→ U3 detailed review ─→ U4 verify ─→ U5 propagation check ─→ U6 assemble and post
                 ↘                      ↗
              U2 structure and quality judgment
```

U1 and U2 can run in parallel. U3 can be split per changed area and run in parallel. U4 is performed by an agent other than the one that produced the finding.

### Inputs and outputs between units

| Unit | Input | Output |
|---|---|---|
| U0 | The whole input contract | Review scope, recheck results, reference rules, identification of entry points, public interfaces, and data models, proposed split per area |
| U1 | U0's review scope and reference rules | findings, target file paths for U3 |
| U2 | U0's review scope, entry points, public interfaces and data models | Structure verdict, quality verdict, findings |
| U3 | U0's review scope and rules, U1's target file paths, U2's structure verdict | findings |
| U4 | The finding lists of U1-U3 | A verdict for each finding |
| U5 | findings that are CONFIRMED or PLAUSIBLE in U4 | Propagation findings |
| U6 | The outputs of all units, approval_scope | Review document |

## U0 Prepare

Check the target head, the comparison base, and uncommitted changes. Read all project rules and reference rules closely and match their application paths. Consult the relevant osiri guide and refactor together.

Compare existing reviews, responses, and user decisions and verification results against the current code. Recheck each finding in prior_ids down to its occurrence condition and related call paths, and when a verdict changes, leave the new evidence and reason. Confirm that a user decision used as grounds for a finding has not been cancelled or replaced by later instructions.

In a follow-up review, even at the same head, read new responses, questions, rebuttals, and body changes and decide whether to respond. The head record exists to prevent duplicate posting of the same full review and is not grounds for skipping a follow-up review. Link existing R-IDs and review links and report only the changed evidence and checked scope; record the ID and time of the last checked comment or review, body changes, and whether it was answered, so you do not answer the same request twice. Do not treat a notification that duplicates your own review as a new request.

GitHub's requested_reviewers is the list of pending requests. Do not infer the withdrawal of an existing request or the end of follow-up work solely from removal from the list after a review is submitted. Confirm explicit cancellation, reassignment, and PR closing from the latest conversation and state.

Review from the problem-modeling perspective: confirm that the input and output definitions of the problem the change solves, its boundary cases, constraints, and accuracy and cost metrics match the real cases.

Review from the ds perspective: confirm that responsibilities, state ownership, and contracts are consistent across all callers and implementations, and whether there is an alternative simpler than the current structure.

If only a review was requested, do not make a new problem definition or design document, code edits, or test runs preconditions. Do not conclude a bug from a difference with a pattern or a lack of measurement alone.

Identify the change's entry points, public interfaces, and data models. Check the list of changed files with `git diff --stat`, and split areas by the nature of the change (DB, prompts, concurrency, Python structure, etc.). Propose an expert type mapping.

## U1 Codebase review

This step ends with structural information only, before reading file bodies. Confirm lists, names, import relationships, and size with tool output (`git diff --stat`, `git ls-files`, search, import contracts, LSP references), and open only suspicious files.

Separately from code content, review the shape of the codebase the change leaves behind. The scope is not the diff lines but the packages the change touched and their neighbors, and even problems that existed before the change are flagged if the change relies on or grows them. The types below are flagged as defects regardless of behavior and whether checks pass, and each finding states the responsibility placement that causes it and the location to move to or the name to change.

1. Import relationships and `__init__.py`
  1.1 Layer inversion: a lower layer imports an upper layer (by the project's layer rules and import contracts).
  1.2 Public path bypass: importing an internal module directly instead of the path the package exposes.
  1.3 `__init__.py` anomalies: unjustified re-exports of internal implementation, several import paths for the same symbol, unused public names, heavy loading or side effects at import time, names not symmetric with submodules.
  1.4 Private name access: importing another module's `_name`, or tests asserting internals.
  1.5 Traces of cycle avoidance: imports inside functions, `TYPE_CHECKING` hiding, or lazy imports used to avoid cycles.
  1.6 Check bypass: covering boundary violations with ignore lines in import contracts or `noqa`.
  1.7 Duplicate owners: several packages define one concept and import each other.

2. Directory structure
  2.1 Placement: one concept scattered across several directories, or one directory mixing unrelated concepts. Breaking the project placement rule that external interfaces are per resource and the internal core is per feature. Top-level directories exposing implementation layers or query types instead of features.
  2.2 Splits and shells: files and directories with almost no content, modules that only pass other modules through, small file splits used in only one place.
  2.3 Placement of tests, fakes, and fixtures does not correspond to the placement of product code.

3. File, module, and identifier names
  3.1 Mismatch between name and content: a name does not point to the responsibility it holds, the same concept has different names in different places, or paired modules (e.g. a prompt module and the module that uses it) are not named symmetrically.
  3.2 Name quality: words absent from the domain and code, catch-all names (`utils`, `helpers`, `common`, `misc` and the like), singular or plural not matching the target, violations of the project naming rules (checkers, AGENTS.md, existing layout on main).
  3.3 Leftovers of moves and renames: old names remain in documents, tests, patch targets, serialization keys, and settings.

4. Size and leftovers
  4.1 Compare the number of files, lines, modules, classes, and functions before and after the change, and flag parts that grew relative to solving the problem.
  4.2 Code without callers, unused config keys, queries, schema objects, and tests and documents of retired features remain.
  4.3 Directory AGENTS.md, README, and design documents differ from the actual placement, names, and contracts.

5. Citing precedent
  5.1 Status of the grounds: if the grounds for a change are "기존 코드와 일치", "관례상", "원래 이렇게 한다", or "다른 모듈도 같다", collect the commits and PRs that created that precedent with `git log -S`, `git blame`, and `rg`, and if there are zero candidates, flag the claim itself. That the code is a certain way is not grounds that it should be.
  5.2 Primary grounds: for each precedent, confirm one of the issue body, design document, test that pins the intent, or user decision record that answered for that decision. Commit messages and review approvals are not grounds. Flag citing an ungrounded precedent as normative grounds, and have the norm newly backed by a document or issue.
  5.3 Repetition: if the same pattern repeats across several changes without grounds, do not read it as a repository standard. Write the repetition count and the commit list and report it as a defect candidate; a person decides whether to promote it to a standard.

## U2 Structure and quality judgment

Judge by reading only the change's entry points, public interfaces, data models, and design documents. If the verdict is that the structure is worse than an alternative, record that verdict first, and focus U3's detailed review on the parts that will not change.

Design decisions and defects are different axes. If a result violates the quality criteria it is a defect, and if its cause is a design decision it counts as a defect arising from the design. Do not exclude something from defects because it is the behavior the design intended.

Separately from the defect search, the review answers the following two questions with evidence. This judgment is not skipped and stays in its own section of the result document.

1. Is this structure the most suitable structure that actually solves the problem logically?
  1.1 Restate the problem being solved at the level of its cause, and judge whether the change removes that cause or only bypasses the symptom.
  1.2 Build at least one feasible alternative structure based on data flow, state ownership, responsibility placement, stage splitting, and call cost (DB round trips, model calls), compare it with the current structure, and judge which is better in correctness, performance, and simplicity.
  1.3 If the current structure is worse than the alternative, flag it as a structural defect. Flag it even if the behavior is correct.

2. Has it reached the highest quality possible within that structure?
  2.1 Find where the implementation, prompts, queries, tests, and documents lose relative to the ceiling the structure allows.
  2.2 If there are measurements, compare every metric against the baseline (main etc.), and flag worsened metrics with their causes. If there are none, record it as a measurement gap.
  2.3 Distinguish whether the remaining gap is a limit of the structure or a shortfall of the implementation. Record a structural limit under verdict 1, and an implementation shortfall as a defect.

A quality gap the user explicitly agreed to as follow-up scope is classified as follow-up scope, not a defect, but both verdicts are still performed and recorded.

## U3 Detailed review

The most expensive step, reading bodies along the file paths the previous steps narrowed down. If U2's structure verdict concluded it is worse than an alternative, focus on the parts that will not change. It can be split per changed area and run in parallel. When splitting, map an expert type suited to the area (sql-expert, llm-expert, parallel-expert, python-expert).

Read all related files with their callers, backends, and fakes, and trace input → state ownership → write → failure → recovery. Aggressively verify that contracts and resource cleanup hold under partial completion, failure during recovery, retries, and concurrent execution and cancellation. Find counterexamples that the defensive logic and tests miss.

Find what the change breaks beyond the diff.

1. Find the one fact the change is safe because of. Most changes that look risky are safe because of a single fact, such as "this call only drops cache entries that are already dead". State it, and if it holds, most risky cases clear at once. Spend the effort here rather than on a long list of maybes.
2. Look where symbol search stops: the source of the library the code calls at its pinned version and any local patch, when things run (callbacks, teardown, transaction commit), and consumers a reference search misses, such as serialized JSON, a DB column, a wire format, another language reading the same bytes, a feature flag, and code several hops downstream.
3. Prove the one fact by running real code when it is cheap: a small script or test that calls the exact function and fails loudly if the fact is wrong. Record how far each safety fact got: asserted, pointed at a `file:line`, walked step by step to show the bad case cannot be reached, run, or reproduced in the running app. If it was not proven, say it is unproven.
4. Keep confirmed risks as findings, and list separately what you checked and cleared, with the reason it is fine, so the reader can see the scope covered.

Check that the fix solves the cause directly and simplifies the structure. First check whether an existing implementation can be reused, and judge whether it is the minimal sufficient change that preserves every caller contract and the error, retry, and regression paths. Even with few lines, hiding an exception or bypassing only a specific case is not a sufficient fix. Even if it works, flag unnecessary branches, duplication, wrappers, abstractions, and old paths not retired, with their concrete impact on maintenance, change, and verification and the direction of simplification.

Compare quality, performance, and completion claims with actual results. For verification, check the SHA, input, environment, scope, and latest run results. Do not extend a CI pass into a guarantee of the correctness or quality of other paths. Distinguish defects, verification gaps, and explicitly agreed follow-up scope.

Check the core paths, existing unresolved findings, and required verification to the end. Leave the scope you could not confirm, and do not assert that every defect was found. Edits and external posting, DB, model, and benchmark runs follow approval_scope.

### DB schema and usage

For changes that touch the DB, read the queries together with their callers, and review whether the existing implementation and the DB's own features could satisfy the same contract at lower cost. Do not exclude inefficiency from the review because the result is correct or CI passes.

1. Always recommend human review for DB schema changes, regardless of size and automatic check results. This includes table, column, type, constraint, index, and data model changes, and they are not excluded because there is no migration file. Report, along with the change target, the risks a person should check among data compatibility, migration and backfill, locking, deployment order, and rollback. Do not mistake the recommendation itself for a defect or a GitHub required-approval setting.
2. Trace call counts and data movement. Check N+1, duplicate lookups, per-row writes, excessive lookup ranges, and filtering, aggregation, sorting, and pagination done in the application, and compare with feasible alternatives such as batching, set operations, and in-DB processing. Also check that reducing call counts does not cause unbounded results or excessive memory use.
3. Compare the conditions, joins, and sorts a query uses with the schema and indexes. Review scans depending on input size and selectivity, unnecessary sorts, conditions that cannot use an index, and the write cost of duplicate indexes. If there are existing execution plans and measurements, check them together with the target data size.
4. Review the effect of transaction boundaries, lock scope, connection and cursor lifetimes, concurrent execution, and retries on cost and consistency. When proposing alternatives, preserve order, duplicates, NULLs, isolation level, and the return contracts of every backend and fake.

A DB inefficiency finding states the call path, the occurrence condition and scale, the unnecessary work, and the alternative. Do not ignore increases in round trips and processing that code can confirm because there is no measurement, but do not write guesses about actual latency or execution plans as measurement results. Do not confirm a defect from mere taste or the presence of an index alone; set severity by impact and evidence. DB runs, EXPLAIN ANALYZE, and benchmarks needed for confirmation follow approval_scope, and items that could not be run remain as verification gaps.

### Meaning and organization of documents

Changed documents, PR descriptions, and comments are also review targets. Do not reduce sucks to substituting banned words or checking example markers; read by section and paragraph. Judge whether the content is needed for the purpose, whether the reader's order of understanding and the topic and level of description are kept, whether terms are used before being introduced, and whether the causality between sentences holds.

For examples, first judge whether they are needed. A needed example connects naturally to the preceding explanation and makes clear what it explains. Check against the source whether an ID, address, path, or setting value is an example or an actual default, constant, or convention, and if it is an example, confirm what it must be replaced with in real use. Also check the role of values, such as a value that selects the current target versus a target value to change, against the call contract. Do not arbitrarily turn actual defaults into examples, and do not force the same order of explanation and '예를 들어' on every document.

A document finding states the concrete original text and the misunderstanding the reader will have. Do not treat passing anti-slop as meeting document quality, and do not extend review authority into authority to edit the original.

## U4 Verify

An agent other than the one that produced a BLOCKER or MAJOR finding verifies it independently. In parallel runs, the verifier is a new agent that receives only the finding and the head SHA (a fresh agent, not a fork). In a single-agent run, recheck by tracing again the execution path where the finding's condition holds, from an entry point different from the one at production time.

### Verification session specification

Verify findings each time in an empty session that does not know the context. An empty session is one that did not receive: the finding producer's conversation history, the producer's conclusions and plans, previous verification results, or other areas' outputs. Put only the finding, the head SHA, and the verdict criteria below in the brief. If verification needs the context, that is a brief defect, so do not verify; report it as a defect.

If the finding producer's session and the verification session are the same, it does not count as verification. A path where one confirms the defect one found oneself is not independent verification even if it leaves evidence.

The verifier reproduces or refutes the finding's condition in the actual code.

| verdict | Criterion |
|---|---|
| CONFIRMED | Confirmed that the execution path from the occurrence condition reaches the defect |
| PLAUSIBLE | The execution path exists, but the occurrence condition could not be confirmed by running |
| REJECTED | Confirmed that the occurrence condition is unreachable or defensive logic blocks it |

A REJECTED finding is excluded from the result document in a first review. In a follow-up review, if a previous R-ID is REJECTED, change its status to SKIP and write the reason.

For a finding to claim the 재현 evidence_class, it must be confirmed by running or measuring. A judgment made by reading code is 관찰, and one inferred from evidence is 추론.

## U5 Propagation check

Search whether the cause of a confirmed defect also exists in other locations in the same pattern. The target is the whole repository.

1. Extract the cause of the defect (a wrong pattern, a missing check, a wrong assumption).
2. Find other locations where that cause appears by search (grep, LSP references, import tracing).
3. At each location found, confirm whether the same defect occurs.
4. Record a propagated defect as a new finding that references the original finding's id.

If the same wrong pattern repeats across several locations or changes, write the repetition count in the propagation finding. Repetition is not a standard, and the fact of repetition does not justify existing behavior. If there are three or more repetitions without primary grounds, leave a standardization candidate separate from the individual fix findings.

## U6 Assemble and post

Merge the findings of all units according to the finding schema, and assemble the markdown document according to the result format. Apply the sucks skill. Post or report in the conversation according to approval_scope.

The markdown document is the primary output. In Claude Code, if the ReportFindings tool exists, report the findings separately from the markdown document. Map to ReportFindings: file (the file path, with the line number split into the line field as an integer), summary (condition), failure_scenario (condition), and verdict. The grounds for verdicts and the structure and quality judgment have no fields in the ReportFindings schema, so include them only in the markdown.

## Termination condition

End when the number of newly CONFIRMED findings in verification (U4) is 0. If there are CONFIRMED findings, perform the propagation check (U5), and if there are propagated findings, pass them to verification (U4) again. This cycle runs at most 2 rounds.

When the round cap is reached, mark unverified propagated findings as PLAUSIBLE and proceed to assembly (U6). Leave the unconfirmed scope as a list in the result document.

## Result format

Prefer the project's format, severity, and status system; if there is none, follow the format below. Write one judgment per line, and put the reproduction steps, scripts, execution output, and aggregate lists that support a judgment not in the body but in separate material. Attach separate material to a scratchpad directory or a PR comment thread.

1. Verdict: in two or three sentences of the first paragraph, write the verdict, the target head and merge-base, the number of findings and the count per severity, and the meaning of statuses and evidence kinds.

2. Index: if findings span two or more areas or it is a follow-up review, include a table of section, scope, severity, status, and latest comment / next actor.

3. Grounds for the verdict: write the answers to the four codebase-review items and the two structure and quality questions in one section of three or four sentences. Write the alternative structure compared in one sentence, and record defects in the finding list.

4. Findings: under a `###` section per review area, write one finding as one `-` item.
  4.1 The format is `R-001 심각도, 근거 구분: 문제. 위치. 조치.`, where 근거 구분 is the project classification or 재현, 관찰, 추론.
  4.2 The problem states the occurrence condition and result in one sentence, with numbers short in parentheses.
  4.3 The location is only the target head's `file:line`, and the action is one sentence.
  4.4 If an item exceeds three sentences, split the finding or trim the evidence.
  4.5 Mark the verdict on BLOCKER and MAJOR findings.

5. Verification scope: in the last `###` section, write in one or two sentences the verification run with pass and fail counts, the verification not run, and the unconfirmed scope.

6. Human review recommendation: if there is a DB schema change, write the change target and the risks a person should check as a separate item. It is not counted among defects, and do not presume whether the reviewer approves.

The default severities are BLOCKER, MAJOR, MINOR, NIT. Unresolved BLOCKER or MAJOR findings and a verdict that the structure is worse than an alternative mean request changes; if a core verification gap prevents judgment, the verdict is withheld.

A follow-up review preserves existing IDs and opinions, records responses as `A-001` and rechecks as `R-001-C`. Statuses are OPEN, ANSWERED, RECHECK, RESOLVED, SKIP, and a status changes to RESOLVED only after the fix and evidence are confirmed. Write the reason on SKIP.

## Posting rules

Apply the sucks skill to the result document before writing it, for both terminal output and external posting. Sentence endings follow the project rules or the reference format.

The procedure for posting as a PR review or comment is as follows. Post and edit only within the scope allowed by approval_scope.

1. Mention the PR author (the login from `gh pr view --json author`) as `@login` in the first sentence of the result document. The same for follow-up reviews.

2. Before posting, recheck the latest head and PR state, the applicable target conditions, CI and conflict conditions, and new reviews and comments. If the head changed, do not post stale results. If there is a review with a different verdict on the same head, do not post; report the conflicting evidence.

3. Outside code spans, `~` becomes strikethrough on GitHub, so write ranges with a hyphen, as in `R-001-R-006`.

4. If the repository has an anti-slop check, read the latest rules and vocabulary through the connected repository tools and compare the draft. Clean up vocabulary and unnecessary phrases without changing technical meaning, severity, evidence, or verification limits. Do not download or run executables.

5. After posting or editing, wait until all anti-slop runs finish, and check the section for your own comment id in the bot thread comment. If there is no section, there are 0 detections. If there are detections, edit the same comment and check again.

6. Do not fix detections from other authors' comments and changed files; report them.

7. Distinguish GitHub Conversation comments from formal PR Review COMMENT, REQUEST_CHANGES, and APPROVE. Choose the action that fits the allowed posting scope and the repository's verdict criteria, and distinguish confirmed findings that need fixes from non-blocking explanations and questions. Do not submit REQUEST_CHANGES on taste or on presumptions without sufficient grounds. Submit APPROVE only when the approval authority and the needed user confirmation are met. After submitting, re-query the actual review state and commit, and report self-PR review limits and remaining verification conditions as they are. Do not report a general comment as a formal review or completed approval.

## Criticism of the review

When you receive a criticism of the review output itself (verdict errors, format, insufficient evidence, etc.), confirm the code and records the criticism relies on from primary sources, then accept it or reject it with grounds, and if accepted, correct that review and reply. If the cause lies in rv's procedure or format, fix rv so the same defect does not recur. Fixing rv follows the my-harness modification procedure of the `harness` skill and the propagation of my-skills.

## Per-agent execution

This presents how each agent maps rv's unit structure. rv does not force an execution method. The agent's delegation rules (AGENTS.md etc.) take precedence over this section.

### Reviewer assignment

A review presumes that one does not judge one's own work, so choose reviewers and verifiers from a model family different from the producer's. Codex takes independent review from a different model family, Claude takes perspective-specific expert review, and pi and Hermes have no review role (pi takes narrow edits whose location and method are fixed, Hermes takes research, documents, and operations). If one family cannot be launched because of limits or outages, write that fact and the remaining verification gap in the result document, and replace it with a worker of another family under the same conditions or ask the caller. Do not fill the review count by sending in agents outside their role.

Submit APPROVE, REQUEST_CHANGES, or COMMENT according to the verdict, but GitHub does not let a PR author approve their own PR, so on your own PR post a verdict equivalent to APPROVE as COMMENT. This record does not meet the approval requirement, and the merge state stays `REVIEW_REQUIRED`. If approval is needed, report that another person's approval or the repository admin's ruleset judgment is needed, and do not create an approval with another account.

### Claude Code

The coordinator starts subagents with the Agent tool. Whether the coordinator edits code directly or only delegates to workers follows the project's delegation rules.

| Unit | Execution |
|---|---|
| U0 | Run by the coordinator |
| U1, U2 | Parallel Agent forks |
| U3 | Agent per area, with expert type specified |
| U4 | Verified by a fresh Agent (not a fork) different from U3 |
| U5 | Agent |
| U6 | The coordinator assembles the markdown document |

### Codex

Codex runs the independent review unit assigned to it. When split execution is needed, the orchestrator starts workers with Paseo `create_agent` according to the shared division-of-labor criteria, and gives one worker only one unit. A delegated Codex worker does not re-delegate without explicit permission.

| Unit | Execution |
|---|---|
| U0 | Run by the coordinator |
| U1-U2 | Review worker |
| U3 | Worker per area |
| U4 | Verification worker different from U3 |
| U5 | Propagation check worker |
| U6 | The coordinator assembles and posts the markdown document |

A worker brief includes every value of the input contract, past rejection types, a self-check script, a prohibition on side work, and the report scope.

## Project-specific settings

This section is settings applied to a specific repository. In other repositories, replace it with that repository's rules.

enterprise-memory repository:

1. Review procedure: follow `docs/REVIEWING.md`. evidence_class uses the six classes of REVIEWING.md as they are (Observed, Measured, Derived, Sourced, Inferred, Hypothesized).
2. anti-slop rules: read `rules/rules.yaml` and `rules/vocabulary/ko.yaml` of `graphai-repository/anti-slop` with `gh api` and replace detected vocabulary with alternatives.
3. Reference format: the review of PR #1208, `pullrequestreview-5646450494`.
