# Integration status (2026-11-25)
| Workstream | Implemented | Tested | Committed | Integrated in v2.1.0 | Remaining |
|---|---|---|---|---|---|
| Core v2.0.0, install, worktrees, gaps-p1 | yes | yes (suite) | yes | yes (earlier on main) | none |
| Speed, suite fix, tips wiring, bench | yes | yes (suite) | yes | yes | tips effect UNKNOWN |
| Integration fixes (agent/budget/stuck/fake claude) | yes | suite | 833a120 | yes | none |
| Docs cost-tips (3371f72 -> fbc9bf8), roadmap (cf1861b -> 9b8c2cb) | yes | n/a | yes | yes | none |
| Windows fixes (fafcade) | partial | Windows CI 11 fail | yes | yes, UNVERIFIED on Windows | dedicated Windows session |
| g0 (feat/v2.1-g00, 4ae9349, 5 commits) | yes | full suite not reported | yes | NO | merges cleanly: first follow-up |
| g1 (tz-repos-g1, 2c87ca8, 9 commits) | yes | suite not reported | yes (+1 uncommitted file) | NO | conflicts in NOTICE, bin/tz, bin/tzbudget.py |
| g2 (feat/v2.1-repos-g2) | partial | no | NO (10 uncommitted) | NO | commit, test, merge |
| g3 (feat/v2.1-repos-g3, 9 repo modules) | partial | 408 pass per its note | NO (16 uncommitted; a LICENSE delete: check AGPL claude-squad) | NO | commit, licence review, merge |
Worktrees ~/tz-wt-g00, ~/tz-wt-g1, ~/tz-wt-repos-g2, ~/tz-wt-repos-g3 are untouched. Never delete them.
