# rv review items and the item ledger

Read this file before running U0-U3. It is the single source of the review item catalog; `bin/check-review.py` reads the catalog table below, so a change here changes the check.

A review item (검토 항목) is one checklist judgment of U0-U3 that the review must make and record: an item is in the catalog below, and a check that is not in it is part of the item whose `SKILL.md` part holds it. Each item judges the review-technique perspectives in its `관점` column (`~/.agents/skills/review-technique/perspectives/<id>.md`), the yardsticks rv, srv, and prv share, so an item's turn also checks those perspectives' `Broken if` states; an item whose `SKILL.md 부분` is a perspective file takes its criteria from that file alone. Every perspective of the catalog is judged by some item (REVIEW-TECHNIQUES.md 4.4 and 8.3 rv-2); U0-prior judges no perspective, because it is the follow-up step of the technique, not a yardstick. The item ledger (항목 원장) is the record of the items: one row per item, per area for the per-area items, written in the turn that examined that item.

## One item per turn

Each item is examined in its own turn, and the turns are consecutive turns of the same reviewing session. The user's words (2026-11-14): "Rv 스킬로 리뷰를 할 때, 각 항목 반드시 별도의 턴으로 파악하도록 해야도ㅑ. 그리고 철저히 리뷰할 수 있어야돼." and, asked whether that means consecutive turns of one session or separate sessions, "같은 세션의 연속 턴." A turn is one prompt to the session and the response that ends it. The session keeps what earlier turns read, so an item does not reread what an earlier item already established, but it does not judge the next item before its own turn.

The words name the item, not the pair of an item and an area: a per-area item is one item, examined in one turn over every area its session reviews, with one row per area written in that turn. So a session's item turns number its items, whatever the number of areas; one turn per item and area multiplies the turns by the number of review units, and a review that does not finish is not posted. The user's words (2026-11-16), when automated reviews of 22-40 item turns did not finish: "리뷰가 왜 안 끝나 (…)" and "리뷰를 해서 올리기 하라고. 그게 어렵냐?". Thoroughness per area is kept by the rows, not by the turns: each area's row names every sub-check with its result for that area and its own evidence.

1. The driver (the coordinator, or the agent that received the review) sends one item per prompt: the item id, its areas (`전체`, or for a per-area item every unit the session reviews), its `SKILL.md` part, and its sub-checks from the catalog. Each next item goes to the same session as a follow-up prompt that keeps its context, after the turn of the previous item ended.
2. The reviewing session examines only that item, in each of its areas, appends the item's rows to the ledger file, one per area, and ends the turn with those rows and the R-IDs it produced. It does not start the next item in the same turn and does not write a row for an item it was not sent.
3. When the agent that received the review has nobody to send it the next prompt (the user called `/rv` in that session), it becomes the driver: it opens one reviewing session, a new Claude session separated from the producer as the agent rules say, and drives it item by item. Only when it cannot open a session does it examine the items itself as steps, one item and its row before any reading for the next, writes `단계:<n>` in the `턴` column, and states in `## 검증 범위` that the items were not separated into turns.
4. Units that run in parallel (U1 and U2, U3 split by review units) each have their own reviewing session, and each session takes its unit's items in consecutive turns; a U3 session given several review units covers all of them in each per-area item's turn. U4 verifiers stay separate fresh sessions; per-item turns do not merge verification into the reviewing session.
5. A follow-up review runs every item again at the current head, because it is exhaustive.

The first item turn of a reviewing session is its selection turn (선별 턴). In it the session judges, for every item whose `고르는 조건` is not `항상`, whether the change meets that condition, and writes a `해당 없음: <the condition it does not meet>` row, with the evidence that shows it, for each item it does not pick; it picks every item it cannot clear that way. Those rows may share the selection turn, and every picked item and every `항상` item still gets its own turn. The user's words (2026-11-14): "Rv 스킬로 리뷰를 할 때, 각 항목 반드시 별도의 턴으로 파악하도록 해야도ㅑ." and (2026-11-25): "Rv는 단일 프론티어 모델을 쓴다는 가정 하게 완벽히 리뷰가 가능한 가는하면서 비용이 적게 드는 절차로 수행되여야 하고". Asked whether to narrow the first decision to the picked items so that an item the change does not touch spends no turn (REVIEW-TECHNIQUES decision 2), the user answered (2026-11-25): "권장으로해라". A row the selection turn writes is an item cleared by its condition, not an examined item, so it names no sub-check, as the ledger format exempts a `해당 없음` row.

