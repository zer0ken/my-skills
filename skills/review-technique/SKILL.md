---
name: review-technique
description: "The review technique that rv, srv, and prv share: the fixed catalog of review perspectives (`perspectives/`, H1-H14 high and L1-L15 low), what a perspective is (core value, depth, picking condition, broken_if frame, breadth), how a repository's rules relate to the criteria, and the ten steps a review takes. rv, srv, and prv read it by path and add only how they automate it. It is not a review procedure of its own: a review request goes to rv, srv, or prv, never to this skill."
metadata:
  author: hrlee
  version: "1.0.0"
  domain: review
  triggers: review technique, perspective catalog, 리뷰 기법, 관점 목록
---

# review-technique

There is one review technique, and rv and srv are two ways to run it with AI. The user's words (2026-11-25): "Rv, srv는 둘 다 리뷰 기법을 스킬화 한 것인데, 그것을 ai로 엌덯게 자동화할지를 추가한거야." So the criteria live here once: the catalog (`perspectives/`), the definition of a perspective, and the steps below. rv (`~/.agents/skills/rv/SKILL.md`) runs them in one frontier-model session at the least cost, srv (`~/.agents/skills/srv/SKILL.md`) in many self-hosted sessions in the least time (the user, same day: "Rv는 단일 프론티어 모델을 쓴다는 가정 하게 완벽히 리뷰가 가능한 가는하면서 비용이 적게 드는 절차로 수행되여야 하고, srv는 완벽히 리뷰 가능하면서 가장 시간이 빠른 절차여야돼."), and prv (`~/.agents/skills/prv/SKILL.md`) applies the high perspectives to a plan before code exists. None of them keeps a copy of a criterion; a change to a perspective is made in its file here. The research behind the catalog and the steps is `~/agent-assets/rebot/REVIEW-TECHNIQUES.md` (sections 2-5), which cites each outside technique.

## Perspective

A perspective is a review yardstick fixed before any change is seen, and a review picks the ones its change needs; it never builds one. After a lead had let code build one perspective per value source, 266 of them on PR #1726, the user said (2026-11-24): "관점은 코드에서 찾는게 아니라 미리 정해진 검토 관점 중에서 코드 변경에 관련된 걸 고르는거다. 똑바로 해르". The earlier definition still holds for what a perspective is, a value-theoretic yardstick with a core value, a depth, and a breadth: "axiology에는 핵심 가치에 대한 정의, 그 가치를 검증할 깊이, 넓이를 한정하지 않으면 정교한 리뷰가 불가능해. 그래서 특정 PR에 있는 diff를 보고, 그 diff에 의해 일어나는 모든 변화를 커버할 수 있는 가치론적인 평가 잣대를 여러개 만들고, 그것이 내가 말한 "관점"이야" (2026-11-24). This skill reads the two together: the core value and the depth come from the catalog, and "만들고" is the review fixing each picked perspective's breadth and binding its `broken_if` to this diff, so that the picked perspectives' breadths together cover every change. That reading is a lead's, not the user's words.

| element | definition | what a review does with it |
| --- | --- | --- |
| core value | one property that must still hold after the change | fixed |
| depth | `high` (structure: concepts, data model, placement of responsibilities, module boundaries; wide and shallow) or `low` (behaviour inside functions: branches, boundary inputs, failure paths, single lines; narrow and deep) | fixed |
| picking condition | a condition that one element of the change set decides true or false (`Picked when`, and the `picks` code reads) | applied to the change set to pick |
| `broken_if` frame | the state, observable at that depth, that lowers the value, with 〈〉 slots | the slots are filled with this change's concepts, functions, and paths; the head's current expression is never copied in as the value |
| breadth | the change-set elements the perspective judges | fixed per picked perspective |

Depth is the level of abstraction at which the value is judged. When a lead answered "깊이가 뭔데" with read, trace, and execute (how far verification goes), the user said (2026-11-24): "하이레벨 로우레벨을 말한거다." The lists in the table that make the two levels concrete are a lead's expansion of that answer. Breadth and depth trade against each other, which is why there are perspectives at all (the user, 2026-11-24): "넓게 보려면 앝게 봐야돼. 좁게 보려면 깊게 봐야돼. 넓고 깊게 보라고 해봤자 어차피 못본다", "그러니까 관점이 필요한거라고". So a perspective has one depth and never asks for both; a value that breaks differently at the two depths is two perspectives (tests H12, H13, L11; concurrency H8, L7; storage H7, L6; model calls H11, L10). The boundary follows Orthogonal Defect Classification: a defect whose fix needs a design change belongs to a high perspective, one fixed inside a function or a local data structure to a low one.

