# Consolidate perspective review findings

The perspective reviews of `<PLAN_COPY>` are finished: `<REVIEW_FILES>`. The project at the review base is `<REVIEW_WORKTREE>` (commit `<REVIEW_BASE>`).<EXTRA_COMMITS>

1. Verify every finding: open each cited file:line yourself. Verdict per finding: CONFIRMED (you observed the contradiction or omission), PLAUSIBLE (needs execution or more tracing), REJECTED (cite the contradicting line), DUPLICATE-OF <id>. Re-grade severity yourself; the reviewers' severity is not used.
2. Cluster duplicates across reviewers. Agreement among reviewers is not evidence: judge a cluster by the code, not by how many raised it.
3. When earlier reviews of the same plan are given (`<PRIOR_REVIEWS>`), mark per cluster whether one already raised it.
4. When the plan changed since the reviewed copy (current: `<PLAN_CURRENT>`), state for each confirmed cluster whether it still applies, citing the current line.
5. When the plan owner's claim ledger is given (`<CLAIM_LEDGER>`, lines `A<n>: <claim> | <observation that would show it wrong> | <where checked>`), open the location every line cites and mark the line 확인됨 when it shows the claim, or 근거 아님 (cite what the location shows instead). For each confirmed cluster, name the ledger line it refutes, or write 원장 누락 when the plan claim it refutes is not in the ledger.
6. Per reviewer: CONFIRMED, PLAUSIBLE, REJECTED counts and precision = confirmed / (confirmed + rejected).

Output `<OUTPUT>` in Korean. Top section `## 현재 계획에 남은 확정 결함`: a table (cluster, severity, current plan line, evidence, fix, and, when a ledger is given, the ledger line or 원장 누락). When a ledger is given, next a section `## 주장 원장 점검`: the 근거 아님 lines with what their location shows, and the counts of 확인됨, 근거 아님, and 원장 누락. Then the per-reviewer numbers, then per-finding tables. End your turn, under 4,000 characters, with the number of confirmed clusters still applying, the precision per reviewer, the ledger counts when a ledger is given, and the output path. Read only these inputs and the repository. Do not edit anything else. No git commits, pushes, PRs, issues or messages. Do not start other agents.
