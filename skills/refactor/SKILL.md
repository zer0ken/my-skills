---
name: refactor
description: "Refactoring procedure that reduces a codebase to a manageable size while preserving function and performance. Use for planning and executing refactors, destructive refactors, cleaning up excessive splitting of code, files, and layers, and auditing a repository's safeguards against refactoring requirements; also use when writing or fixing repository checkers and safeguards. Do not apply to simple feature additions or to investigating bugs whose cause is not confirmed."
metadata:
  author: hrlee
  version: "1.1.1"
  domain: engineering
---

# Refactor

These are working instructions for reducing the size and comprehension cost of the implementation while preserving the product's contracts. The goal is to remove code and structure unnecessary for the functionality so maintainers can predict the impact of changes.

## Work scope

Distinguish the work mode from the request.

| Mode | Allowed scope | Result |
| --- | --- | --- |
| Plan | Investigating code and contracts | Priorities, expected structure, impact, verification criteria |
| Execute | Implementation changes within the approved scope | Cleaned-up implementation and evidence that behavior and performance are preserved |
| Safeguard audit | Comparing requirements with current checks, tests, and CI | Whether each is met, the evidence, and missing safeguards |

Do not modify the product or CI on an audit request alone. Do not expand a general refactoring request into a rewrite of the whole codebase. When a destructive refactor is approved, do not treat the internal structure as a condition to keep; redesign within the needed scope. Make lower-level implementation decisions within the approved goal yourself, and confirm only at boundaries that need authority, such as contract changes or data loss.

## Baseline and preserved contracts

Confirm that the current working directory is the actual target branch. Record the commit under review and the modification state of the working tree, and fix the comparison target to the release or refactoring start commit the user specified. Separate other workers' changes with a separate checkout or similar.

Separate the contracts to preserve from the internal implementation to change. Investigate only the items that apply to the product.

| Preserved | Evidence to check |
| --- | --- |
| Public behavior | Inputs, responses, errors, settings, and deployment interfaces of APIs, CLIs, and MCP |
| Stored data | Schema, migrations, identifiers, integrity, transaction semantics |
| Computed results | Search scores and order, filters, time conditions, equivalence across backends |
| Operational behavior | Loading, cancel and resume, recovery, concurrent execution, and resource cleanup |
| Performance | Latency, throughput, DB round trips, and resource use for the same work |

The change scope allowed by the current instruction takes precedence. Do not carry a schema freeze or an allowance for index changes from earlier work into another project as a permanent rule. Also check whether differences between existing backends are intended contracts or defects, and keep defects found separate from the results of the refactor.

Record the size of the baseline tree and the product code. Count product, test, and evaluation tooling separately, and do not inflate the reduction with generated or moved code.

## Priorities and design

Within the approved scope, choose first the unit that removes the most unnecessary complexity and code volume. Do not postpone a redesign of a large storage layer or feature implementation with small wrapper cleanups. Proceed in units whose preserved contracts can be verified.

- Review not only line counts but file count, class count, abstraction, and the breadth and depth of directories together. Do not pile responsibilities into one file for the sake of a smaller total.
- Do not judge that code shrank by abbreviating names and conventions or putting several statements on one line. Apply SOLID to reduce the impact of change, and do not create unnecessary interfaces and files in the name of principles.
- Directories must reveal the product's features and responsibilities. Do not force one project's feature names on another product. Use shared directories for responsibilities several features actually share.
- One concept is owned in one place, or each implementation owns it deliberately. A caller must be able to explain which of the two it is. If the cost of sharing exceeds the duplication, keep separate implementations.
- Backends share common contracts and judgments but do not force differences in storage into the same query. Use the expressiveness of SQL and DB operations, and reduce unnecessary relay code and round trips. Check scores, ordering, atomicity, and recovery semantics together.
- Auxiliary modules managed together with their consumers, such as prompts, keep their name and location correspondence. Clean up private markers and public re-exports by the same standard.
- Measure maintainability as the work a reader must do, on two independent axes: layers to trace between a question and its answer, and hidden or mutable state the reader must hold. Collapse wrappers with one caller, adapters with no second implementation, and pass-through layers that repeat the same methods and arguments. Prefer interfaces that hide meaningful decisions. Shrink state scope (returns over mutation, locals over fields, fields over module state, module state over globals; derive instead of syncing). Name an invariant once at the boundary instead of in every consumer. The test: a new reader can answer "where does X come from?" and "what can change X?" in under 30 seconds.
- Subtract before you add. Remove dead code, redundant validators, and stub references first, then build the new structure on the simpler base.
- When an internal API is replaced, migrate every caller and delete the old API in the same change instead of keeping a compatibility layer. This applies only when no external user depends on the old API; changing a public contract still follows the approval rules.

