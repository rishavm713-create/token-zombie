# Debug

Find the cause before you change anything.

1. Reproduce it with a command that fails every time. Flaky: see debug-flaky.md.
2. Read the whole error and trace; note the first frame in your own code.
3. Check what changed: diff, recent commits, dependencies, config, environment. `git bisect` for "worked last week".
4. Several components: log what enters and leaves each boundary, run once, then dig only into the layer that breaks.
5. Compare with similar code that works; list every difference.
6. Shrink input, config or code to the smallest failing case.
7. One hypothesis ("X causes it because Y"), one variable, one check that could disprove it. Bad value deep in the stack: debug-trace.md.
8. Fix the cause, not the symptom: one change, failing test first, kept as regression. No catch-all or retry that hides it.
9. Failed guess: revert it before the next. After three failed fixes, question the design and ask the owner.
