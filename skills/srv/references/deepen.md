# Follow-up questions

After verifying a round, the operator writes follow-up questions so the next round digs where the swarm was weak. Each question is one sentence or a short paragraph about one place, answerable by reading code at the head; it names the perspective method file whose items apply.

Write a question for each of these:

1. Each PLAUSIBLE cluster: the execution or tracing that would decide it (example: "Does any caller of `f` at the head pass an empty list, and what does `f` return then?").
2. Each CONFIRMED cluster: whether the same cause appears elsewhere (rv U5 propagation): the other callers, backends, fakes, prompts or documents that share it.
3. Each CONFIRMED or PLAUSIBLE cluster raised by only one task or session: the condition under which it occurs, so a second reading confirms or rejects it.
4. Each task whose `checked` rows name a decisive code location as not visible in its request (a caller not listed, a file outside the unit): a question naming that location, the unit, and the perspective, so a session with tools reads it.
5. Each cluster whose cause spans two units, since round 1 saw each unit alone: whether the other unit's side holds the same assumption.

A question may name the counter-argument the reviewer must also weigh (example: "check whether the exception is intended"), but it does not carry the operator's verdict, the cluster text, or other reviewers' suggestions. Each question file holds the question, the follow-up brief below, the perspective method file, the output path `round-<k>/Q<n>-result.md`, and a length limit for the output (140 lines in the first run). The reviewer reads only what the question needs and does not repeat the perspective sweep.

One session per question, launched together. In the first run the seven round-2 questions, one session each, reached 77.8% precision against 34.1% for the perspective sweep.

A question whose answer repeats a REJECTED suggestion is closed with the line that rejects it. No question is written about an OUT-OF-SCOPE suggestion.

## Follow-up brief

A follow-up reviewer is a session with tools, so its brief fixes what it may read and do:

- Allowed inputs: the change (`diff.patch` with its sha256, from the merge base to the head), the requirement copies, the project at the head (the head worktree: code, callers, tests, AGENTS.md files and docs; `git show <merge base>:<path>` shows a file before the change), the perspective method file, and the question. No other path under `~/.agents`, other worktrees, PR pages, or session logs.
- Report only defects inside the perspective and the scope of the change, as `references/brief.md` defines both.
- Find definitions, callers, and references with LSP or Serena first; text search supplements them for strings, config keys, SQL, and documents.
- Read; do not run tests, scripts, or the product. The operator runs the checks that decide a verdict.
- Every finding needs evidence checked in the code: the changed line and the location it conflicts with, as `file:line` at the head, with the verbatim line as its anchor.
- Write the answer in Korean to the output file named in the question: each finding with id, severity, `file:line`, anchor, condition and result, and fix; then what was checked and found satisfied, each with its location. End the turn with the finding count per severity and the output path. Edit no other file; no commits, pushes, PRs, issues, comments, or messages; do not start other sessions.
