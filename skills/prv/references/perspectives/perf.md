# Method: performance budget
1. List every hot path the design adds or changes (per request, per document, per candidate, per row): its query shape, model calls, embedding calls, and network round trips per unit.
2. Each hot path has a stated budget and a measurement on realistic data size (not test seeds), with the command (EXPLAIN ANALYZE, PROFILE, benchmark).
3. Per-row function calls inside search or batch queries are bounded and indexable; no per-id lookup scans a large table.
4. The feature's model-call work fits the stated time target (one existing LLM call time); identify calls that cannot change the outcome.
5. Comparison with main on the same input is planned for search score, upsert time and recovery where they are affected.
