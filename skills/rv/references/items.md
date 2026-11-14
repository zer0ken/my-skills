# rv review items and the item ledger

Read this file before running U0-U3. It is the single source of the review item catalog; `bin/check-review.py` reads the catalog table below, so a change here changes the check.

A review item (검토 항목) is one checklist judgment of U0-U3 that the review must make and record: an item is in the catalog below, and a check that is not in it is part of the item whose `SKILL.md` part holds it. The item ledger (항목 원장) is the record of the items: one row per item, per area for the per-area items, written in the turn that examined that item.

## One item per turn

Each item is examined in its own turn, and the turns are consecutive turns of the same reviewing session. The user's words (2026-11-14): "Rv 스킬로 리뷰를 할 때, 각 항목 반드시 별도의 턴으로 파악하도록 해야도ㅑ. 그리고 철저히 리뷰할 수 있어야돼." and, asked whether that means consecutive turns of one session or separate sessions, "같은 세션의 연속 턴." A turn is one prompt to the session and the response that ends it. The session keeps what earlier turns read, so an item does not reread what an earlier item already established, but it does not judge the next item before its own turn.

1. The driver (the coordinator, or the agent that received the review) sends one item per prompt: the item id, its area, its `SKILL.md` part, and its sub-checks from the catalog. Each next item goes to the same session as a follow-up prompt that keeps its context, after the turn of the previous item ended.
2. The reviewing session examines only that item, appends the item's row to the ledger file, and ends the turn with that row and the R-IDs it produced. It does not start the next item in the same turn and does not write a row for an item it was not sent.
3. When the agent that received the review has nobody to send it the next prompt (the user called `/rv` in that session), it becomes the driver: it opens one reviewing session, preferring a different model family as the agent rules say, and drives it item by item. Only when it cannot open a session does it examine the items itself as steps, one item and its row before any reading for the next, writes `단계:<n>` in the `턴` column, and states in `## 검증 범위` that the items were not separated into turns.
4. Units that run in parallel (U1 and U2, U3 per area) each have their own reviewing session, and each session takes its unit's items in consecutive turns. U4 verifiers stay separate fresh sessions; per-item turns do not merge verification into the reviewing session.
5. A follow-up review runs every item again at the current head, because it is exhaustive.

## Ledger format

The ledger is a Markdown file kept with the review's separate material, not a section of the posted review. It holds one table with these columns in this order.

| Column | Value |
|---|---|
| 턴 | `<session name>:<turn number>`; unique in the ledger, so two rows never come from one turn |
| 항목 | An item id from the catalog |
| 영역 | `전체` for an item that is not per area; for a per-area item, the area name U0 gave, or `전체` when U3 is not split |
| 확인한 범위 | What was read or run for the item, naming each of the item's sub-checks with its result |
| 근거 | At least one `file:line`, a command in backticks, or a URL |
| 판정 | The R-IDs the item produced, `배제: <reason>` when the item found nothing, or `해당 없음: <reason>` when the item does not apply |

A `해당 없음` row is exempt from naming the sub-checks but still gives its reason and evidence, such as the `git diff --stat` that shows no DB file changed. Every R-ID a row names must be a finding in the review document. A per-area item appears once for every area that any per-area row names; any other item appears exactly once.

## Catalog

| 항목 | 단위 | 영역별 | SKILL.md 부분 | 세부 |
|---|---|---|---|---|
| U0-prior | U0 | 아니오 | U0, the recheck of prior_ids, responses, and user decisions | 이전 지적, 응답, 사용자 결정 |
| U1-import | U1 | 아니오 | U1 item 1 | 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7 |
| U1-layout | U1 | 아니오 | U1 item 2 | 2.1, 2.2, 2.3 |
| U1-names | U1 | 아니오 | U1 item 3 | 3.1, 3.2, 3.3 |
| U1-size | U1 | 아니오 | U1 items 4.1-4.3 | 4.1, 4.2, 4.3 |
| U1-split | U1 | 아니오 | U1 item 4.4 | 4.4.1, 4.4.2, 4.4.3 |
| U1-leftovers | U1 | 아니오 | U1 items 4.5-4.6 | 4.5, 4.6 |
| U1-precedent | U1 | 아니오 | U1 item 5 | 5.1, 5.2, 5.3 |
| U2-concepts | U2 | 아니오 | U2 question 0 | 0.1, 0.2, 0.3, 0.4 |
| U2-structure | U2 | 아니오 | U2 question 1 | 1.1, 1.2, 1.3 |
| U2-quality | U2 | 아니오 | U2 question 2 | 2.1, 2.2, 2.3 |
| U3-safety | U3 | 예 | U3 steps 1-4 | 안전 사실, 심볼 밖 소비자, 실행 증명, 배제 목록 |
| U3-reuse | U3 | 예 | U3, reuse and known implementations | 저장소 재사용, 외부 구현, 의존성, 최소 변경 |
| U3-cost | U3 | 예 | U3, implementation cost | 입력 규모, 반복 작업 |
| U3-failure | U3 | 예 | U3, failure paths | 실패 전달, 원인 맥락, 재시도 |
| U3-security | U3 | 예 | U3, security | 입력 검증, 조립, 비밀, 인증 |
| U3-tests | U3 | 예 | U3, tests | 결함 시 실패, 공개 동작, 경계, 가짜 형태, CI |
| U3-claims | U3 | 예 | U3, claims against results | 주장 대조, 검증 조건 |
| U3-db | U3 | 예 | U3, DB schema and usage | 스키마 권고, 호출 수, 인덱스, 트랜잭션 |
| U3-docs | U3 | 예 | U3, meaning and organization of documents | 필요성, 순서, 예시 |
