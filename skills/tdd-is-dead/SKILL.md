---
name: tdd-is-dead
description: Coding work order. Understand scope and intent first, write target tests, implement while respecting existing intent, self-review, run only the minimal tests, and verify last with the full suite or PR CI. Bans the TDD-style write-run-fix loop. Also covers building a feature PoC outside the repository and porting it into product code via a /ds port design. Use when starting code implementation, bug fixes, test writing, PoC experiments, or porting a PoC into the product, and when the user calls /tdd-is-dead.
---

# tdd-is-dead

Do not do TDD. Write tests, but writing tests carelessly without understanding the code's context and then looping on run and fix is a waste of time and is prohibited. Running tests does not replace understanding; it is a means to confirm what you understood.

The four steps of the global instructions (`AGENTS.md`) (fix the intent, fix the implementation, optimize, test loop) and the user's direct instructions take precedence over this skill. This skill is the detailed procedure for those four steps.

## Research first

Make the work plan after defining the problem and surveying known solutions, following the research principle of the shared instructions. The standard for material used as evidence also follows the shared instructions. This skill adds one thing.

1. When each step of the plan ends, call `/zoom-out` yourself. Check against the overall goal, the user's original instruction, and the remaining steps that the current work is not sunk into one subproblem, then decide the next step.

## Choosing a path

At the start of the work, choose one of two paths.

1. Direct path. Work whose target behavior can be judged by code and unit tests alone. Defect fixes, feature additions with a fixed contract, and refactoring belong here.
2. PoC-first path. Work whose promise cannot be judged before running the solution. Pipelines that depend on model output quality, features that must choose one of several design alternatives, and work where the user ordered a PoC or external experiment belong here. This path goes through a PoC stage and a port stage, then ends with the verification of the direct path.

## Common criteria

Apply to the implementation on both paths.

1. Computational complexity. Worst-case complexity is at most O(n) in the input size. Write the input size as a symbol for each path to check it. Nested loops, correlated subqueries, greedy algorithms that re-evaluate all candidates every iteration, and sorting (O(n log n)) also count as exceeding it; if the consumer does not require order, remove the sort. For SQL, block even the bad plans the planner could choose through the query structure, and confirm linearity by measuring with the input size doubled. Write this condition into delegation briefs too.
2. Model calls. Bind the number of model calls to the output space or the changed delta, not the input size. Do not ask again about what has already been judged or has not changed. Report computational complexity and call count separately. One model call costs T_llm, so it is slow even if linear.
3. Anti-pattern cleanup. Once implementation commits accumulate, before measurement and `/rv`, have a worker who did not implement it clean up the whole PR diff (`origin/main..HEAD`) by anti-pattern, maintainability, and simplification criteria while preserving behavior. Write these criteria into the brief.

## Direct path

1. Fix the intent. Read the problem that the issue, requirements, user decisions, and existing code and commits try to solve, and decide the work scope, target behavior, and completion criteria. If the intent is unclear, confirm with the user before implementing.
2. Fix the scope. Search the whole repository with LSP or Serena for the names of the functions, columns, tables, and queries being changed, and list callers and write paths. Include other backend implementations and test fakes in the list, and record for each path whether to change it and why. Check that fakes return the same shape as the real implementation.
3. Write target tests. Write tests that verify the agreed behavior. Do not assert implementation details. Behavior is what the code's users (callers, end users, other services) can observe: return values, errors, state they can read back, and effects outside the code such as a request sent or a row written. Judge each test against two imagined edits.
  3.1 Break the behavior: return a wrong value, skip an effect, or do it twice. If the test still passes, it proves nothing. Usual causes are an assertion looser than the contract, an expected value computed by the code under test, a restated constant that never runs the code that reads it, and an assertion on data the test built itself.
  3.2 Change the internals while keeping every observable result. If the test now fails, it is pinned to the implementation.
  3.3 Keep a test that catches 3.1 and survives 3.2. Drive the code through its users' interface with a concrete input, derive the expected value from the requirement and not from a run of the code, and assert exactly what the contract promises. When an effect must not happen, pair the assertion with a case where it does happen, so the test shows it can see the effect.
  3.4 Prefer no new test over a bad test: one that mostly tests mocks, encodes current implementation details, depends on timing or unrelated global state, or needs expensive infrastructure for a small fix. When a new test is impractical, use the closest executable check instead (a targeted script, a reproduction command, a log assertion) and say why. Whichever is used, a regression check must be shown failing on the defective code before the fix.
4. Implement. Keep the existing structure, naming, conventions, and design judgments, and do not edit code outside the scope. When porting another implementation's behavior, confirm what constraint that behavior existed for, and follow the reference implementation's place of computation (DB query, code) as is.
5. Review again. Before running, reread the diff and check boundary conditions, error paths, missed callers, and type and contract violations. Check that the diff covers the whole list from 2.
6. Optimize. Keeping the settled behavior, reduce unnecessary processing, duplication, DB round trips, and model calls. Complexity and call count follow `Common criteria`. If the intent of behavior or structure changes, go back to 1 or 4.
7. Run the minimal tests. Following the test-running rules below, run only the tests that touch the changed names, and record the tests run and the grounds for choosing that scope.
8. Return on failure. Judge whether the cause of failure lies in the intent, scope, tests, or implementation, and redo from that step. Do not edit code or tests and rerun without understanding the cause. When a check fails, suspect the observation method (stale output, wrong process, cached value, wrong tree) before suspecting the system, and read the real artifact directly.
9. Full verification. Verify with the full suite or PR CI. Run the full suite yourself only when the user asks, and if it takes long, hand the command to the user. If design judgments or risks remain, ask the user for a review.

