---
name: response-rv
description: "Respond to findings on your work in five ordered stages (understand, root cause, decide, act, reply), leaving a completion record per stage so the work survives compaction and can be shown at once when asked whether it was done properly. Use when a review (a person's, or an rv, srv, or prv result), a review comment, a gate verdict, or a user's criticism of a delivered artifact points out something wrong in your work and asks for a change (리뷰·코멘트·게이트·사용자 지적에 대응할 때), and when asked whether a response round was done properly (지적 대응을 똑바로 했냐고 물을 때)."
metadata:
  author: hrlee
  version: "0.5.1"
  domain: workflow
  triggers: 리뷰 대응, 지적 대응, 리뷰 회신, review response, 근본 원인, 스펙 수정
  dependencies:
    - pr
    - sucks
---

# response-rv

The user's words (2026-11-16), after a lead answered "아니오" to "각 지적에 대한 근본 원인을 전부 분석했어?" on fifteen review findings it had already triaged and drafted replies for, while the same cause had recurred in two self-review rounds: "지적에 대해 대응할때는, 그 지적에 대해 올바르게 이해하고, 근본 원인을 분석하고, 어떻게 대응할지 결정하고, 실제로 대응한 뒤에, 답변을 만들어야돼. 이것을 rv같은 기존 스킬이 아니라 별도 스킬로 분리하고, 각 단계는 오래 걸리고 컨텍스트 압축이 일어날 수 있으니, 각 단계를 올바르게 수행했다는 것을 문서로 작성해서 보존하고, 아까처럼 내가 똑바로 한게 맞냐고 물어볼 때 그것을 즉시 제시 가능하도록 작업해야돼. 이 파일은 클린업때 정리될 수 있어".

## Concepts

