# Test a skill or rule

A rule you never saw an agent fail without may teach nothing.

1. Baseline: give a fresh agent the task without the rule; record what it does wrong and its excuses.
2. Write the smallest text that fixes exactly those failures.
3. Rerun fresh. Discipline rules: add pressure (time, sunk cost, "just this once"). Technique rules: a new case. Reference docs: can it find and apply the fact?
4. New excuse or miss: fix, rerun.

- Description says when to use it ("Use when ..."), not a summary of the steps.
- No skill for one-off stories or what a script or check can enforce.
- Subagent runs cost tokens: agree the number first.
