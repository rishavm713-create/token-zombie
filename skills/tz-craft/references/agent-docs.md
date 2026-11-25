# Writing for agents

For skills, CLAUDE.md, AGENTS.md and docs an agent reads.

- Always-loaded text costs tokens every turn. Keep it to what every task needs.
- Put branch-only material in a separate file behind a one-line pointer.
- The pointer's wording decides if it gets read: lead with the key word, one trigger per distinct case, no synonyms.
- Steps in order; end each with a checkable done condition.
- Keep a term's definition, rules and caveats together; state each fact once.
- Prefer a known short term (e.g. "red-green") over a paragraph explaining it.
- Delete lines the model would obey anyway; test by removing them.
- Do not copy what code, config or diffs already say: point to the path.
