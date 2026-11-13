# Method: queries, indexes and readers
Apply the sections `DM-Querying` and `DM-Processing` of `~/.agents/skills/sql-expert/SKILL.md` to the plan.
1. Every query the plan adds or changes has a stated shape (joins, predicates, aggregation) and, per access direction, the index or structure it uses; check that the index exists or is added.
2. Every stored unit whose meaning the plan changes (a table, column or relation, even when its shape stays) lists all its readers and writers across every backend's query text, tests and fakes; search the repository yourself and report a reader the plan does not list.
3. No query per item in a loop where one set query would do; no per-row function call or per-id lookup that scans a large table.
4. Results stay correct for NULLs, duplicates, empty sets and the visibility rules the repository already applies.
