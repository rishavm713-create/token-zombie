
# Review a change

Review the diff against its intent, not your taste. Feedback on your own work: review-reply.md.
Asking for one: give the reviewer the requirement and BASE..HEAD (BASE = where work started), read-only; subagent only if the diff is over ~150 lines.

1. One line: what the change is meant to do; check all of it is there, flag extras. Past lessons: `tz learn recall WORDS`.
2. Walk the diff: wrong behaviour, edge cases (empty, null, huge, concurrent), security, data loss, tests that would fail if it were wrong, missing error paths, cleanup, migrations, docs.
3. Rank P0 breakage/exploit/data loss; P1 likely in normal use; P2 edge case; P3 minor. "Could be better" never blocks.
4. Each finding: file:line, problem, fix, quoted line. Report only what you checked; mark guesses. Pre-existing issues go separately.
5. Several reviewers: `tz learn review returns.json` merges duplicates and hides unproven findings (P0 stays).
6. Never propose deleting plan docs. Verdict: merge, merge after fixes, or no. Clean: one line.
