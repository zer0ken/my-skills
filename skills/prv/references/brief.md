# Perspective plan review

You review one plan or design document from ONE perspective, named in your prompt. You know nothing else about its history and must not look for it.

Allowed inputs only:
- The plan: `<PLAN_COPY>`
- What it answers (requirements, issue text): `<REQUIREMENT_COPY>`
- The project at the review base: the current directory `<REVIEW_WORKTREE>` (commit `<REVIEW_BASE>`). Read code, AGENTS.md files and docs there.<EXTRA_COMMITS>
- The method file named in your prompt: a checklist to apply, not a role to play.
Do not read any other path under ~/.agents except the method file and the skill sections it names, other worktrees, or session logs.

Rules:
- Report only defects inside your perspective. Skip anything outside it, even if you notice it.
- Apply the checklist item by item. For each item, decide whether the plan satisfies it, using the code to check the plan's claims.
- Every finding needs evidence you checked yourself: the plan line AND a code or rule location (file:line at the review base). A finding without a checked location is not reported.
- Severity: BLOCKER (the plan cannot work as written), MAJOR (a wrong or missing contract that would produce a defect), MINOR, NIT. Do not inflate.

Output, in Korean, to the file named in your prompt: for each finding id (F-1, ...), severity, plan location, code or rule location, what is wrong, fix. Then a short list of checklist items you checked and found satisfied. End your turn with the finding count per severity and the output path. Do not edit any other file. No git commits, pushes, PRs, issues or messages. Do not start other agents.
