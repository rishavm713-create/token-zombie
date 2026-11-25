# Review a change

Review the diff against its intent, not your taste. Feedback on your own work: review-reply.md.

Asking for one (after a feature, before merge; subagent only if the diff is over ~150 lines): give the reviewer the requirement and BASE..HEAD, not your history. BASE is where the work started, not HEAD~1. Reviewer stays read-only.

1. Say in one line what the change is meant to do; check all of it is there, and flag anything extra.
2. Look in order for wrong behaviour, edge cases (empty, null, huge, concurrent), security, data loss, tests.
3. Would the tests fail if the change were wrong?
4. What is absent: error paths, cleanup, migrations, docs.
5. Rank blocker, should fix, nit: file:line, problem, why it matters, fix.
6. Report only what you checked; mark guesses and what you could not verify.
7. End with a verdict: merge, merge after fixes, or no. If clean, one line.
