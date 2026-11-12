---
name: rv
description: "Apply when the user asks for a review or calls /rv or $rv. Read all project rules and review procedures first and consult osiri and refactor together. The project decides the result's form, while this skill's mandatory judgment sections, including size and growth, and its blocking criteria always apply."
metadata:
  author: hrlee
  version: "2.10.1"
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

A review serves gatekeeping, accident prevention, maintaining norms, and education (Sadowski et al., "Modern Code Review: A Case Study at Google", ICSE-SEIP 2018). Gatekeeping covers the code health the change leaves behind, not only its behavior. Google's code review standard says "Nothing in this document justifies checking in CLs that definitely worsen the overall code health of the system." and its reviewer guide says "Most systems become complex through many small changes that add up, so it's important to prevent even small complexities in new changes." (https://google.github.io/eng-practices/review/reviewer/standard.html, https://google.github.io/eng-practices/review/reviewer/looking-for.html). A review that only hunts behavior defects lets the codebase grow without limit; the user's words (2026-11-12): "코드베이스가 무한정 늘어나기만 하면 안돼." For education, state with each simplification or design finding the alternative and the reason it is better.

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

Severities have these meanings, after the severity mapping of osiri `TECHNICAL_REVIEW_GUIDE.md`. BLOCKER and MAJOR block approval; MINOR and NIT do not.

1. BLOCKER: a supported path returns a wrong result, loses or corrupts data, fails to terminate or recover, or breaks a public contract; or a reachable security defect (U3).
2. MAJOR: a reachable correctness defect; a structure worse than a feasible alternative (U2); or a code-health defect the change introduces or grows: growth the problem does not require, a duplicate of an existing implementation in the repository, a hand-written version of what a known implementation already provides (U3), an unnecessary layer, wrapper, branch, or abstraction, code without callers, an old path left unretired, error handling that hides a failure or leaves its cause untraceable, or changed behavior with no test that fails on the defect.
3. MINOR: a bounded defect without a demonstrated wrong result or lasting code-health cost, such as an unenforced contract, a missing check, or a local naming fault.
4. NIT: a concrete low-cost correction with no behavior change.

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

4. Size and leftovers. These items fill the `크기와 증가` section of the result from tool output, not from estimates.
  4.1 Dimension table: for merge_base and head, count product lines, files, modules, classes, functions, public names and config keys, tests, and documents, with the difference per dimension. Count generated code, moved code, and deleted whole files separately so they neither inflate nor hide growth.
  4.2 New unit table: for each new file, class, function, public name, config key, query, schema object, and external dependency, write its caller, the reuse search run for it in the repository and in known implementations (U3), with what was searched and found, and why an existing implementation cannot serve, and the verdict: keep, merge into a named existing unit, or delete. A new unit without a caller or with a reusable existing implementation is a MAJOR finding.
  4.3 Proportion: judge whether the growth is what the problem defined in U0 requires, and list the deletion candidates the change could take with it, such as code it makes unnecessary. Growth the problem does not require is a MAJOR finding that names what to remove or reuse.
  4.4 Split: a change that bundles independent purposes is split by purpose, and size is only a secondary signal to look for a boundary. Google's guide says "100 lines is usually a reasonable size for a CL, and 1000 lines is usually too large, but it's up to the judgment of your reviewer." and "reviewers have discretion to reject your change outright for the sole reason of it being too large." (https://google.github.io/eng-practices/review/developer/small-cls.html). These numbers are reference points, not thresholds; a project may set its own. The author of a large change may have judged that it must land as one unit, so a split is judged in two steps and never requested on size alone.
  4.4.1 Boundary: each separate purpose of the change is a boundary, and mechanical refactoring such as moves and renames is a boundary of its own: "It's usually best to do refactorings in a separate CL from feature changes or bug fixes." Request a split only by naming a concrete boundary, the changes of the first part and why the system keeps working with only that part merged. The guide's criterion is "The system will continue to work well for its users and for the developers after the CL is checked in."
  4.4.2 Author's reason: read the PR body and responses for why the change is one unit, and judge that reason against the boundary. A reason holds when merging the first part alone breaks a working state, such as a schema, contract, or migration step that no released path can run, or when the size comes from deleting whole files or from an automatic refactoring tool the reviewers trust, which the guide lists as acceptable large changes. A boundary that holds against no valid reason is a MAJOR finding; a reason that holds closes it with the reason recorded. The guide says the belief that a change cannot be made small "is very rarely true", so "it belongs together" without naming the state that breaks is not a reason.
  4.4.3 Unsplittable change: request that mechanical and judgment changes sit in separate commits, judge in `설계와 원인` the coupling that forced many files to change together, and write in `검증 범위` any depth the size kept the review from reaching.
  4.5 Code without callers, unused config keys, queries, schema objects, and tests and documents of retired features remain, or the diff carries debug code, changes unrelated to its purpose, or misses files its change needs.
  4.6 Directory AGENTS.md, README, and design documents differ from the actual placement, names, and contracts.

