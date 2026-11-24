# Follow-up questions

After verifying a round, the operator writes follow-up questions so the next round digs where the swarm was weak. Each question is one sentence or a short paragraph about one place, answerable by reading or running code at the head; it serves one perspective of `design/perspectives.json`, named by its id.

Write a question for each of these:

1. Each PLAUSIBLE cluster: the execution or tracing that would decide it (example: "Does any caller of `f` at the head pass an empty list, and what does `f` return then?").
2. Each CONFIRMED cluster: whether the same cause appears elsewhere (rv U5 propagation): the other callers, backends, fakes, prompts or documents that share it.
3. Each CONFIRMED or PLAUSIBLE cluster raised by only one task or session: the condition under which it occurs, so a second reading confirms or rejects it.
4. Each task whose `checked` rows name a decisive code location it did not open (a caller not listed, a file outside the breadth): a question naming that location and the perspective, so a session with tools reads it.
5. Each cluster whose cause spans changes in two perspectives' breadths: whether the other side holds the same assumption.
6. Each check that round 1 did not decide by its means (a `trace` check answered from the request alone, an `execute` check with no run): the place to follow or the input to run, so every check of the perspective is decided.
7. Each change with `structure.alters` true whose `high` perspective raised nothing and whose `low` perspectives raised a symptom of it: whether the symptom comes from the structure (example: "Do the other modules that compare this status string share the same assumption, and can a type enforce the status instead?").

A question may name the counter-argument the reviewer must also weigh (example: "check whether the exception is intended"), but it does not carry the operator's verdict, the cluster text, or other reviewers' suggestions. The operator writes the round's questions to `round-<k>/questions.json`, `[{"id": "Q1", "perspective": "K-3", "question": "..."}]`, and runs `bin/followup.py`, which gives each question one omp reviewer session with the brief below, the perspective as round 1 showed it, the question, the requirement copies, and the hunks of the perspective's breadth, and writes round 1's schema to `round-<k>/<unit>__Q<n>.json`. The reviewer reads only what the question needs and does not repeat the perspective sweep.

One session per question, launched together. In the first run the seven round-2 questions, one session each, reached 77.8% precision against 34.1% for the perspective sweep.

A question whose answer repeats a REJECTED suggestion is closed with the line that rejects it. No question is written about an OUT-OF-SCOPE suggestion.

## Follow-up brief

A follow-up reviewer is an omp session in the reviewer jail (`bin/reviewer.py`), so its brief fixes what it may read and do:

- Inputs: the request (the perspective, the question, the requirement copies, the hunks of the perspective's breadth) and the head, read-only at `/work` (code, callers, tests, `AGENTS.md` files and documents). Nothing else is mounted, and the head's git history is not reachable; the hunks show what the change removed.
- Report only defects inside the perspective and the scope of the change, as `references/brief.md` defines both.
- Find definitions, callers, and references with grep and glob on `/work`, and read each place you cite.
- When the question is decided by running, run the counterexample with `sandbox_run`, which runs a bash script on a fresh writable copy of the head with no network; drive the head's own code into the question's situation, with a fake for an external program or service that returns what its official documentation says. A finding that only a run decides and that you could not run says so and names the input to run.
- Every finding needs evidence checked in the code or in a run: the changed line and the location or output it conflicts with, as `file:line` at the head, with the verbatim line as its anchor.
- Write `condition`, `evidence`, and `fix` in Korean; `checked` holds what was checked and found satisfied, each with its location. End with one JSON object that matches the output JSON Schema at the end of the request, and nothing after it.
