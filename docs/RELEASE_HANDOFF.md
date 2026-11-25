# Release handoff, v2.1.0
- PR #4 feat/v2.1.0 -> main: MERGED (merge commit 78743eb). Tag v2.1.0 -> 78743eb pushed. GitHub release created from CHANGELOG.
- Website: docs/index.html pill and release link now say v2.1 / v2.1.0 (Pages from docs/).
- Owner tasks: run `./install.sh` yourself (never done on live ~/.claude by Claude); `tz hooks live`; HOST-VERIFY checklist; OK for paid `tz ab` trials.
## Next steps, in order
1. Windows session (other account/Mac): fix 11 failures (test_smoke 8, test_stuck 2, test_g03_ruflo 1) from CI run 45604891823; do not mix with other work.
2. g0 -> branch from main, merge, run `bash tests/run_all.sh`, push.
3. g1: resolve NOTICE, bin/tz, bin/tzbudget.py conflicts; test.
4. g2, g3: commit uncommitted files in their worktrees, check licences (AGPL), test, merge one at a time.
5. Other projects: EditSutra captions-audit fix, GTA6 clips question.
Rules: one integration owner; no force push; one writer per file set; full suite after each merge.
