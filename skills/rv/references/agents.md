# rv per-agent execution

Read this file when the review is split across workers or another agent family must verify it.

This presents how each agent maps rv's unit structure. rv does not force an execution method. The agent's delegation rules (AGENTS.md etc.) take precedence over this file.

## Reviewer assignment

A review presumes that one does not judge one's own work, so choose reviewers and verifiers from a model family different from the producer's. Codex takes independent review from a different model family, Claude takes perspective-specific expert review, and pi and Hermes have no review role (pi takes narrow edits whose location and method are fixed, Hermes takes research, documents, and operations). If one family cannot be launched because of limits or outages, write that fact and the remaining verification gap in the result document, and replace it with a worker of another family under the same conditions or ask the caller. Do not fill the review count by sending in agents outside their role.

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

Codex runs the independent review unit assigned to it. When split execution is needed, the orchestrator starts workers with Paseo `create_agent` according to the shared division-of-labor criteria, and gives one worker only one unit. A delegated Codex worker does not re-delegate without explicit permission.

| Unit | Execution |
|---|---|
| U0 | Run by the coordinator |
| U1-U2 | Review worker; each next item is a `send_agent_prompt` to the same agent id |
| U3 | Worker per area; items sent one per turn the same way |
| U4 | Verification worker different from U3 |
| U5 | Propagation check worker |
| U6 | The coordinator assembles and posts the markdown document |

A worker brief includes every value of the input contract, past rejection types, a self-check script, a prohibition on side work, and the report scope.
