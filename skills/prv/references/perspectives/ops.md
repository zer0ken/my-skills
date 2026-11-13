# Method: operations and lifecycle
1. For every stored state the design adds, list how it is created, changed, deleted, and what happens on each failure; every path ends in a defined state.
2. Document deletion, document re-upload/replacement, group changes, and direct database edits each have a defined effect on every new state.
3. Background tasks: kind, key, idempotency, duplicate suppression, retry limit, terminal failure state, and who observes it.
4. Existing databases: migration of existing rows and data written by earlier versions; whether a reload is required and how operators detect it.
5. Public contract (REST/MCP responses, config keys, schema): every change is listed with its effect on existing deployments.