Start reducing from large units, but do not do only the large ones; stop only when a sweep of the whole finds nothing left to delete. A reviewer's "큰 것은 남지 않았다" is not a signal to stop. Sort the queue not by arrival order but by the amount deleted (including what the item unlocks), and start the target from the lower bound the contract requires so that everything above it must give a reason to exist. Do not accept a worker's or planner's "이것이 최소" as evidence; ask what the next deletion is. Progress reports show every dimension against the base commit: product lines, files, classes, functions, tests, harness, scripts, and documents, with "최초 N줄, 지금 M줄, 차이 D줄" first.

Before removing the outer layer of a duplicated defense, distinguish "the outer layer filters every result" from "the inner layer already blocks every path". Make a list of input paths (channels, branches), confirm one by one that the inner layer blocks each path, and check whether another test covers the guarantee when the tests that checked the outer layer disappear.

A defect fix changes only the one difference the issue defines and keeps weights, row counts, order, scores, and plan shape the same as the baseline. A port or restoration ends when speed, search and answer scores, and graph quality on the same input are all at or above the baseline, and a worsened metric is not a trade-off but a defect. Check regressions with two conditions that differ only in code (baseline and target HEAD, a new empty DB in the same container, the same input and model), and do not use the DB of a long-used instance as evidence.

In a destructive refactor, tests that pin only Protocols, method lists, file structure, or internal implementation may be redesigned. Remove replaced old implementations and unused product code after checking callers. Separate development evaluation tools and valid evaluation data from the product path as needed, and do not delete them for low usage alone. When a shared contract changes, fix callers and implementations together.

## Bulk moves and renames

Green CI shows only that imports resolve. Write and fix a separate move table of modules and symbols, and before writing, confirm that every destination in the table exists. A pure prefix move is based on the original tree of the requested commit, and does not invert the table of intermediate owners for definitions that already belong to a shared module. Put a token boundary after the dotted path (no `[A-Za-z0-9_]` following) or substitute from the original in one pass so that, when a new name contains the old name as a prefix, they do not overlap as in `feedback_routes_routes`. Build file lists and hash lists with `git ls-files -z`. The default output quotes non-ASCII names and makes existing files look deleted.

A move or rename is finished only after confirming the following.

1. Search the old name in every notation: dotted path, `stem.py`, `stem/`, backticks, snake form inside test names, and after regex `\b`. Define the scope by pattern, not by path.
2. Point `patch("...")` and monkeypatch strings at the module where the caller looks up the name, not the new location of the definition, and assert that the fake was actually called.
3. For each class, attribute, or function deleted or reshaped, search the integration tests and harness, run only those files with `-k`, and report the list and results.
4. The class names of response pydantic models go into LLM requests (`json_schema` name, `$defs` keys). If you touched LLM code, compare `model_json_schema()` of the two trees.
5. If there is a convention of writing caller paths in comments, such as query file headers, fix those too. If you inlined a factory, search all keyword arguments of the deleted factory.
6. `dataclasses.asdict` and `model_dump` omit properties, so deleting manual serialization can make values disappear.
7. Reverting one file during a bulk rename also reverts the other renames applied to that file. After reverting, run the substitution again and search the old names in one pass.

## Verifying behavior and performance

Prefer tests that observe public behavior. Do not use tests that pin only internal function names or private state as evidence of preservation. When deleting or rewriting tests, confirm where the existing valid behavioral assertions are verified.

Compose tests from fast units as the base, integration tests that use real dependencies, and a few E2E tests. Verify common contracts across supported backends with the same expected values. Keep product tests from importing the judgments of the development harness.

For each core feature, confirm a request path that actually passes. Do not report that the whole flow was verified merely because a test file exists or because a test replaced part of the API with a fake. If a real model or external service is part of how the feature works, confirm the combined behavior with a few E2E tests within the allowed environment and cost.

In before/after comparisons, use the same data and settings. If the randomness of model responses obscures the product comparison, control the variable by fixing responses and embeddings, record and replay, or similar. Do not judge preservation of search and loading by model answer quality. Separate tests where backends produce the same result from tests that preserve the previous version's product contract. Even if both backends change wrongly together, the comparison between them can pass.

