---
name: my-code-plan
description: "Plan every code change top-down as a tree of context depths, from depth 0 (the user story or requirement in the user's wording) down to depth N (the actual code changes), refining exactly one depth at a time, and pass the tree through the bundled checker before the first code edit. Use once per task whose purpose is to modify code, whatever its size or source: a one-line fix, a review finding, an issue, a script written during an investigation. Not for writing documents, notes, plans, or rules, and not per file write. 코드 수정이 목적인 작업이면 단위가 크든 작든, 리뷰 지적 수정이든 이슈 해결이든 조사든 그 작업을 시작할 때 한 번 사용한다."
metadata:
  author: hrlee
  version: "1.1.0"
  domain: planning
  triggers: 코드 계획, 코드 수정, 맥락 깊이, 탑다운 계획, 계획 트리, 리뷰 지적 수정, 이슈 해결, code plan, context depth, top-down plan, stepwise refinement
---

# my-code-plan

Plan a code change the way the user (이현령) plans it: start at context depth 0 and descend one depth at a time until every branch ends in a concrete code change. The user's words (2026-11-18): "이현령은 맥락 깊이 0부터 시작해서 탑다운으로 기획을 시작한다. 중요한 점은 0: 최상위 요구사항, N: 실제 코드 변경, 그리고 그 사이에 트리(그래프)처럼 내려가면서 한 깊이씩 계획을 구체화하는 것이다." and "맥락 깊이 0(최상위 유저스토리/요구사항) > 1 > 2 > ... > N. (충분히 구체화됨) 이 순서다." On when it applies (same day): "코드를 짜기 전에 반드시!!!! 이 스킬을 읽고 실행해야돼. 모든 코드 수정 전에는.", "단위가 크든 작든.", "리뷰 지적에 대한 수정이든", "이슈 해결이든", "조사이든.", "뭐든". The user's words on its scope (2026-11-18), after a hook had blocked every file write, documents included: "코드 수정이 목적일 때에 쓰라고" and "실제로 파일에 뭔가 쓸 때마다 하는게 아니라고".

Address the user in Korean with the neutral technical written-style rule (`~/.agents/skills/sucks/SKILL.md`).

## Concepts

| Name | Definition |
| --- | --- |
| context depth | The number of refinement steps between a node and the requirement it serves; depth 0 is the requirement itself. |
| node | One statement of the plan at one depth, with the observation that shows it holds. |
| refinement | The edge from a node at depth d to the nodes at depth d+1 that together make it hold. |
| leaf | A node that names one code change: a file, the symbol or region in it, the edit, and the test or observation that pins it. |
| plan tree | The nodes and refinements of one change, a directed acyclic graph rooted at depth 0, since one child may serve several parents. |
| computation | A node whose content is how a result is derived from data: a query, an aggregation, a selection, a ranking, a search, a numeric routine. |
| algorithm table | The record of each computation's choice: the problem it solves named by its known type, at least two known candidates with their complexity, the one chosen, and why. |

