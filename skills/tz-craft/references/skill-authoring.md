# Writing a skill cheaply

- The name and description load in every chat: say what it does and when to use it, in about 250 characters.
- SKILL.md loads on each use: keep it a short router with the steps always needed.
- Put detail in separate files, one topic each, linked straight from SKILL.md with a line saying when to open it.
- Avoid chains (file A points to B points to C) and all-in-one compiled copies an agent may read whole.
- Replace long deterministic steps with a script that is run, not read; have it print a short result.
- State a rule once. Remove what the model already does without being told.
- Remove broken links and files nothing points to.
- Check with `tz skills check DIR`; its token figures are estimates.
