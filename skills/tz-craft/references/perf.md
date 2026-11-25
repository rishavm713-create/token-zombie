# Performance

Measure, change one thing, measure again.

- Get a baseline number first on a realistic input. No number, no optimization.
- Profile to find the hot spot; the slow part is rarely where you guess.
- Fix the biggest cost first: wrong algorithm or data structure, repeated work inside loops, N+1 queries, needless copies, work done eagerly that is rarely used.
- Then batch, cache with a clear invalidation rule, or do the work lazily or in parallel.
- Keep results identical: run the tests before and after.
- Stop when the target is met. Record before and after numbers in the commit message.
- Reject micro-tweaks that make code harder to read for a gain you cannot measure.
