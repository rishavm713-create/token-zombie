# Review a change

Review the diff against its intent, not your taste.

1. Read the description or task, then say in one line what the change is meant to do.
2. Walk the diff for, in order: wrong behaviour, missing edge cases (empty, null, huge, concurrent), security (input, secrets, permissions), data loss, then tests.
3. Check that tests would actually fail if the change were wrong.
4. Look for what is absent: error paths, cleanup, migrations, docs for changed behaviour.
5. Rank findings: blocker, should fix, nit. Give file and line, the problem, and a concrete fix.
6. Report only things you checked. Mark guesses as guesses.
7. Praise nothing by default; if it is clean, say so in one line.
