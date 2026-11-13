# Method: transactions, concurrency and recovery
Apply `~/.agents/skills/parallel-expert/SKILL.md` and the section `DM-Internals` of `~/.agents/skills/sql-expert/SKILL.md` to the plan.
1. Every multi-step write names its transaction boundary, and no other session can observe a half-done state the plan does not define.
2. Concurrent runs of the same work (two workers, a retry, a re-upload) end in one defined state: name the lock, unique key or idempotency key that guarantees it.
3. Every failure point (process crash, timeout, model or network error) between steps leaves a state the recovery path resumes from; name that path.
4. Ordering assumptions (A before B) are enforced by a mechanism, not by timing.
