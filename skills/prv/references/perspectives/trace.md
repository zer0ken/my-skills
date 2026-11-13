# Method: requirement-design traceability
1. Every requirement id and acceptance condition in N0 maps to a named design component or contract in N1; list unmapped ones.
2. No N1 statement contradicts an N0 statement (scope, behavior, error handling, schema).
3. Every concept N1 introduces has one name and a one-sentence definition that decides membership; the same concept is not called by two names; stored concepts state what one identifier denotes and which change creates a new one.
4. Every claim N1 makes about existing code ("currently", "base", "keeps", "unchanged") matches the code.
5. Every rule in the repository AGENTS.md files that the design touches is followed or the deviation is justified.
