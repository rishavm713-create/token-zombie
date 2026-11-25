# Performance

Measure, change one thing, measure again.

- Baseline first, on the real workload (not the test suite). No number, no optimization.
- Profile; take the biggest cost. Skip anything under 2% of the run. Change the outermost function that covers the hot loop.
- Fix order: algorithm/data structure, repeated work in loops, N+1, needless copies, eager rare work; then batch, cache with clear invalidation, lazy/parallel.
- Record real calls before editing, replay all after. Same results, exceptions and argument mutations; never edit recordings.
- Not faster per call? Revert, even if correct.
- Report end-to-end and per-call speedup, plus undo; numbers in the commit message. Stop at the target.

Python, with `tz fast`:
1. `tz fast scan -- app.py args`
2. `tz fast record mod.py:func -- app.py args` (pure functions)
3. edit, then `tz fast verify mod.func` (exit 0 keep, 1 differs, 3 slower)
4. `tz fast bench --vs "new cmd" -- old cmd` (for in-place edits, time before and after)
