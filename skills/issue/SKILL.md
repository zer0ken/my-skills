---
name: issue
description: "Post an issue. Write the title as a noun phrase, and write the body as one bullet line per item, each labeled with its item name like `- **문제:**`, holding only those of the problem, the cause or presumption, the goal, and the plan that are needed, with the detailed explanation placed at the bottom of the body. Always apply the sucks skill to Korean prose. Use when the user calls /issue or instructs to post an issue (이슈를 올리라고 지시할 때)."
metadata:
  author: hrlee
  version: "1.9.0"
  domain: workflow
  triggers: 이슈, issue, 이슈 올려, 이슈 생성, gh issue create
  role: guardian
  scope: output
  output-format: action
---

# Issue

The author rereads the relevant global rules and project rules and confirms the scope of application.

## Prerequisite

Call `sucks` first with the Skill tool. Apply its rules to all Korean prose in the body.

## Metadata

Before creating, look up the repository rules and the actual choices on GitHub. Check `.github/ISSUE_TEMPLATE/`, `CONTRIBUTING`, the repository's `AGENTS.md`, and recent issues of the same kind, and confirm valid values with `gh label list`, `gh api`, `gh project list`, `gh project field-list`, and so on.

Make all of the items below into an internal checklist and judge each as `값` (a value), `해당 없음` (not applicable), or `사용자 확인 필요` (user confirmation needed).

- Labels
- Issue type
- Assignee
- Milestone
- Whether to include in a Project
- The editable fields of the Project

Use evidence in this order: an explicit request, the defaults of the issue form, repository rules, recent issues of the same kind. If the value to apply is not uniquely determined, ask the user before creating. Do not invent user or team ownership, release schedules, or priorities without evidence. Exclude computed fields and read-only fields from editing. For an issue being worked on, check the assignee the moment work starts, and add the user's account without removing the existing assignee.

Values that `gh issue create` supports, `--label`, `--assignee`, `--milestone`, and `--project`, are passed together at creation. Set the Issue type with the GraphQL `updateIssueIssueType` after looking up the available type IDs in the organization repository. Set Project fields by adding the issue to the Project and then running `gh project item-edit` with the item ID from the `gh project item-list` result and the field ID from the `gh project field-list` result. Choose the actual arguments from the `--help` of the installed `gh` version.

Right after creation, reread the general metadata with `gh issue view --json id,url,labels,assignees,milestone,projectItems`, the Issue type with GraphQL, and the Project fields with `gh project item-list`. Compare the pre-creation checklist with the actual values, correct any omission immediately, and look it up again. Do not silently drop a value that could not be set because of missing permission or `project` scope; report which item remains.

## Reader

The reader is a developer who works together in this repository. Write in the vocabulary they know and include only the minimum context needed to understand. Use domain knowledge and technical terms that already exist in this repository as they are, without explaining them. Respect the project's own rules (CONTRIBUTING, README, the repository's AGENTS.md, the existing issue and PR formats) above all. If a project rule and this skill's instructions conflict, follow the project rule.

The reader is not the user, not the user's agent, and not the session that is writing. A fellow developer who has not seen this conversation or the work record reads only the issue title and body and understands it. Do not use names that only the author, the user, or the agent session knows. Examples are the output file names of an experiment run, evaluation set labels (like `A 6,211쌍`), configuration labels (like `route-1500`), ledger seq, session ids, internal file names, and round names. Every proper noun, abbreviation, named number, metric, threshold, and method in the body must satisfy one of two conditions. One is that it already exists where a fellow developer can see it (the code and documents of this repository, a linked issue, a linked public source). The other is that the body explains it in plain words and states its source. The sentence above that says not to explain domain terms that already exist in this repository applies only to names that satisfy this condition.

Write in the order of title, body, and details, and finish with the pre-posting check.

## Title

The title is the name of the observed phenomenon or the requirement. Write it as a noun phrase whose last word is a noun. Do not put in a sentence-final ending (`~다`, `~습니다`), a nominalizing ending (`~함`, `~음`, `~하기`), or punctuation. Keep an identifier that distinguishes it from other issues in the same repository (an error name, an exit code, the target module).

When turning a sentence into a noun phrase, keep the object and change the predicate into the noun of that action.

| Sentence | Noun phrase |
| --- | --- |
| `20000건 동시 insert 시 벡터 인덱스 서버가 죽는다` | `동시 Insert 시 Segfault (Crash 30) 발생` |
| `git 저장소가 아닌 경로에서 scan 을 실행하면 git 원문 에러가 노출된다` | `git 저장소 밖 scan 의 git 원문 에러 노출` |
| `검색 응답에 키워드 점수를 추가하기` | `검색 응답의 키워드 점수 추가` |