5. Citing precedent
  5.1 Status of the grounds: if the grounds for a change are "기존 코드와 일치", "관례상", "원래 이렇게 한다", or "다른 모듈도 같다", collect the commits and PRs that created that precedent with `git log -S`, `git blame`, and `rg`, and if there are zero candidates, flag the claim itself. That the code is a certain way is not grounds that it should be.
  5.2 Primary grounds: for each precedent, confirm one of the issue body, design document, test that pins the intent, or user decision record that answered for that decision. Commit messages and review approvals are not grounds. Flag citing an ungrounded precedent as normative grounds, and have the norm newly backed by a document or issue.
  5.3 Repetition: if the same pattern repeats across several changes without grounds, do not read it as a repository standard. Write the repetition count and the commit list and report it as a defect candidate; a person decides whether to promote it to a standard.

## U2 Structure and quality judgment

Judge by reading only the change's entry points, public interfaces, data models, and design documents. If the verdict is that the structure is worse than an alternative, record that verdict first, and focus U3's detailed review on the parts that will not change.

Design decisions and defects are different axes. If a result violates the quality criteria it is a defect, and if its cause is a design decision it counts as a defect arising from the design. Do not exclude something from defects because it is the behavior the design intended.

Separately from the defect search, the review answers the following two questions with evidence. This judgment is not skipped: question 1 fills the `설계와 원인` section of the result and question 2 the `품질` section.

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

Check that the fix solves the cause directly and simplifies the structure. For every new unit, first search the repository for an existing implementation that can be reused, then search known implementations of the same problem outside it, in this order: the language's standard library, the project's existing dependencies, native features of the platforms the project already runs on (DB, framework, runtime), and established libraries, algorithms, and implementation patterns. Record each search in the new unit table (U1 4.2); a passing CI or an agent author does not exempt a change from it. The user's rule (2026-11-12) is "바퀴를 재발명하지 말것". Logic written by hand where a known implementation meets the requirement is a MAJOR finding that cites the official documentation URL of that implementation. When the alternative needs a new dependency, write its license, maintenance state, and deployment impact; it is MAJOR only when that cost is smaller than maintaining the hand-written version, and otherwise a non-blocking note. A dependency the change itself adds is judged the same way: whether it is needed, its known vulnerabilities from the ecosystem's audit tool or advisory database, its license, and its maintenance state. Judge whether it is the minimal sufficient change that preserves every caller contract and the error, retry, and regression paths. Even with few lines, hiding an exception or bypassing only a specific case is not a sufficient fix. Even if it works, flag unnecessary branches, duplication, wrappers, abstractions, and old paths not retired, with their concrete impact on maintenance, change, and verification and the direction of simplification.

Judge the implementation's cost at the input sizes the product handles, even when the result is correct and no DB is involved. Look for work that grows faster than the input, such as membership tests on a list or nested scans inside a loop where a dict, set, or one sort would do; whole data sets built in memory where a streaming pass would do; and the same lookup, parse, or call repeated where one batch call or a reuse of the earlier result would do. When data comes from a DB, filtering, aggregation, sorting, or joining it in application code follows item 2 of the DB section below, and conditions that cannot use an index follow item 3. An inefficiency finding states the call path, the input scale, the unnecessary work, and the cheaper alternative, and its severity follows the scale the product reaches; do not write a latency guess as a measurement.

Trace each failure path the change adds or touches: what happens when an external call, I/O, or parse fails, whether the failure reaches a caller or a log with enough context (input, target, cause) to find the cause in operation, and whether retries and fallbacks keep the contract. Error handling that swallows a failure, replaces it with a default, or drops its cause is a MAJOR finding.

