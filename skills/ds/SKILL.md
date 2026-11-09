---
name: ds
description: Pre-contribution design planning. Identify the target repository's architecture as one known pattern, bring in that pattern's philosophy with sources, then decompose the user's intended work into responsibilities per architectural component. A read-only and web research procedure that writes no code. Use when the user calls /ds or $ds, or asks for design planning before starting to implement, add, or change a feature.
---
# ds

Before contributing to a repository, decide in which component of the current architecture, with what responsibility, the work should sit. The result is an implementation plan, not code.

## Constraints

Do not modify or create files. Do not commit, create branches or worktrees, or run tests, servers, DBs, or models. The only allowed actions are reading the repository (files, `git log`, `git ls-files`, search, definition and reference lookups with LSP or Serena), viewing issues and PRs, and web research. Report the result in the conversation, and leave it as a file only when the user asks.

## Evidence rules

Every claim in the result is paired with evidence. Do not write claims without evidence.

1. Write repository observations as locations: the base SHA, `file:line`, or the command run and the gist of its output. Do not use in the conclusion an observation whose location you could not state.
2. Cite sources per sentence for external concepts (pattern names, layer names, principles, quotations). Prefer the original source (the literature that first defined it) and the author's own material, and use blogs, summaries, and wikis only as leads to the original or as support. If you found only secondary sources, say so.
3. Separate origin from popularization. Confirm separately the person or literature that first defined the pattern, the one that named it, and the one that organized it for a particular field, and do not write the organizer as the creator, as in "X's pattern" (e.g. the Layers pattern originates in Dijkstra's THE system and Buschmann et al.'s POSA volume 1, and Fowler's PoEAA is the literature that organized three layers for enterprise applications).
4. Write names with the spelling found in the source. Mark industry aliases as aliases, separate from the formal name. Do not use a name whose source you could not find, or state "unconfirmed".
5. Do not write from memory. Search and confirm external concepts in this run before using them in the result, and check that the sentences of the search results match your own description. If sources differ, write the difference as is.
6. Mark claims as observation, source quotation, or inference. For an inference, write which observations and sources it came from.
7. If you find a counterexample or opposing literature that changes the conclusion, write it too. When correcting, state what was wrong and on what evidence it changed.
8. Research and include in the design document the grounds for every decision before publishing. Searching to answer only after receiving a question means preparation was insufficient, so run the expected questions and answers yourself before submitting the document, fill the gaps, and submit only when the document is self-contained.

## 1. Fix the work intent

Restate the work the user wants as functional requirements. Read the related issues, PRs, shared records, and user decisions to decide the target behavior, scope, and completion criteria. If the intent is unclear, ask before the architecture investigation.

## 2. Understand the architecture

Read structural information first and open bodies only at suspicious points.

1. Check the top-level package and directory layout, entry points, and process and deployment units (physical separation).
2. Check the import direction and dependency rules. Prefer the layer rules in check scripts, AGENTS.md, and design documents.
3. Check where the contracts between layers (interfaces, protocols, storage contracts, query files) are defined and who implements and calls them. If there are several implementations (backend, fake), list them all.
4. Check state ownership. Write in which component persistent state, in-memory state, and execution mechanisms (scheduler, queue, DAG executor) live.

## 3. Identify the pattern and its philosophy

Compare the observations of 2 with known architecture patterns and identify one. Candidate examples: Layers, Hexagonal Architecture (Ports and Adapters), Clean Architecture, Onion Architecture, n-tier, Pipes and Filters, Event-driven, CQRS, Microkernel. This list is a starting point for exploration, and each candidate's definition is confirmed by research.

1. For each candidate, find the original source and write, with sources, the defining features that distinguish that pattern (e.g. dependency direction, ownership of contracts and ports, whether skipping layers is allowed).
2. Compare those features one by one with the observations of 2 (`file:line`) and leave a table of matching candidates, rejected candidates, and the reasons for rejection. Exclude from the verdict candidates whose features you could not confirm, and say so.
3. Bring in the philosophy of the identified pattern from the original source: each component's responsibility, the dependency rules, what the abstraction hides, and the known costs. Write origin and organizing literature separately, and attach a source URL to every claim.
3. Write separately the points where the repository diverges from the pattern (mixing, intended variation, violation). Do not immediately conclude that a divergence is a defect; first confirm the intent with repository rules or decision records.

## 4. Decompose the work into responsibilities

Decompose the work of 1 into responsibilities per component, following the philosophy of 3.

1. Organize it in a table: component | responsibility in this work (what / how) | contract that changes | affected callers and implementations.
2. Place intent (what to do, business rules) separately from method (how to do it, storage, lookup, optimization). Prefer abstractions that hide behavior, and write the contract that results as their cost (the same meaning for the same input) and where to verify it.
3. Write where to put execution mechanisms (scheduling, retries, concurrency), separate from business rules.
4. If there is a contract change, list by search the callers and implementations across the whole repository (including other backends and test fakes) and write for each whether to change it and why.
5. If a choice that conflicts with the pattern's philosophy is needed, leave it, with alternatives, as an item for the user's decision.

## Result

1. Work intent and completion criteria
2. Architecture verdict: the identified pattern, the candidate comparison table (defining feature · source · repository observation location · verdict), and a summary of the philosophy
3. Divergences between the repository and the pattern, with the evidence location of each
4. The responsibility decomposition table and the list of contract changes
5. Items needing the user's decision, unconfirmed scope, and claims that rely only on secondary sources
6. Source list: separate original and secondary material, and write the claims each source supports. Write the base SHA.