If the repository requires a title prefix, keep that format and write the rest as a noun phrase.

## Body

Fill in the template below. One item is one bullet line, and that line ends in one sentence. Write the item name in bold like `**문제:**` so it shows which item it is. Use no bold other than the item names, and do not put in a `#` heading line.

```
- **문제:** 
- **원인:** 
- **목표:** 
- **계획:** 
```

Keep only the needed items, in this order, and delete the other lines. Do not repeat in the sentence what the item name already says. Do not end the `추정` item with `추정한다`, nor the `목표` item with `목표로 한다`. Do not split one content across two items. Do not stretch one item into two lines.

If you reference another issue or PR (`Refs #12`, a parent issue, a related PR, and so on), put that reference line at the very top of the body, leave a blank line, and then write the items.

| Item | What to write | When to use |
| --- | --- | --- |
| 문제 (problem) | The observed phenomenon | Always |
| 원인 (cause) | The confirmed cause | When the cause has been confirmed |
| 추정 (presumption) | A candidate cause | When the cause has not been confirmed. Do not use it when a cause is written |
| 목표 (goal) | The state to achieve by resolving the issue | When it is not self-evident from the problem sentence |
| 계획 (plan) | A direction of work that can be started right away | When the cause has been confirmed |

Do not use checkboxes (`- [ ]`). The body is the place to explain the issue, not to track progress. If it must be split into subtasks, write them at the bottom of the body.

When the cause has not been confirmed:

```
- **문제:** 20000건을 동시에 insert 하면 벡터 인덱스 서버가 종료 코드를 남기지 않고 종료된다
- **추정:** 세그먼트 병합 경로가 인덱스 락을 획득하지 않는다
- **목표:** 인덱스 서버가 20000건 동시 insert 를 종료 없이 처리한다
```

When the cause has been confirmed:

```
- **문제:** 20000건을 동시에 insert 하면 벡터 인덱스 서버가 종료 코드를 남기지 않고 종료된다
- **원인:** 세그먼트 병합 경로가 인덱스 락을 획득하지 않아 병합 중인 세그먼트를 다른 스레드가 해제한다
- **계획:** 병합 진입부에서 인덱스 락을 획득하고 동시 insert 재현 테스트를 회귀 테스트로 추가한다
```

## Details

End each item of the body in one line. Put everything that does not fit in one line at the bottom of the body: reproduction steps, logs, the course of the investigation, the grounds for a presumption, causes that were examined and ruled out, and the detailed steps of the plan. Leave a blank line so it is distinct from the bullet summary, and continue writing. Do not split the details into comments; put all of them in the single body.

## Issues written on the user's behalf

When the user entrusts the writing of an issue, write in the body only the requirements the user stated or decided (the problem, goal, scope, conditions). Design such as tool choice, implementation location, kind of test, scoring metric, and execution procedure is the assignee's to decide, so do not write it, and write the `계획` item only when the user decided the method. If the user stated a general principle, do not narrow it down to a concrete case you happen to know. Do not delete what was investigated on the way to the issue (tools, evidence, the relevant points of the current code); put it in a `참고` section at the bottom of the body so the assignee can choose.

## Issues for anti-slop malfunctions

When anti-slop flags a normal usage or its replacement suggestion is ungrammatical, do not just reword the text to get it through; leave an issue in the `graphai-repository/anti-slop` repository. Writing this issue is a standing instruction from the user, so it is an exception to the global instruction that an issue is made only when the user says so. Reproduce with the minimal input, and write the intended rule and the malfunction separately. Use the label `bug` and the Issue type `Bug`, and if it is the same class as an earlier closed issue, link it with `Refs #number`.

## Decision record

When the user decides a design or scope, do not leave the decision only in the conversation; also leave it as a comment on the linked issue. If the decision changes the design or the completion condition in the body, fix the body as well.

## Pre-posting check

Read only the title and body and check the following. If any one is off, write it again.

1. The last word of the title is a noun, and the title is distinct from other issues.
2. Each item is one bullet line and one sentence, and the same statement is not split across two items.
3. The `문제` item describes the observed phenomenon, not a solution or a cause.
4. There is no AI signature, no Generated with phrase, and no agent session URL.
5. List every proper noun, abbreviation, and named number, metric, threshold, and method in the body, and look each one up with `git grep` in this repository and in the bodies of the linked issues. For a name that is not found, explain it in plain words in the body and state its source, or replace it with the explained wording. If you cannot tell whether a name is one I attached in this work or one a fellow developer can see, treat it as a name I attached.

```bash
gh issue create --title "<명사구 제목>" --body-file body.md
```

Pass the body as a file. An inline string breaks across multiple lines. After posting, reread the title with `gh issue view --json title` to confirm, and if it is a sentence, fix it with `gh issue edit --title`.
