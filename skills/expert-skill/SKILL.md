---
name: expert-skill
description: Draft or revise an `-expert` skill by researching how a field defines its own expertise, and propose it to the user. Use when work meets a field that has no `-expert` skill, when the user calls /expert-skill or asks for a new or revised expert skill, or when an existing `-expert` skill must be checked against its sources.
metadata:
  author: hrlee
  version: "1.0.0"
  domain: harness
  triggers: 전문가 스킬, expert skill, 새 분야, 전문성
---

# expert-skill

An `-expert` skill (`sql-expert`, `llm-expert`, and so on) holds a field's expertise so that any agent working in that field applies it. This skill is how such a skill is made and kept true.

The user's words (2026-11-12), in order: "정리하자면, 전문 작업에서는 '역할극'이 아니라, 메소돌로지를 적용해야돼.", "스킬 자체는 작업에 대한 메소돌로지가 아니라, 전문성에 대한 메소돌로지여야 한다는 거야.", and "전문성의 방법론은 니가 정하는게 아니다. 학계가, 사람들이, 세상이, 사회가 정하는거야."

## What an `-expert` skill is and is not

1. It is the field's expertise as the field itself has settled it: how the field frames its problems, its principles and theories under their own names, the criteria it uses to tell sound work from naive or vague work, its named anti-patterns, and its procedures for diagnosing a bad result. Every claim carries a citation to a source of the kind listed below.
2. It is not a procedure for one kind of task. Request rewriting, approval steps, and report formats belong to the instructions and to `my-workflow`, and the skill does not repeat them.
3. It is not a character to play. A persona sentence, an expert's tone, and knowledge written from recall are not expertise; content without a source is not carried over, including from an earlier version of the skill.
4. The structure of the skill is taken from the field too. Do not impose a frame of your own; take the sections from how the field organizes its own knowledge, such as the knowledge areas of a body of knowledge or the parts of a standard curriculum or textbook.

## Sources

Take expertise only from what the field has settled, found by search through the `prior-research` skill, and record for each source its URL, the section read, and a quoted sentence.

1. Bodies of knowledge and curricula published by the field's professional or academic bodies.
2. Standard textbooks and reference works, and survey papers of the field.
3. Standards and specifications.
4. Official documentation of the products the field uses, for product-specific guidance; the skill tells its reader to confirm the actual product and version of each piece of work and to read that version's documentation, because a version fixed in the skill goes stale.
5. Practice literature the field itself recognizes, such as widely cited guides and catalogs of anti-patterns, with the reason it counts as recognized.

Model-generated titles, numbers, and URLs are leads, not sources, until found again by search. When sources conflict, write both with their citations and the condition under which each holds. A part of the field for which no source was found stays in the skill as a heading marked unsurveyed, not filled from recall.

## Procedure

1. Name the field and its boundary: what work loads this skill and which neighboring field's skill takes over at the edge.
2. Find how the field defines its expertise and take the skill's sections from it.
3. Fill each section from the sources with citations, including the field's terms for naive and for undefined or blurred structure, so the global rule against such work has the field's own criteria to apply.
4. Check every citation mechanically: fetch each URL and confirm that the quoted sentence is on the page. Remove or mark claims whose quotation is not found.
5. Write the `description` from the work that should load the skill, so agents load it on their own when such work appears.
6. Propose the draft to the user with its source list and its unsurveyed parts. Proposing does not create it; after the user decides, deploy it by the my-skills procedure of the `harness` skill.
7. When revising an existing `-expert` skill, rerun 4 on the whole skill and record which claims changed and on what source.
