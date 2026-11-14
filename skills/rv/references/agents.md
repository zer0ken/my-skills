# rv per-agent execution

Read this file when the review is split across workers or another agent family must verify it.

This presents how each agent maps rv's unit structure. rv does not force an execution method. The agent's delegation rules (AGENTS.md etc.) take precedence over this file.

## Reviewer assignment

A review presumes that one does not judge one's own work, so reviewers and verifiers are sessions separated from the producer, given only the target and criteria. Claude takes every review role, independent and perspective-specific alike. Codex takes code writing and running only and has no review role; the user's words (2026-11-14), after a lead gave design-document work to a Codex partner: "그리고 코덱스는 코드밖에 못짜는 병신이야." So Codex's, pi's, and Hermes's work is reviewed by Claude, a different family, and Claude's work by an empty Claude session separated from the producer. pi and Hermes have no review role either (pi takes narrow edits whose location and method are fixed, Hermes takes research, documents, and operations). If one family cannot be launched because of limits or outages, write that fact and the remaining verification gap in the result document, and replace it with a worker of another family under the same conditions or ask the caller. Do not fill the review count by sending in agents outside their role.

Submit APPROVE, REQUEST_CHANGES, or COMMENT according to the verdict, but GitHub does not let a PR author approve their own PR, so on your own PR post a verdict equivalent to APPROVE as COMMENT. This record does not meet the approval requirement, and the merge state stays `REVIEW_REQUIRED`. If approval is needed, report that another person's approval or the repository admin's ruleset judgment is needed, and do not create an approval with another account.

## Item turns

Each review item of `references/items.md` goes to the reviewing session that runs its unit as its own prompt, and the next item goes to the same session as a follow-up prompt once the previous turn ended. Use the agent product's native means of continuing a session with its context intact; do not start a new session per item, because the user chose consecutive turns of one session. A reviewing session ends each turn with the item's ledger row and does not re-delegate.

## Claude Code

The coordinator starts subagents with the Agent tool. Whether the coordinator edits code directly or only delegates to workers follows the project's delegation rules.

| Unit | Execution |
|---|---|
| U0 | Run by the coordinator |
| U1, U2 | Parallel Agent forks, one per unit; each next item goes to the same agent with SendMessage, which the Agent tool documents as continuing "a previously spawned agent with its context intact" |
| U3 | Agent per area, loading that area's `-expert` skill; items sent one per turn the same way |
| U4 | Verified by a fresh Agent (not a fork) different from U3 |
| U5 | Agent |
| U6 | The coordinator assembles the markdown document |

## Codex

Codex is not a review worker, so no coordinator assigns it a unit. When the user calls rv directly in a Codex session, the user's instruction holds: Codex runs the units itself in order and does not start workers.

A worker brief includes every value of the input contract, past rejection types, a self-check script, a prohibition on side work, and the report scope.
