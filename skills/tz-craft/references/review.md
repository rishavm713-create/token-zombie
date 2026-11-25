# Review a change

Review the diff against its intent, not your taste.

1. Say in one line what the change is meant to do. Check past lessons: `tz learn recall WORDS`.
2. Walk the diff for: wrong behaviour, edge cases (empty, null, huge, concurrent), security (input, secrets, permissions), data loss, tests that would fail if it were wrong, missing error paths, cleanup, migrations, docs.
3. Rank P0 breakage, exploit or data loss; P1 likely in normal use; P2 edge case or trap; P3 minor. "Could be better" never blocks.
4. Each finding: file, line, problem, concrete fix, quoted line as evidence. Report only what you checked; mark guesses. Pre-existing issues go separately.
5. Use extra reviewers only for diffs over about 150 lines. Combine their JSON with `tz learn review returns.json`: it merges duplicates and hides unproven findings (P0 stays). Same-model agreement is not proof.
6. Never propose deleting plan or solution docs. If clean, say so in one line.
