# Method: implementation cost
Apply rv `~/.agents/skills/rv/SKILL.md` U3's paragraph on implementation cost and `~/.agents/skills/prv/references/perspectives/perf.md` items 1-2 and 4-5, read for the code instead of a plan.
1. Each computation the change adds or changes, in code or inside a query, is named as its known problem type with the known algorithms for it and their complexity; one of higher complexity than a known algorithm that meets the same requirement is a finding whatever the current input size, such as an all-pairs medoid where the member nearest the centroid takes one pass.
2. List each hot path the change adds or changes (per request, document, candidate, row) with its DB round trips, model calls, and network calls per unit.
3. No work grows faster than the input where a dict, set, sort, batch call, or reuse of an earlier result would do.
4. No whole data set is built in memory where a streaming pass would do.
5. Claims of speed in the change are backed by a measurement on realistic data; report a claim without one as a verification gap, not a defect.