The method connects two known techniques. Stepwise refinement decomposes a task into subtasks in a sequence of refinement steps, each a design decision that makes the previous level more concrete (Wirth, "Program Development by Stepwise Refinement", CACM 14(4), 1971, https://doi.org/10.1145/362575.362577). Goal-oriented requirements engineering refines a goal into subgoals with AND-refinements, where a refinement is complete when its children together suffice for the parent (Darimont and van Lamsweerde 1996, as summarized in https://en.wikipedia.org/wiki/KAOS_(software_development) and the KAOS literature). From the first comes "one depth per step"; from the second come the completeness and necessity checks on each refinement.

## When

Run this skill once per task whose purpose is to modify code, before its first code edit: a one-line change, a review finding, a CI failure, an issue, a script for an investigation. It is a planning step of the task, not a step before each file write, and writing documents, notes, plans, or rules is not code modification. A change whose plan already exists extends that plan with the new requirement at depth 0 instead of editing outside it. Small changes produce small trees, not no tree: a one-line review fix is still depth 0 (the finding in the reviewer's words), depth 1 (the condition that must hold afterwards), and depth 2 (the edit and its test).

Inside a staged workflow such as my-workflow, the stage order belongs to the workflow; this skill is how the code of a stage is planned before it is edited. Scheduling the leaves over several turns uses `~/.agents/skills/task-graph/SKILL.md`, whose nodes are this tree's leaves.

## Depths

The number of depths is not fixed; descend until every branch reaches a leaf. A typical tree uses these depths, and each depth refines exactly one step of concreteness.

| Depth | What a node at this depth states | Grounded in |
| --- | --- | --- |
| 0 | The user story or requirement, quoted in the original wording (user, issue, reviewer). | The original message, issue, or review comment. |
| 1 | A completion condition: an observable state that must hold for the requirement to be met. | The requirement and the user's decisions; not the code in hand. |
| 2 | The behavior or component that produces the condition, placed in the architecture's known pattern, with its current state. | The code as it is, read with LSP or Serena, and the records that introduced it. |
| 3 | The contract the component needs: interface, data model, query, prompt, or schema, with the callers it touches. | The callers and write paths, listed by search. |
| N | The leaf: `path::symbol`, the edit, and the test or observation that pins it. | The contract above it. |

A node is concrete enough to be a leaf when an implementer can make the edit without a further decision and the check is something that can be run or observed. When a node at depth d would need a decision to turn into code, it is not a leaf; refine it.

## Procedure

1. Write depth 0. Quote the requirement in its original wording, with its situation. Do not paraphrase it into a solution. When the plan sets a target level for something measurable (time, accuracy, cost), set it at an absurdly high level, write it as achievable, and write next to it "나는 할 수 있다, 그것은 이론상 가능한 수치이다.", as the user's Philosophy requires.
2. Settle depth d before writing depth d+1. For each node at depth d, check its refinement from depth d-1:\
  2.1 Completeness: the siblings together make the parent hold. Name the observation that would show a gap.\
  2.2 Necessity: each node is needed by its parent. A node nothing depends on is removed, and so is what exists only to support it; prefer removal to addition.\
  2.3 One step: the node is exactly one step more concrete than its parent. A depth-1 condition that already names a function skipped a depth; split it.\
  2.4 Grounds: the node rests on what the "Grounded in" column names, checked at its source, and on existing practice for the same pattern in the codebase.\
  2.5 Algorithm: a node that specifies a computation, usually a contract at depth 3, has its row in the algorithm table before it is settled. Name the problem by its known type, list the formal definitions the requirement's words admit, and for each the known algorithms with their complexity in the input sizes, the platform's native features among them (a DB aggregate or index, a library routine); the one that first meets the definition is one candidate, not the answer. Choose the cheapest that meets the requirement and the user's decisions, and when candidate definitions give results that differ in a way the requirement cares about and its words do not decide, ask. A small current input does not keep a higher-complexity candidate. The case (2026-11-20): "embedding 기준으로, 묶인 정보 중 중앙에 있는 것을 대표로 삼자" was built as an all-pairs medoid, O(m²), where the member nearest the centroid takes O(m) and is the member with the least sum of squared distances; the user asked "Centroid 몰라?" and "왜 이런 알고리즘을 말 안하면 안쓰는거야?".\
  Then mark every node at depth d `settled`. Only then write depth d+1 as `draft`.
3. Descend until every branch ends in a leaf. A leaf names one change; a rename across files is one leaf per file.
4. Run the checker and fix what it reports until it prints the approval line:\
  `python3 -I ~/.agents/skills/my-code-plan/bin/check-plan.py <plan file> --repo <repository or worktree root>`\
  Keep the plan file outside the repository, in the work artifact directory, so it is not committed by accident.
5. Edit only what the leaves name. A needed edit that no leaf names means the tree has a gap: add it under the node it serves, from the highest depth that changes, and run the checker again.
6. When a problem appears during or after the edit (a failing test, a review finding, a wrong result), trace it up to the highest node whose content caused it, fix that node, and rewrite every node under it. A fix at the leaf where the problem surfaced is not a fix.

## Plan file

The plan is a Markdown file with one table under the heading `## Plan tree`. Above the table, write the goal in the user's wording and the user's decisions, each with the situation it answered.

| id | depth | parents | node | check | code | status |
| --- | --- | --- | --- | --- | --- | --- |
| R1 | 0 | - | "로그인 실패가 5번이면 잠근다" (issue #12) | the issue's acceptance criteria hold | - | settled |
| C1 | 1 | R1 | The fifth failed login within 10 minutes locks the account | test of the fifth failure | - | settled |
| B1 | 2 | C1 | `AuthService.login` counts failures per account | unit test of the counter | - | settled |
| L1 | 3 | B1 | Increment and check the failure count in `login` | `test_auth.py::test_fifth_failure_locks` | `src/auth/service.py::AuthService.login` | settled |
| L2 | 3 | B1 | Add the count column | migration test | `new:migrations/0012_failure_count.sql` | settled |

Below the tree, the heading `## Algorithms` holds the algorithm table, one row per computation node. The example row below belongs to another plan, whose leaf L1 picks a merged group's representative.

| node | problem | candidates | chosen | grounds |
| --- | --- | --- | --- | --- |
| L1 | 1-medoid of a group's m embeddings of dimension d | sum of distances medoid: O(m²·d); nearest to centroid: O(m·d) | nearest to centroid | It is the member with the least sum of squared distances (Σⱼ‖xᵢ−xⱼ‖² = m‖xᵢ−c‖² + const), which meets "중앙에 있는 것" in one pass. |

`candidates` separates entries with `;`, each `<name>: <complexity>` with a big-O bound, and `chosen` is one of the names. A plan with no computation writes, under the heading, the one line `none: <reason>`, such as `none: the change renames a column`.

The columns of the plan tree are fixed: `id` is unique, `depth` an integer, `parents` the comma-separated ids at depth - 1 (`-` at depth 0), `check` the observation that shows the node holds, `code` `-` for an inner node and `path` or `path::symbol` for a leaf, relative to `--repo` or absolute when the change spans repositories (`new:` before a file the change creates), and `status` `draft` or `settled`.

## Checker

`bin/check-plan.py` enforces the structure: unique ids, a depth-0 root, parents exactly one depth up, no draft depth above a deeper one, a check on every node, children for every inner node, no children under a leaf, leaves at depth 2 or deeper, leaf paths that exist (or, with `new:`, do not yet exist) under `--repo`, and an `## Algorithms` section that is either `none: <reason>` or rows naming a tree node, a problem, at least two candidates each with a big-O bound, a chosen candidate, and grounds. On success it prints `approved: <absolute path>` per leaf and the line `my-code-plan: plan OK`. The checker cannot judge completeness, necessity, grounds, or whether every computation has its row and the candidates are the known ones; step 2 does. `bin/test_check_plan.py` pins the algorithm-table check; run it after changing the checker.

## Report

When reporting a plan, show the tree from depth 0 down with the algorithm table, mark which depths are settled, and name the leaves still unedited. When a node changed after a problem, say which node it was, why it was the highest cause, and which nodes under it were rewritten.
