# The routed round

The team works the way Fagan's inspection meeting does: "Questions raised are pursued only to the point at which an error is recognized. It is noted by the moderator" (Fagan 1976, IBM Systems Journal 15(3)). An inspector that meets something it cannot settle inside its own perspective writes a question about the change it rests on (`questions`, `about: <unit>/E-<n>`). `bin/team.py` plays the moderator's routing in code, which is this skill's reading of Fagan rather than his words: after the judge has decided each perspective from round 1, it writes `round-2/questions.json` from two rules, the undecided perspectives first:

1. Each perspective the judge left `undecided` gets its own `broken_if` back, asking the inspector to look for that state at every change of its breadth and to report each place it looked.
2. Each question about a change goes to every other perspective whose breadth holds that change (an inverted index from change id to perspectives).

At most two questions go to one perspective, so the round stays one short session per question. `bin/followup.py` gives each question one omp session with the brief below, all launched together, and the judge then decides those perspectives again from round 1's and round 2's observations together. A question carries no verdict, cluster text, or other inspectors' findings, only the asking perspective's id and its question.

## Follow-up brief

A follow-up reviewer is an omp session in the reviewer jail (`bin/reviewer.py`), so its brief fixes what it may read and do:

- Inputs: the request (the review's shared context, the perspective with its `broken_if`, the question, the hunks of the perspective's breadth) and the head, read-only at `/work` (code, callers, tests, `AGENTS.md` files and documents). Nothing else is mounted, and the head's git history is not reachable; the hunks show what the change removed.
- Report only defects inside the perspective and the scope of the change, as `references/brief.md` defines both.
- Find definitions, callers, and references with grep and glob on `/work`, and read each place you cite.
- When the question is decided by running, run the counterexample with `sandbox_run`, which runs a bash script on a fresh writable copy of the head with no network; drive the head's own code into the question's situation, with a fake for an external program or service that returns what its official documentation says. A finding that only a run decides and that you could not run says so and names the input to run.
- Every finding needs evidence checked in the code or in a run: the changed line and the location or output it conflicts with, as `file:line` at the head, with the verbatim line as its anchor.
- Write `condition`, `evidence`, `fix`, and `result` in Korean; `checked` holds what you observed at each place you looked, as fact, not whether the value holds, because the judge decides that from the observations. End with one JSON object that matches the output JSON Schema at the end of the request, and nothing after it.
