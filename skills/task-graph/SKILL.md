---
name: task-graph
description: "Plan work that will take several turns as a directed acyclic graph (tasks as nodes, dependencies as directed edges) and schedule from it: start every ready task, overlap long waits with other work, and replan when results change the graph. Use when the user calls /task-graph, asks to plan or schedule a long task, or when starting work of medium difficulty that takes several turns but is smaller than a whole issue. Work at the scale of a whole issue uses my-workflow, and task-graph may be nested inside it. Do not use for work that finishes in one turn or for a single short chain of steps."
metadata:
  author: hrlee
  version: "1.2.0"
  domain: planning
  triggers: 작업 그래프, 태스크 그래프, 의존성 그래프, 작업 계획, 스케줄링, 긴 작업, 여러 턴, task graph, dependency graph, scheduling
---

# Task graph and scheduling

Plan the whole of a long task before starting it, and decide what to run next from the plan instead of from the order in which the tasks came to mind. Address the user in Korean using the neutral technical written-style rule.

The method connects two known techniques. The ready set comes from Kahn's algorithm for topological ordering, which repeatedly takes the nodes with no remaining incoming edges. The priority on the longest remaining chain comes from the critical path method, in which the longest chain of dependent tasks sets the shortest possible duration of the whole.

## Build the graph

1. List the tasks. A node is a task with one verifiable result: a file, a measurement, a decision, a passing check. Split a task only when the pieces can be scheduled differently, and merge steps that always run together.
2. Draw the edges. An edge from A to B means B needs A's result. Draw one only for a real need:\
  2.1 B reads an output of A.\
  2.2 A and B edit the same file or worktree, or load the same server, so they cannot overlap.\
  2.3 A is a decision or a check that fixes B's scope or can make B unnecessary.
3. Do not draw an edge for habit or listing order. A false edge serializes work that could overlap, and a missing edge causes rework.
4. Mark each node with what runs it (this session, a worker, a long run, CI, the user) and whether it waits on something external.
5. Check the graph: no cycle, every node reachable from the goal, and no node whose result nothing uses. A cycle means two tasks were cut in the wrong place; cut them again.

## Schedule from the graph

1. At each turn, compute the ready set: the nodes whose predecessors are all done. Start every ready node that does not conflict with another over files, worktrees, or servers, within the concurrency caps that apply to the session.
2. Start first the nodes on the longest remaining chain and the nodes with long waits (long runs, CI, workers, questions to the user), so the waiting overlaps with other work. While a wait is pending, work on ready nodes that do not depend on it instead of ending the turn idle.
3. Place a node that can invalidate later work, such as a feasibility check, a measurement that decides the approach, or a user decision, as early as its dependencies allow.
4. When a node finishes, record its result, recompute the ready set, and start the newly unblocked nodes in the same turn.
5. When a result changes the plan (a node fails, or a new task or dependency appears), update the graph first and then continue. Do not keep executing the stale order.
6. End a turn only when the ready set is empty and every remaining node waits on something that has a wake signal, or on the user.

## Keep the record

Keep the graph in a file that a later turn, a resumed session, or the session after compaction can read without rereading the conversation: the plan document, mirrored in a task list with dependency fields where the runtime has one. Above the table, write the goal in the user's wording, the user's decisions in their wording, and the completion criteria; do not change the criteria to match what was done. One row per node is enough.

| id | task | needs | runs on | waits on | status |
| --- | --- | --- | --- | --- | --- |
| T1 | Measure the baseline | - | long run | completion file | running |
| T2 | Read the existing design records | - | this session | - | done |
| T3 | Choose the approach | T1, T2 | this session | - | blocked |

Status is one of done, running, ready, and blocked. Update the row when the node starts and when it ends, and write the result or its path next to a finished node. When a finished node changed a repository, commit it with a message that says what was done, so that the record and the history agree.

After compaction or a resume, read the record first, together with the recent commit log when a repository is involved, and continue from it; the summary of the conversation does not replace the record. When compacting the session yourself, name the path of the record in the summary instruction. This is the note-taking practice for long-running agents: a progress record and the commit history let a fresh context window see the state of the work (Anthropic, "Effective harnesses for long-running agents").

## Report

Report progress from the record as done, running, ready, and blocked nodes, with what each blocked node waits on and which chain is currently the longest. When the graph changed during the turn, say which nodes or edges changed and why.

## With a workflow

Inside a staged workflow such as my-workflow, the stage order belongs to the workflow. The graph covers the tasks of the current stage only, does not reorder or skip stages, and does not start a later stage's task early.