Check security at every trust boundary the change touches: input from users, other services, files, and models is validated before it reaches logic; queries, commands, and paths are built with parameters or the platform's escaping, never by concatenating untrusted strings; secrets and credentials do not appear in code, config committed to the repository, logs, error messages, or responses; and authentication and authorization are checked at the boundary the project assigns to them, before internal logic runs. A reachable security defect is a BLOCKER.

Judge the tests as code. Each changed behavior needs a test that fails on the defective code; tests observe public behavior rather than internal names or private state; boundary and error paths are covered; fakes return the same shape as the real implementation. Tests that only pin internals, and test volume that grows without covering a new behavior, count as growth in U1 item 4.

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

Changed documents, PR descriptions, and comments are also review targets. A PR description states what changed and why, and links its issue. Do not reduce sucks to substituting banned words or checking example markers; read by section and paragraph. Judge whether the content is needed for the purpose, whether the reader's order of understanding and the topic and level of description are kept, whether terms are used before being introduced, and whether the causality between sentences holds.

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

Merge the findings of all units according to the finding schema, and assemble the markdown document according to the result format. Apply the sucks skill to the document, for both terminal output and external posting; sentence endings follow the project rules or the reference format. Assembling and the format check below apply even when posting is not allowed. Post or report in the conversation according to approval_scope, following `references/posting.md` when posting.

Before posting or handing the document over, run `uv run --no-project python ~/.agents/skills/rv/bin/check-review.py <review.md>` and fix the document until it prints `rv review format: 1 document(s) passed`. It rejects a document that lacks the verdict paragraph or a mandatory section, leaves a section empty, puts the sections out of order, ends on a section other than `검증 범위`, or has no table in `크기와 증가`. Exit code 1 is a format violation and 2 is a read failure.

The markdown document is the primary output. In Claude Code, if the ReportFindings tool exists, report the findings separately from the markdown document. Map to ReportFindings: file (the file path, with the line number split into the line field as an integer), summary (condition), failure_scenario (condition), and verdict. The judgment sections have no fields in the ReportFindings schema, so include them only in the markdown.

## Termination condition

End when the number of newly CONFIRMED findings in verification (U4) is 0. If there are CONFIRMED findings, perform the propagation check (U5), and if there are propagated findings, pass them to verification (U4) again. This cycle runs at most 2 rounds.

When the round cap is reached, mark unverified propagated findings as PLAUSIBLE and proceed to assembly (U6). Leave the unconfirmed scope as a list in the result document.

## Result format

The project decides the form: finding IDs, statuses, severity labels, sentence style, and sections added to the ones below. The review criteria are the union of the project's and rv's, and where both judge the same thing the stricter wins. A project severity scale does not lower an rv blocking class: map each rv BLOCKER and MAJOR onto a level the project treats as blocking. The mandatory sections below stay in every format, under these exact `##` headings and in this order. Write one judgment per line, and put the reproduction steps, scripts, execution output, and aggregate lists that support a judgment not in the body but in separate material. Attach separate material to a scratchpad directory or a PR comment thread.

1. Verdict: in two or three sentences of the first paragraph, write the verdict, the target head and merge-base, the number of findings and the count per severity, and the meaning of statuses and evidence kinds.

2. Index: if findings span two or more areas or it is a follow-up review, include a table of section, scope, severity, status, and latest comment / next actor.

3. Judgment sections: one `##` section per judgment, in the order below. Each holds short sentences or tables, one judgment per line, and a judgment that does not apply is written as `해당 없음: <이유>`. Record defects in the finding list and point to them by R-ID. A follow-up review keeps every section for the current head; a section whose judgment did not change says so in one line with the earlier review link, but `크기와 증가` is always remeasured.
  3.1 `## 설계와 원인`: U2 question 1. Whether the change removes the cause or bypasses the symptom, the alternative structure compared in one sentence, and which is better.
  3.2 `## 기능과 완료 기준`: whether the change does what the issue's completion criteria and the PR's claims say for the code's users, whether it adds functionality nobody asked for, and the failure path and security judgments of U3.
  3.3 `## 크기와 증가`: U1 item 4. The dimension table, the new unit table, deletion candidates, and the split judgment.
  3.4 `## 품질`: U2 question 2. Where the implementation, prompts, queries, and documents fall short of the ceiling the structure allows, including complexity a simpler implementation would remove and the implementation cost judged in U3, and every metric against the baseline or the measurement gap. Size and reuse belong to `크기와 증가`, tests to `시험`, and failure paths and security to `기능과 완료 기준`.
  3.5 `## 시험`: the test judgment of U3, and the CI state of the reviewed head: each failing or pending required check with its job and cause. A failure the change causes is a finding.
  3.6 `## 이름과 문서`: U1 items 3 and 4.6 and the document review of U3.