## PoC-first path

### PoC stage

1. Problem definition. Define the problem before choosing a solution (`problem-modeling`). The order of progress is: settle the ground truth, settle the structure, iterate improvements. Set the answer key and quality criteria first, decide the pipeline structure, then refine prompts and parameters. Fix functional defects first to settle the code structure, and do quality improvement with prompts and minimal pipeline changes.
2. Experiment location. End the PoC within a time cap. Write experiment code in an experiment directory outside the repository and do not edit product files. If data the product produces is the input, produce it by actually loading it with the product, and the PoC only reads that DB. Do not split stages finer than the unit the user set, and judge promise by experiments that tune each stage. Every PoC brief carries an input-source cross-check table. For each field that goes into the model and the judgment, write the source of the PoC value, the code location (`file:line`) in the comparison-baseline product commit that fills the same field, and its value (including empty). If they differ, state the difference as a condition or rebuild the input through the product path. A test that the record format is the same does not replace this cross-check. After a commit that changes or reverts a product contract, list every experiment that uses fixed inputs and labels made before it and verify them again. Choose judgment signals (similarity, candidate channels) from "what determines the same target", not from small-sample numbers or the inertia of existing code.
3. Compare alternatives. Build several options from the known solutions confirmed in research and compare them on the same input. Attach a source to each option.
4. Design conditions. Check that every option meets the following conditions.
  4.1 It meets the complexity and call-count caps of `Common criteria`.
  4.2 Model calls go out as parallel batches that do not wait on each other. Report total time as a multiple of one model response time (T_llm), with T_llm or less as the goal.
  4.3 The code structure can be moved onto the layers and contracts of the product being ported to.
5. Evaluation. Base conclusions on qualitative evaluation that reads outputs case by case, and use numbers as support. For each failure, separate with that call's actual input whether the cause is the pipeline structure (stage composition, order, data flow, judgments assigned to stages) or the prompt.
6. Freeze and report. When you judge it cannot be improved further, freeze the PoC in that state (code, input, results, remaining defect list), report to the user, then move to the port.

### Port stage

1. Port design. Use `/ds` to decide in which component of the product architecture, with what responsibility, the PoC's judgment structure should sit. `ds` creates no files, so record its result as a port design document in the experiment directory before starting implementation. The document records the base commit, goal, completion criteria, decisions on compatibility and scope, and the defects found in the PoC evaluation with their fix locations.
2. Port implementation. Create a worktree from the base branch and follow 1-6 of the direct path. Do not paste PoC code as is; move the judgment structure to fit the product's contracts and conventions. Fix defects found in the PoC during the port. Do not carry the PoC's temporary workarounds or non-standard implementations into the product; replace them with standard implementations. When adding a storage query, confirm with one parameterized test that every backend and test fake returns the same meaning. If the reference implementation computes inside the DB, port that SQL and do not port a Python fallback. Moving computation from the DB to Python requires user approval. If you change the transaction or commit behavior of a shared helper, list every caller and compare each against the reference implementation, and keep a negative test for paths that must roll back. Guarantee functional equivalence of two backends with one test function parameterized over both implementations, not with each one's own test file; a replay cache miss in a harness that checks equivalence by record and replay is not a cost to reduce but a defect signal that the two implementations sent different requests.
3. draft PR. When the port implementation is done, open the PR as draft (unsettled) and get CI passing. Finish the anti-pattern cleanup of `Common criteria` before measurement and `/rv`.
4. Functional verification. Code that controls model output, such as model input composition, candidate limits, gates, and pre-save validation, is functionality. Confirm functionality with unit tests that assert inputs and saved results using a fake model, and stop there. Do not confirm functionality with load measurements.
5. Quality verification. After closing all functional defects in draft state, compare the base branch (main) and the port branch once. The two conditions differ only in code and use a new empty DB, the same input, and the same model. Measure through the whole real product path and look at speed and quality together. The port ends when every metric is at or above the baseline. A worsened metric is not a trade-off but a defect; go back to the step that caused it and fix it.
6. Review and merge. Give an independent review via `/rv` to a new reviewer who did not implement it, address the comments, confirm CI passes, then switch the PR to ready (settled, unverified). Then fix until no review comments remain, request re-review, and merge. Do not split the PR unless the user instructed it.

## Test-running rules

Running tests has the lowest priority. Do not make measurement or feature work wait for tests.

1. When a work unit ends, run once only the test files that directly touch the changed names. If you changed SQL or Cypher, add that query's integration test. After a fix, rerun only the failed tests.
2. Do not run a full suite the user did not request. When handing tests to a worker, write "only the test files that touch the changed names" in the brief.
3. Do not change expected values, widen assertions, or skip tests to make them pass. Report a test that also fails on the base commit instead of widening its assertion to pass it.
4. Answer questions like "does this change break X" by reading the diff and call relationships, not by substituting a long run for the answer.
5. Start verification from the test that finds failure fastest, widen the scope, and put the long full test last. Do not follow the order mechanically; decide by where the change would break first. If a stage fails, do not go to the next stage.

## Report

When reporting results, state the tests, measurements, commits, and scope actually run. Do not count unrun or failed verification as passed. For a defect fix, name the regression check that failed on the defective code with the failure it printed, and the run that passed after the fix. A fix without failing-before evidence is not verified; report it as unverified instead of done. Prefer a scripted check that a reviewer can rerun over a one-time observation. On the PoC-first path, also state which stage you are in: PoC, port implementation, draft PR, functional verification, quality verification, or review.
