---
name: problem-modeling
description: "Define the problem mathematically before choosing a solution. Name it with a known problem type, fix inputs and outputs as symbols, and document the core subproblems with their boundary cases, constraints, evaluation metrics, and out-of-scope items. Use when the user calls /problem-modeling, asks for a problem's definition, input, or output, or when two or more fix attempts on the same defect have failed and the problem must be redefined."
metadata:
  author: hrlee
  version: "1.2.0"
  domain: workflow
  triggers: 문제 정의, 입력 출력, problem modeling, 수학적 정의, 문제를 정의해
---

# Problem Modeling

Define the problem before deciding on a solution. Without a definition, fixes that block one symptom (surface rules, wording patches) repeat, and there is no criterion to judge whether a fix was right. This skill produces one document, `PROBLEM-<identifier>.md`.

## Preconditions

1. Reread the project rules (AGENTS.md, CLAUDE.md, design documents) and the criteria the user set. Copy user decisions in their original wording and do not mix them with your own judgment.
2. Confirm observed defects with raw output, logs, and real data cases, not summaries or labels. Pick one real case and use it as the example that runs through the whole document.
3. Apply the `sucks` skill to Korean prose.
4. When this skill is invoked because two or more fixes for the same defect failed, attack their premise before defining anything else.
  4.1 Write down the premise: the one sentence every failed fix assumed.
  4.2 Test it directly. Find an observation that would come out differently if the premise were false, and make it. Look at how the failures are distributed across cases, not only at how large they are, and keep the check rerunnable.
  4.3 If the evidence contradicts the premise, the cause is elsewhere; look for what the failures share that the premise did not predict. If it confirms the premise, ask the next "why", because the earlier fixes may have treated a consequence.
  4.4 Remove the condition that produces the failure instead of adding a mechanism that compensates for it after the fact.
  4.5 Do not start the next fix until the premise is written down and tested. Record the premise and the test result in the definition document.

## Procedure

### 1. One-line definition and problem type

Define the problem in one sentence and name it with a known problem type (e.g. coreference resolution, set partitioning, shortest path, classification, ranking, scheduling). If you narrowed or varied the type, write what you reduced (e.g. "not full coreference clusters; each anaphor needs only one antecedent sentence number").

Research the problem type and existing solutions on the web with the iterative search of the `prior-research` skill, not from local code. Find papers, benchmarks, and widely used implementations and keep source links. If the conditions existing research assumes (allowing source rewriting, language, dependencies) differ from this project's constraints, write the difference.

### 2. Input

Fix the input as symbols. Map each symbol to an actual data type or function output in the code (e.g. "document D: the source sentence sequence s1 … sn after `split_sentences`"). List every piece of side information already in the input (structure, context, exclusions).

### 3. Output

Fix the mathematical structure of the output (partition, graph, function, ranking, set). Write from what and how the output is determined (e.g. "the partition is the connected components of edge set E"). If the output is the input of a later stage, write which properties of the output that stage relies on.

### 4. Core subproblems

Define separately the functions or judgments, not yet solved, that are needed to determine the output (e.g. a(m): the antecedent sentence number of anaphor m). Always include the following.

1. Define what the elements of the domain are, with examples.
2. Define what the values are.
3. List every boundary case where the value becomes "none". If boundary cases are missing, the solution and the answer set solve different problems.

### 5. Conditions

Number the conditions a solution must satisfy. Separate functional conditions (self-containedness, minimality, etc.) from project constraints (source preservation, layer boundaries, supported languages, call count, speed). Attach grounds (issue, user decision, rule document) to each condition. If conditions conflict, write their priority.

### 6. Relation to other defects

If other defects in the same symptom cluster depend on this output, write what happens to them when this definition is satisfied. This relation decides scope and work order.

### 7. Evaluation

Define metrics computable from the output and the answer key alone. Include accuracy (recall, precision, F1, etc.) and cost (time, tokens, call count, downstream workload) together. Keep the following.

1. Write who made the answer set by what criteria, and keep the generation script and file path.
2. Split development cases from evaluation cases and report them separately. Do not put evaluation-case sentences or answers into prompts or product code.
3. If the answer criterion is close to the solution's rules, write that limitation.
4. Set the number of repetitions for elements that make measurement fluctuate (model judgments).
5. Name what, other than the producer of the solution and its own report, shows that the result is right: an answer key made independently, a downstream consumer's check, a reviewer from another model family, or a measurement on real data.

### 8. Out of scope

Write the adjacent problems that are not part of this problem, and for each, which stage or issue is responsible.

### 9. Solution structure (after the definition)

Write the solution only after finishing the definition. Map each part of the solution to the subproblem of the definition it handles, and justify that placement with the research grounds of 1. Separate the parts that rules can judge, the parts deterministic analysis (parsers, part-of-speech analysis, etc.) handles, and the parts a model handles, and leave the model only questions whose output space is small and that code can verify.

## Document format

Put `PROBLEM-<identifier>.md` in the work artifact directory. The section order is definition, input, output, core subproblems, conditions, relation to other defects, evaluation, out of scope, solution structure. If there is a plan document, point to this document from the head of the plan document.

## Prohibitions

1. Do not use solution terms (a specific model, library, regular expression) in the definition section.
2. Do not write a definition fitted to one symptom case. The definition must cover the distribution of all cases.
3. Do not use invented examples. Examples are real data or sentences of the same shape as that data.
4. Do not write unmeasured properties as if the condition were met.
