# rv per-agent execution

Read this file when the review is split across workers or another agent family must verify it.

This presents how each agent maps rv's unit structure. rv does not force an execution method. The agent's delegation rules (AGENTS.md etc.) take precedence over this file.

## Reviewer assignment

A review presumes that one does not judge one's own work, so reviewers and verifiers are sessions separated from the producer, given only the target and criteria. Claude takes every review role, independent and perspective-specific alike (a perspective-specific reviewer loads the area's `-expert` skill), in a new session that holds none of the producer's history; that separation carries the independence, whoever the producer is. The user's words (2026-11-18): "이제 나는 codex 시트가 없다. 내 하네스, 워크플로우, 스킬, 기타 등등에서 모두 코덱스를 클로드로 전환해라." These moved to Claude the review roles the user had given Codex on 2026-11-16 ("리뷰는 코덱스라고"), and what still holds of that answer is that review is delegated, never skipped: "아니 리뷰는 시켜야돼". Pick the reviewer's model by the situation, as the harness model-tier table says ("모델 수준을 잘 고려해야된다", "상황에 따라", 2026-11-18): an independent review of a PR, design, or plan and a perspective-specific expert review run on opus at high thinking, xhigh when the change spans several layers; a recheck of a small fix commit against one finding may run on sonnet. pi and Hermes have no review role (pi takes narrow edits whose location and method are fixed, Hermes takes research, documents, and operations). If no Claude account can launch a reviewer because every account is at its limit, write that fact and the remaining verification gap in the result document and ask the caller. Do not fill the review count by sending in agents outside their role.

Submit APPROVE, REQUEST_CHANGES, or COMMENT according to the verdict, but GitHub does not let a PR author approve their own PR, so on your own PR post a verdict equivalent to APPROVE as COMMENT. This record does not meet the approval requirement, and the merge state stays `REVIEW_REQUIRED`. If approval is needed, report that another person's approval or the repository admin's ruleset judgment is needed, and do not create an approval with another account.

## Item turns

Each review item of `references/items.md` goes to the reviewing session that runs its unit as its own prompt, a per-area item with every area that session reviews, and the next item goes to the same session as a follow-up prompt once the previous turn ended. Use the agent product's native means of continuing a session with its context intact; do not start a new session per item, because the user chose consecutive turns of one session. A reviewing session ends each turn with the item's ledger rows and does not re-delegate.

## Claude Code

The coordinator starts subagents with the Agent tool. Whether the coordinator edits code directly or only delegates to workers follows the project's delegation rules.

| Unit | Execution |
|---|---|
| U0 | Run by the coordinator |
| U1, U2 | Parallel Agent forks, one per unit; each next item goes to the same agent with SendMessage, which the Agent tool documents as continuing "a previously spawned agent with its context intact" |
| U3 | Agent per area or per group of areas, loading the areas' `-expert` skills; items sent one per turn the same way, each per-area item covering all the agent's areas |
| U4 | Verified by a fresh Agent (not a fork) different from U3 |
| U5 | Agent |
| U6 | The coordinator assembles the markdown document |

## Claude reviewer

The Claude reviewer session runs the review units assigned to it. When split execution is needed, the coordinator starts workers with Paseo `create_agent` or Orca `orca orchestration worker-start` according to the shared division-of-labor criteria, and gives one worker only one unit. A delegated worker does not re-delegate without explicit permission.

| Unit | Execution |
|---|---|
| U0 | Run by the coordinator |
| U1-U2 | Review worker; each next item is a `send_agent_prompt` to the same agent id |
| U3 | Worker per area or per group of areas, loading the areas' `-expert` skills; items sent one per turn the same way, each per-area item covering all the worker's areas |
| U4 | Verification worker different from U3 |
| U5 | Propagation check worker |
| U6 | The coordinator assembles and posts the markdown document |

A worker brief includes every value of the input contract, past rejection types, a self-check script, a prohibition on side work, and the report scope.
