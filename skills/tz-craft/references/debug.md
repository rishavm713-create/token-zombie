# Debug

Find the cause before you change anything.

1. Reproduce it. Get a command that fails every time. If it is flaky, loop it, log the inputs, and pin the clock, random seed, ordering and network until it fails on demand.
2. Read the exact error and the first frame in your own code, not the last line only.
3. Shrink: remove input, config or code until the smallest case still fails.
4. Write one hypothesis, then one check that could disprove it. Test it with a print, a debugger step or a bisect (git bisect for "worked last week").
5. Fix the cause, not the symptom. A retry, sleep or catch-all that hides it is not a fix.
6. Keep the reproduction as a regression test.
7. After two failed theories, stop guessing: list what you assumed and verify each assumption directly.