Breadth is the set of changes a perspective judges, its horizontal span, from the change of one function to every file and backend the change touches. Asked "범위는 뭔대 그럼", a lead answered that breadth is that span, that depth is the vertical axis, and that R-004 of PR #1726 is caught only by a high-depth yardstick whose breadth covers all six queries, and the user confirmed (2026-11-24): "ㄱㄱ". So breadth is not bound to the units the diff was cut into for reading.

A perspective is a yardstick, not a persona. The user's words (2026-11-12): "전문 작업에서는 '역할극'이 아니라, 메소돌로지를 적용해야돼." Every catalog perspective names its sources.

## The catalog

`perspectives/<id>.md` holds one perspective per file: front matter `id`, `depth` (`high` or `low`), `picks` (the change kinds, `structure`, and change tags of `~/.agents/skills/srv/references/changes.md` that select it, the machine form of `Picked when`), and `execute: true` when only a run can decide it; then the title, `Value:`, `Picked when:`, `Broken if:`, and `Sources:`. The list is H1-H14 and L1-L15 of REVIEW-TECHNIQUES.md 4.2-4.3. It holds no rule of one repository and no product's usage: a repository's rules are read from that repository at review time and attached to the picked perspectives they refine.

## Criteria and the repository's constraints

The criteria, what counts as a defect, stay strict: the catalog's universal criteria and the repository's own both apply, the stricter where they differ, and a loose or missing repository rule never lowers a universal one. The constraints a repository puts on a review, its form, severity scale, numbering and reply conventions, and procedure, are respected: findings made on the strict criteria are written in the form the repository requires. This division comes from the project instructions of rebot, the tool that runs srv on review requests (its `AGENTS.md`, third paragraph).

## Steps

Each step says what it must produce; the automating skill decides who produces it and with how many calls.

| step | what it does | done when |
| --- | --- | --- |
| 1 Context | gather once the requirement copies, the repository documents on the changed paths, the callers of the symbols the change edits, the head lines naming what the diff adds, and the open issues, and place the same pack first in every request | the pack is written |
| 2 Change set | per reading unit, write each behaviour the change alters as an element, with the structure it alters or why it alters none | every hunk is in an element or declared behaviour-free with a reason |
| 3 Pick | apply each catalog perspective's picking condition to the elements; a perspective left unpicked keeps the reason that no element meets it | every element meets a picked perspective's condition, every structural element a high one's, every external contract an `execute` one's |
| 4 Fix the targets | bind each picked perspective's breadth and fill its `broken_if` with this change's names; a concept spread over many places goes to one high perspective whole; a low breadth stays under a cap | every element has a low perspective that holds it |
| 5 Inspect | one reviewer per perspective reads only its targets and writes, per check, the observations, the findings, and questions to other perspectives | every check has an observation |
| 6 Judge | per perspective, decide holds, broken, or undecided from the value, `broken_if`, and the observations only, never from the reviewer's conclusion | every perspective is judged |
| 7 Route | send each question and each undecided perspective to the perspectives whose breadth holds its target; collect what only a person can answer (H14's unrecorded decisions) | every routed question is answered |
| 8 Merge, high before low | settle the high findings first; a finding joins an earlier one only when it is on the same head line, has the same cause, and takes the same fix, and the joined finding stays visible as that cluster's duplicate | every finding remains or has joined |
| 9 Verify | a call other than the producer decides each remaining finding from the head lines and hunks: holds, rejected, or out of scope, out of scope only after looking for an open issue that promises it; a follow-up review marks each earlier finding resolved, unresolved, or unchecked | every remaining finding has a decision |
| 10 Verdict | a rule decides blocking, insufficient evidence, conditional acceptance, or acceptance, and lists the residual risk and the questions for a person | always |

Step 8's condition is the coordinator's definition of one cluster (2026-11-25, after merging hid findings with different causes on PR #1726): "같은 head 줄, 같은 원인, 같은 수정", and its order is the user's (2026-11-24): "계획 이후 리뷰는 병렬로 수행하되, 끝나고 하이레벨 -> 로우레벨 순으로 검토해서 중복 없는 지적사항만 남겨." There is no step that enumerates the same defect across the repository: OWASP separates that into a code scan apart from change review, and a review raises no finding where the change does not reach; the same cause inside the change is gathered by step 4's high breadth.
