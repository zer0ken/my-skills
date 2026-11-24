# Method: size, splitting, and reuse
Apply rv `~/.agents/skills/rv/SKILL.md` U1 items 4.1-4.4 and U3's paragraph on reuse and known implementations.
1. Count what the change adds (files, functions, public names, config keys, tests) from `git diff --stat` and the diff; report growth the requirement does not need.
2. (stake: returned_value, stored_data, state_and_ownership, failure_result, resource_use, interface_and_name) For each new unit, search the repository for an existing implementation and the standard library, existing dependencies, and platform features for a known one; report a hand-written duplicate with what it duplicates.
3. (stake: interface_and_name) Each new unit has a caller; report code without callers and old paths the change makes unnecessary but leaves.
4. The change bundles no independent purpose (a mechanical refactor mixed with a behavior change); name the boundary if it does.
