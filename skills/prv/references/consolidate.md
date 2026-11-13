# Consolidate perspective review findings

The perspective reviews of `<PLAN_COPY>` are finished: `<REVIEW_FILES>`. The project at the review base is `<REVIEW_WORKTREE>` (commit `<REVIEW_BASE>`).<EXTRA_COMMITS>

1. Verify every finding: open each cited file:line yourself. Verdict per finding: CONFIRMED (you observed the contradiction or omission), PLAUSIBLE (needs execution or more tracing), REJECTED (cite the contradicting line), DUPLICATE-OF <id>. Re-grade severity yourself; the reviewers' severity is not used.
2. Cluster duplicates across reviewers. Agreement among reviewers is not evidence: judge a cluster by the code, not by how many raised it.
3. When earlier reviews of the same plan are given (`<PRIOR_REVIEWS>`), mark per cluster whether one already raised it.
4. When the plan changed since the reviewed copy (current: `<PLAN_CURRENT>`), state for each confirmed cluster whether it still applies, citing the current line.
5. Per reviewer: CONFIRMED, PLAUSIBLE, REJECTED counts and precision = confirmed / (confirmed + rejected).

Output `<OUTPUT>` in Korean. Top section `## 현재 계획에 남은 확정 결함`: a table (cluster, severity, current plan line, evidence, fix). Then the per-reviewer numbers, then per-finding tables. End your turn, under 4,000 characters, with the number of confirmed clusters still applying, the precision per reviewer, and the output path. Read only these inputs and the repository. Do not edit anything else. No git commits, pushes, PRs, issues or messages. Do not start other agents.
