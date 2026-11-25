# Trace to the source

For a bad value or side effect that shows up deep in the call stack.

1. Name the symptom and the line that directly causes it.
2. Ask who called it and with what value. Repeat upward until you find where the bad value is born.
3. Cannot follow by reading: log the value, cwd and a stack trace to stderr just before the failing operation, run, grep.
4. Fix at the origin.
5. Then guard the layers it passed through: reject at entry, check in the operation, refuse dangerous actions in tests (e.g. writes outside a temp dir). Try to bypass the first guard to prove the next one holds.

Which test leaves stray files or state: confirm the artifact is absent, run test files one at a time (or halves), check after each; the first run that creates it is the polluter.