## Ledger format

The ledger is a Markdown file kept with the review's separate material, not a section of the posted review. It holds one table with these columns in this order.

| Column | Value |
|---|---|
| 턴 | `<session name>:<turn number>`; one turn holds one item, so rows that share a turn are the area rows of one per-area item, and two items never share a turn |
| 항목 | An item id from the catalog |
| 영역 | `전체` for an item that is not per area; for a per-area item, the review unit id from U0's `units.json` (`U-1`, ...), or `전체` for a target without a diff |
| 확인한 범위 | What was read or run for the item, naming each of the item's sub-checks with its result |
| 근거 | At least one `file:line`, a command in backticks, or a URL |
| 판정 | The R-IDs the item produced, `배제: <reason>` when the item found nothing, or `해당 없음: <reason>` when the item does not apply |

A `|` inside a cell, inside a backtick command too, is written `\|`, because a GFM table reads every other `|` as a cell boundary ("Include a pipe in a cell’s content by escaping it, including inside other inline spans", https://github.github.com/gfm/#tables-extension-); `&#124;` does not serve, because a code span shows it as those six characters. A `해당 없음` row is exempt from naming the sub-checks but still gives its reason and evidence, such as the `git diff --stat` that shows no DB file changed. Every R-ID a row names must be a finding in the review document. A per-area item appears once for every area that any per-area row names; any other item appears exactly once.

## Catalog

| 항목 | 단위 | 영역별 | SKILL.md 부분 | 세부 | 고르는 조건 | 관점 |
|---|---|---|---|---|---|---|
| U0-prior | U0 | 아니오 | U0, the recheck of prior_ids, responses, and user decisions | 이전 지적, 응답, 사용자 결정 | 이 PR 에 이전 리뷰, 작성자 응답, 사용자 결정 중 하나가 있다 | - |
| U1-import | U1 | 아니오 | U1 item 1 | 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7 | 변경이 import, `__init__.py`, 패키지 공개 경로를 더하거나 바꾼다 | H4 |
| U1-layout | U1 | 아니오 | U1 item 2 | 2.1, 2.2, 2.3 | 변경이 파일이나 디렉터리를 더하거나 옮기거나 지운다 | H4 |
| U1-names | U1 | 아니오 | U1 item 3 | 3.1, 3.2, 3.3 | 변경이 파일, 모듈, 식별자의 이름을 더하거나 바꾼다 | L12 |
| U1-size | U1 | 아니오 | U1 items 4.1-4.3 | 4.1, 4.2, 4.3 | 항상 | H5 |
| U1-split | U1 | 아니오 | U1 item 4.4 | 4.4.1, 4.4.2, 4.4.3 | 항상 | H5 |
| U1-leftovers | U1 | 아니오 | U1 items 4.5-4.6 | 4.5, 4.6 | 항상 | L12, H5 |
| U1-precedent | U1 | 아니오 | U1 item 5 | 5.1, 5.2, 5.3 | 변경의 근거로 기존 코드나 관례를 드는 곳(PR 본문, 응답, 주석, 커밋)이 있다 | H1 |
| U2-concepts | U2 | 아니오 | U2 question 0 | 0.1, 0.2, 0.3, 0.4 | 항상 | H2 |
| U2-structure | U2 | 아니오 | U2 question 1 | 1.1, 1.2, 1.3 | 항상 | H3 |
| U2-quality | U2 | 아니오 | U2 question 2 | 2.1, 2.2, 2.3 | 항상 | H2, H3 |
| U2-intent | U2 | 아니오 | `~/.agents/skills/review-technique/perspectives/H14.md` | 결정 확인, 찾아본 범위, 기록할 자리 | 변경이 대안 선택이나 불변식에 기대는데, 그 결정을 코드만으로는 알 수 없다 | H14 |
| U3-safety | U3 | 예 | U3 steps 1-4 | 안전 사실, 심볼 밖 소비자, 실행 증명, 배제 목록 | 항상 | L1, L2, L4 |
| U3-reuse | U3 | 예 | U3, reuse and known implementations | 저장소 재사용, 외부 구현, 의존성, 최소 변경 | 변경이 함수, 클래스, 모듈, 설정 키, 질의, 의존성 같은 새 단위를 더한다 | H6 |
| U3-cost | U3 | 예 | U3, implementation cost | 알려진 알고리즘, 입력 규모, 반복 작업 | 변경이 반복, 검색, 정렬, 집계, 순위, 수치 계산을 더하거나 바꾼다 | L5 |
| U3-failure | U3 | 예 | U3, failure paths | 실패 전달, 원인 맥락, 재시도 | 변경이 외부 호출, I/O, 파싱, 예외 처리, 재시도를 더하거나 바꾼다 | L3 |
| U3-security | U3 | 예 | U3, security | 입력 검증, 조립, 비밀, 인증 | 변경이 사용자·다른 서비스·파일·모델에서 온 입력, 질의·명령·경로 조립, 비밀, 인증·권한에 닿는다 | H10, L8 |
| U3-tests | U3 | 예 | U3, tests | 결함 시 실패, 공개 동작, 경계, 가짜 형태, CI, 같은 PR, 최소, 사용자 가치, 픽스처 재사용, 준비 범위 | 항상 | H12, H13, L11 |
| U3-claims | U3 | 예 | U3, claims against results | 주장 대조, 검증 조건 | 항상 | L15 |
| U3-db | U3 | 예 | U3, DB schema and usage | 스키마 권고, 호출 수, 인덱스, 트랜잭션 | 변경이 스키마, 질의, 인덱스, 트랜잭션, DB 연결을 더하거나 바꾼다 | H7, L6 |
| U3-docs | U3 | 예 | U3, meaning and organization of documents | 필요성, 순서, 예시 | 변경이 문서, docstring, 주석을 더하거나 바꾼다 | L13 |
| U3-concurrency | U3 | 예 | `~/.agents/skills/review-technique/perspectives/H8.md`, `~/.agents/skills/review-technique/perspectives/L7.md` | 결과 상태, 순서 메커니즘, 경쟁 창, 대기 상한 | 변경이 병렬 실행, 잠금, 큐, 재시도, 대기, 공유 상태, 여러 단계 쓰기를 더하거나 바꾼다 | H8, L7 |
| U3-lifecycle | U3 | 예 | `~/.agents/skills/review-technique/perspectives/H9.md` | 소유자, 회수 경로, 남의 자원 | 변경이 컨테이너, 파일, 프로세스, 잠금, 임시 자원을 만들거나 지운다 | H9 |
| U3-external | U3 | 예 | `~/.agents/skills/review-technique/perspectives/L9.md` | 문서 근거, 실행 근거, 거부 결과 | 변경이 외부 명령, 라이브러리, API 를 부르거나 그 응답으로 분기한다 | L9 |
| U3-model | U3 | 예 | `~/.agents/skills/review-technique/perspectives/H11.md`, `~/.agents/skills/review-technique/perspectives/L10.md` | 호출 수, 판단 분리, 스키마 일치, 잘못된 출력 처리 | 변경이 모델 호출, 프롬프트, 출력 스키마, 출력 파싱을 더하거나 바꾼다 | H11, L10 |
| U3-interface | U3 | 예 | `~/.agents/skills/review-technique/perspectives/L14.md` | 종료값, 메시지의 대상과 원인, 기본값 | 변경이 CLI 인자, 설정, 기본값, 출력 형식, 오류 메시지, 종료값을 바꾼다 | L14 |