4. Findings: under a `##` section per review area, write one finding as one `-` item.
  4.1 The format is `R-001 심각도, 근거 구분: 문제. 위치. 조치.`, where 근거 구분 is the project classification or 재현, 관찰, 추론.
  4.2 The problem states the occurrence condition and result in one sentence, with numbers short in parentheses.
  4.3 The location is only the target head's `file:line`, and the action is one sentence that also names the problem it solves, so the author can weigh it and the same mistake does not recur.
  4.4 If an item exceeds three sentences, split the finding or trim the evidence.
  4.5 Mark the verdict on BLOCKER and MAJOR findings.

5. Human review recommendation: if there is a DB schema change, write the change target and the risks a person should check in a `## 사람 리뷰 권고` section after the findings. It is not counted among defects, and do not presume whether the reviewer approves.

6. `## 확인하고 배제한 항목`: the risks checked and cleared in U3 step 4, each with the reason it is fine and how far its safety fact was proven.

7. `## 검증 범위`: the last section. Write in one or two sentences the verification run with pass and fail counts, the verification not run, and the unconfirmed scope. Only HTML comment lines, such as a machine-read verdict marker, may follow it.

Request changes when an unresolved BLOCKER or MAJOR finding remains or the structure is worse than an alternative. Approve when no blocking finding remains, the change meets the issue's completion criteria, and it does not worsen the code health of the codebase it leaves behind; Google's standard is that reviewers "should favor approving a CL once it is in a state where it definitely improves the overall code health of the system being worked on, even if the CL isn't perfect." (https://google.github.io/eng-practices/review/reviewer/standard.html). MINOR and NIT findings do not block approval, and the review labels them as non-blocking. The review proceeds while CI fails, but a head whose required checks fail or are still pending is not approved; a CI pass is a precondition of approval, never its ground, and a change that works or passes CI is not approved when it worsens code health. If a core verification gap prevents judgment, the verdict is withheld.

A follow-up review preserves existing IDs and opinions, records responses as `A-001` and rechecks as `R-001-C`. Statuses are OPEN, ANSWERED, RECHECK, RESOLVED, SKIP, and a status changes to RESOLVED only after the fix and evidence are confirmed. Write the reason on SKIP.

## Criticism of the review

When you receive a criticism of the review output itself (verdict errors, format, insufficient evidence, etc.), confirm the code and records the criticism relies on from primary sources, then accept it or reject it with grounds, and if accepted, correct that review and reply. If the cause lies in rv's procedure or format, fix rv so the same defect does not recur. Fixing rv follows the my-harness modification procedure of the `harness` skill and the propagation of my-skills.

## Posting and per-agent execution

Posting rules, including the PR author mention, rechecks before posting, anti-slop checks, and the choice among COMMENT, REQUEST_CHANGES, and APPROVE, are in `references/posting.md`; read it before any posting. Reviewer assignment and how Claude Code and Codex map the units to workers are in `references/agents.md`; read it before splitting the review across workers.

## Project-specific settings

This section is settings applied to a specific repository. In other repositories, replace it with that repository's rules.

enterprise-memory repository:

1. Review procedure: follow `docs/REVIEWING.md`. A finding's evidence_class is 재현, 관찰, or 추론, as the review document format of REVIEWING.md prescribes. The six classes of REVIEWING.md (Observed, Measured, Derived, Sourced, Inferred, Hypothesized) classify the atomic claims of the PR body, CHANGELOG, and API.md, not findings.
2. anti-slop rules: read `rules/rules.yaml` and `rules/vocabulary/ko.yaml` of `graphai-repository/anti-slop` with `gh api` and replace detected vocabulary with alternatives.
3. Reference format: the review of PR #1208, `pullrequestreview-5646450494`.
