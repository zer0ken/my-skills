# Method: backend equivalence and storage contract
Apply the storage-contract parts of `~/.agents/skills/sql-expert/SKILL.md` (`DM-Modeling`, `DM-NoSQL`) to the plan.
1. List every storage backend the repository supports for the touched data; the plan states the change for each, or why one is unaffected.
2. Each backend enforces the same constraints (keys, uniqueness, cascades, triggers or their equivalent) and returns the same shape to callers, including test fakes.
3. A mechanism the plan uses on one backend (a trigger, a view, a function, a type) exists on the others, or the plan names the equivalent.
4. Migrations and existing data are covered for every backend.
