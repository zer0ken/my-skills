# Method: requirement-design traceability
1. Every requirement id and acceptance condition in N0 maps to a named design component or contract in N1; list unmapped ones.
2. No N1 statement contradicts an N0 statement (scope, behavior, error handling, schema).
3. Every concept N1 introduces has one name and a one-sentence definition that decides membership; the same concept is not called by two names; stored concepts state what one identifier denotes and which change creates a new one.
4. Every claim N1 makes about existing code ("currently", "base", "keeps", "unchanged") matches the code.
5. Every rule in the repository AGENTS.md files that the design touches is followed or the deviation is justified.
6. When N0 states a solution (the issue body, a comment, the user's words), N1 takes it as its mechanism or quotes the N0 requirement it fails; report a design that replaces it without that quote.
7. Every change N1 lists serves a named N0 requirement, and N1's mechanism is the smallest known one that meets them; report a change no requirement needs and a mechanism a smaller known one would replace.