Check performance separately from result equivalence. Match the inputs and execution environment of baseline and target, and keep the measurements, repetition count, variance, and tolerance. Writing latency to a log is different from a check that judges performance regression. A query round-trip assertion verifies the structural cost of that path but does not replace overall loading performance.

Run tests grouped by the scope of the change. Do not repeat the full test suite for every small fix. Use the repository's standard runner and isolation, and serialize runs that share DB and model resources under one runner and a lock. Reuse prepared environments safely and clean up only resources the worker owns.

When a product package moves, align the unit test directories too. Directories that need a different classification, such as shared fixtures, integration tests, and E2E, state the purpose of the exception. In repositories where structural symmetry is required, check new directories' deviations automatically.

## Safeguards and check output

Separate the fix of the current implementation from the prevention of recurrence for repeated criticisms. Connect constraints a machine can judge to the execution path of existing linters, static checks, tests, and CI. Try the strongest encoding first: change the architecture so the mistake cannot be written, then the types, then a lint whose error message names the fix, then a test, and write documentation last. If a structural fix exists, use only that; the instruction text is the symptom. Leave in AGENTS.md and similar instructions only work judgments that tools cannot make. Do not duplicate lists of files, APIs, or labels that can be looked up, or rules already checked. When moving sentences, confirm that the needed judgment criteria were not lost.

Include in a check's failure output the reason the rule is needed. Instead of repeating the check condition, explain who suffers what defect or cost from the violation. Require the reason on a common reporting path, and prevent missing check registration and reporting paths with a meta-check. Repository checks enumerate files with `git ls-files`, not `Path.rglob`. rglob passes in clean CI and fails in a developer copy that has worktrees and virtual environments. A check that will become a blocking gate shows false positives and false negatives in case files, and distinguishes a tool failure (read failure) from a violation with a different exit code. A baseline file holds only violations that predate the check and is not used as an exception list. A renamed item is also a new key, so make "zero added lines in the baseline" a commit gate. A person reviews whether the reason is meaningful; do not claim the machine judges the meaning too.

Follow the existing style rules and warning levels. Leave an explicit acceptance rationale for each detected item, either fixing it or stating it need not be fixed. Do not treat a warning's successful exit as acceptance. Updating an allowlist or test baseline can hide new violations, so review the justification for that increase too.

## Safeguard audit

Trace, per requirement, the actual checks, tests, CI, and failure conditions. Do not classify something as automatic blocking merely because a rule exists in the docs or a check file exists.

| Requirement | Implementation evidence | Current verification | Verdict | Needed action |
| --- | --- | --- | --- | --- |
| Preservation or structural requirement | File and location | Actual execution result or not run | Automatic blocking · partial verification · human review · none | Missing check or judgment |

For automatic blocking, confirm check registration, actual execution conditions, failure on violation, and the connection to the completion verdict. If needed, confirm with a small counterexample that the check catches the violation. For manual E2E, confirm separately whether it exists and the evidence of success for that commit. Do not claim to have confirmed remote required status checks or branch protection by looking only at CI files.

Organize audit results by impact. Connect requirements and evidence, and mark separately the scope you could not verify. Distinguish the fact that a safeguard is missing from the fact that a product defect was reproduced.

## Completion verdict and report

Distinguish passing tests from completing the design. Following the approved review system, confirm the remaining complexity and the evidence for preserved contracts with a review separate from the implementation. If there is no separate reviewer, state that limitation and do not describe it as having received independent review. Do not re-review confirmed scope without reason.

Connect the completion verdict to the needed tests and performance comparison results of that commit. Expensive E2E need not run for every small fix, but do not leave them out of final verification because they are manual. Do not count unrun, in-progress, or unclear results as passed.

The user report includes the following evidence, scaled to the work. Keep the reporting history and before/after comparisons in the conversation or an explicit review record, and have product code and documents describe the current state.

- Commits and scope reviewed and implemented, with done, in-progress, and not-started separated
- Initial and current trees, per-file line counts, and whether files were created, moved, renamed, or deleted
- Changes in code, file, and class counts and layer counts, and the remaining complexity
- Behavior and performance verification results and the checks that could not be done
- Unresolved defects, accepted warnings, and safeguards left to human judgment