A finding is one claim, made by someone other than the producer at that moment (a person's or agent's review, including an rv finding, an srv or prv cluster, a review comment, a gate verdict, the user's criticism of a delivered artifact), that something in the work is wrong and asks for a change. A claim outside the scope of the work is not a finding either, even when it arrives in a review: the scope is the promise of the issue the work resolves and of its PR, as rv's `## Scope of a finding` (`~/.agents/skills/rv/SKILL.md`) defines it, and a claim is outside it when it points at a problem that exists the same at the base and that the promise does not ask to fix, or at a problem another open issue already describes. The user's words (2026-11-18), while a lead answered a design gate whose findings included one the lead matched to an open issue: "이미 열린 이슈가 있는거면 억지로 해결하지 말것", "이미 열린 이슈가 있는 문제라면 이 PR에 대한 지적으로 삼지 말것", and "즉, 범위를 벗어난 지적을 내지 않아야 하며, 그것이 나오더라도 범위를 벗어났으면 지적으로 인정하지 말아야 한다." A question that only asks why you did something is not a finding: answer it first as the instructions require, and if the answer shows a change is needed, that change becomes a finding here. A round is the set of findings that arrived together, such as one submitted review or one gate verdict, and is answered together. A stage record is the file a stage leaves for the whole round: one section per finding, and a completion check that says which of the stage's criteria hold, with evidence. The round index is the one file that shows, per finding, which stages are complete, and is the first thing to show when asked whether the response was done properly.

## Stages

Run the stages in order for the whole round. A finding enters a stage only when its section in the previous stage's record is complete, and a stage record is complete only when its completion check holds for every finding. A finding may close a stage in one line when that line is enough, as for a typo, but no finding skips a stage. Write each record with the file-writing tool as you go, not after the fact, and update the round index when a stage completes.

### 1. Understand (이해)

For each finding, write its original text verbatim with its source link, then restate in your own words the condition it claims and the result it claims, and what it asks for. Read the primary sources the finding relies on (the code at the reviewed head, the contract, the rules, the measurement) and write the paths and lines read. Classify the claim as 사실, 부분 사실, 사실 아님, or 불명, each with the evidence kind 재현, 관찰, or 추론. A finding whose meaning has two readings is 불명: write both readings and the question that would settle it, and do not pick one; it waits at this stage and its reply asks that question.

Then place each claim against the scope: search the repository's open issues for the problem it describes (`gh issue list --state open --search "<terms>"`) and compare the code it points at with the base. A claim outside the scope is marked 범위 밖 here with the open issue, or the base line that shows the problem exists the same before the work, and is not handled as a finding: stage 2 closes it in one line, stage 3 decides 범위 밖, stage 4 changes nothing for it, and its reply says it is outside the scope, with that issue or evidence.

Completion check: every finding has the verbatim text, the restatement, the sources read with paths and lines, a classification with its evidence, and its place against the scope, with the open-issue search run for it.

### 2. Root cause (근본 원인)

For each finding classified 사실 or 부분 사실, write the whole causal chain in one place, as the instructions define it for "문제가 뭐냐": the symptom, each cause of the cause in turn, up to the root cause, the highest node whose content caused it (the reading of the goal, a completion condition, a component's design, a plan or spec node, a procedure), then your own procedural error that let it through (which step or check should have caught it, and why it did not), and the links you did not check, each marked 미확인. A chain that stops at the line the finding points to is not a root cause.

Then name the one layer the root cause sits in, because the fix belongs in that layer and nowhere else:

1. 명세: the specification the work implements, meaning the document or contract that states what the code must do, such as the issue's completion conditions, a design document, or a section like `tests/TESTING.md`, states the wrong behavior, or is silent where the finding's condition needs a rule.
2. 구현: the specification states the right behavior and the code departs from it.
3. 시험: the specification and the code are right, and the test or check fails to pin that behavior or pins a wrong one.

Decide it by comparing the finding's expected behavior with the specification first: quote the sentence that governs the condition with its path and lines, or show its absence with the search that found nothing, then compare the code and the test against that sentence. Then write the smallest region whose change removes the root cause, by section and lines of that layer, and the layers below it the change must reach (a 명세 change reaches the implementation and the test that follow it, a 구현 change reaches the test). A region larger than the cause, such as a redesign around it, and a region in a lower layer than the cause, such as code changed to cover a specification that still permits the defect, are both wrong; the second is a symptom fix, because the next implementer reads the unchanged specification and reproduces the defect. The user's words (2026-11-17), before a lead answered seven independent-review findings on a test-runner PR, two of which it traced to the test-run lifecycle rules in `tests/TESTING.md` rather than to the code (typos corrected): "리뷰 지적에 대해서 대응 할 때는 단순히 대증치료가 아니라 원인을 찾아서 필요하면 코드가 아니라 '스펙'을 고쳐야 될수도 있어.", and, on making this a skill rule: "스펙을 수정해야될수도 있다고" and "그리고 애초부터 분석할 때 스펙이 문제인지, 그에대한 구현이 문제인지, 그에 대한 테스트가 문제인지, 뭐가 문제인지 딱 짚어서, 수정 가능한 최소 영역을 찾으란말이야."

For a finding classified 사실 아님, write what led the reader to the claim, such as a misleading name, document, or PR text; when that is on your side it is the cause to fix, and otherwise write `원인 없음` with the evidence.

Then group the findings by shared root cause, and for each root cause search for the other places it produced the same defect: elsewhere in the diff, the codebase, the documents, and earlier rounds of this work. Write the search commands or queries and their results, so the absence of other places is shown, not claimed.

Completion check: every finding has a chain ending at a named node or a stated `원인 없음`, every root cause names its layer (명세, 구현, or 시험) with the governing specification sentence or the search showing its absence, and the smallest region to change with the layers it reaches, every chain names the procedural error or says why there was none, unchecked links are marked, and every root cause has its same-cause search with results.

### 3. Decide (대응 결정)

For each finding, decide 수용, 부분 수용, 기각, 질문, or 범위 밖, with grounds checked against the primary sources of stage 1, and for 부분 수용 say which part. 범위 밖 is the decision for every claim stage 1 placed outside the scope, and only for those: the work does not fix it. When an open issue already describes the problem, it is left to that issue and nothing is drafted; when none does and the claim is 사실 or 부분 사실, draft the issue that would promise it and bring it to the user, as the instructions require for a problem found outside the scope. For each accepted root cause, the fix lands on the smallest region stage 2 named in the layer stage 2 named, and propagates down to every node under it and to every same-cause place found in stage 2; a fix only at the leaf the finding pointed to is not a fix of the root cause. A 명세 cause is fixed in the specification first, then the implementation and the test are changed to follow the new text; a code-only change for it is the symptom fix stage 2 describes.

Before choosing how to fix, ask of each accepted finding whether the code or artifact it points at needs to exist at all, as the instructions' rule on solving a problem by removal before addition requires, and write the answer: the requirement, contract, or caller that depends on it with the path or record that shows it, or that nothing does. When nothing does, the fix is to delete it and what exists only to support it. A fix that adds code, a guard, a check, a branch, an option, a test, or a rule is chosen only after removal or simplification is shown not to solve the root cause, and the record says why. The user's words (2026-11-17), as a general instruction on handling findings: "지적을 받으면, 지적을 받은 코드가 정말 꼭 필요한 것인지 확인해. 없애버리면 지적받을 일도 없어." and "모든 것을 추가해서 해결하려고 하지마".

Then place each fix:

1. Within the promise of the issue and PR: decide the change.
2. Outside that promise: when an open issue already promises it, leave it to that issue; otherwise draft the issue that would promise it and bring it to the user. Do not slip it into the current change.
3. A public contract change (REST and MCP responses, DB schema, config keys) or a structural change: ask the user, or, inside a procedure that owns redesign, go back to its design stage.
4. A procedural error whose cause lies in my-harness or my-workflow: hand it to a modification session as the `harness` skill describes; one that lies in the project's rules: propose the rule change within that repository's procedure.

Completion check: every finding has a decision with grounds, every 범위 밖 decision names the open issue or the base evidence and the issue draft when one is needed, every accepted finding records whether the thing it points at needs to exist, every fix that adds something records why removal does not solve it, every accepted root cause has its fix region in the layer stage 2 named and its propagation, every 명세 cause has a specification change, every same-cause place has a disposition, and every fix is placed by the list above.

### 4. Act (대응 실행)

Carry out the decisions and record, per finding, what was actually done: the commits (short SHA, linked when pushed), the files and documents changed, the specification sections changed with their new text, the root-node edits, the same-cause places fixed, the issue drafts and handoff ids, and the verification run with its command and the last line of its output. Write what was not done and why, and verification not run as not run. Before leaving the stage, check that the diff covers every accepted decision and every same-cause place, mapping each to its commit.

Completion check: every accepted decision maps to a change that exists and was verified, every not-done item says why, and no claim lacks its evidence path.

### 5. Reply (답변 작성)

Write the reply only from the records of stages 1 to 4, in the form and place the `pr` skill's review-response section sets: a formal review answered in the repository's response form, a colleague's prose answered in prose, the whole round delivered as one review. Per finding, say what was accepted and changed with its commit, the layer the cause sat in, and when it was the specification, the specification change and the implementation and test that followed it, the root cause when it changed more than the line pointed to, including the same-cause places fixed, the grounds of a rejection, the open issue or base evidence that places a 범위 밖 claim outside the scope, and the question of a 불명 finding. Apply `sucks` to Korean prose. Do not link or name the stage records in the reply; they are local working files, and the reply carries their content in plain words. After posting, write the review link in the round index.

Completion check: every finding is answered, every statement in the reply traces to a stage record, and the posted review link is recorded.

## Records

Keep a round's records in one directory:

1. Inside a procedure that keeps its own run directory, such as a my-workflow run, under that run's artifacts as `<run root>/artifacts/<PHASE>-response-<round>/`, where `<PHASE>` names the step the findings belong to, such as the task id `T4` or `GATE`, and `<round>` counts the rounds of that PR or gate from 1. The procedure's own response artifact, such as a review-response JSON, keeps its schema and points its evidence at these records.
2. Otherwise under `~/.agents/responses/<session>/<NNN>-<target>/`, where `<session>` is the first eight characters of the session's own Paseo agent id (confirm it is your own, because `PASEO_AGENT_ID` can name the session that launched you) of `ORCA_AGENT_SESSION_ID` in Orca, or of the agent product's session id outside a runtime, `<NNN>` is the next three-digit number in that directory, and `<target>` is a short ASCII name such as `pr1412-r1`.

The directory holds `0-index.md`, `1-understand.md`, `2-cause.md`, `3-decide.md`, `4-act.md`, and `5-reply.md`. Each stage record starts with `## 완료 확인`, a table of the stage's criteria with 충족 or 미충족 and the evidence, then one `## <finding id> <short title>` section per finding. `0-index.md` names the target (repository, PR or gate, the round's source link, the head the findings were made on), lists the root causes of stage 2 in one line each, and holds one table with a row per finding and the columns 지적, 1 이해, 2 원인, 3 결정, 4 실행, 5 답변, each cell 완료, 진행, or 대기 with the reason.

These records are the context of this activity: a context note written at a switch into or out of a stage points to the round index instead of copying it. After a compaction or a resume, read `0-index.md` and the record of the stage in progress, and continue from what they hold, not from the conversation summary. Do not redo a stage whose completion check holds unless new evidence contradicts it.

## Answering whether it was done properly

When the user asks whether a round, a stage, or a finding was handled properly, as in "똑바로 했어?" or "근본 원인을 전부 분석했어?", read `0-index.md` and the stage record asked about before answering, then answer from them with the link to the record: which stages are complete for which findings, and what is missing. If a stage is incomplete or was skipped, say so first, then complete it.

## Cleanup

The records are working files. At cleanup, the `cleanup` skill decides each round directory: preserve it when it holds context that outlives the session and that the PR, its reviews, the commits, or the issue do not already carry, such as an unresolved root cause awaiting a follow-up issue; delete it otherwise. Records inside a run directory follow that procedure's finishing rules.
