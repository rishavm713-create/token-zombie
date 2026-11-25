# Integration status (updated 2026-11-25, branch merge/g123, local only: not pushed, no PR)
Source: `git log origin/main..HEAD` = 15 commits (12 non-merge: 9+1 g1, 1 g2 WIP, 1 g3 WIP, plus 3 merge commits); `git diff --stat origin/main..HEAD` = 38 files, +3277/-821.
| Workstream | Implemented | Tested | Committed | Integrated | Remaining |
|---|---|---|---|---|---|
| Core v2.0.0, install, worktrees, gaps-p1 | yes | yes (suite) | yes | yes, in v2.1.0 on main | none |
| Speed, suite fix, tips, bench, integration fixes, docs | yes | yes (suite) | yes | yes, in v2.1.0 on main | tips effect UNKNOWN |
| Windows fixes (fafcade) | partial | Windows CI: 11 fail | yes | yes, UNVERIFIED on Windows | deferred; dedicated Windows session |
| g0 (feat/v2.1-g00) | yes | per PR #6 | yes | yes, PR #6 merged to main | none |
| g1 (tz-repos-g1, 12 repos: tzaskills, tzhumanlayer, tzreplayrank, tzscope, tztokopt + wiring) | yes | own tests/v21/test_g1_*; merged-suite result: see TEST_EVIDENCE | yes (10 commits) | merged into merge/g123 only | merge to main; `tz budget` semantics vs v21 UNVERIFIED |
| g2 (feat/v2.1-repos-g2) | yes, WIP checkpoint (not release-ready) | own tests test_g02_*; merged-suite: see TEST_EVIDENCE | yes (1 WIP commit 8da16ed) | merged into merge/g123 only | owner review of WIP content; merge to main |
| g3 (feat/v2.1-repos-g3, lean-ctx/tzread etc.) | yes, WIP checkpoint (not release-ready) | own tests test_g03_*; merged-suite: see TEST_EVIDENCE | yes (1 WIP commit 0e89897) | merged into merge/g123 only | licence review (below); merge to main |
## Conflicts resolved in the merges
- bin/tz mods dict: g1 commands added to v21 dispatch.
- bin/tzbudget.py: kept v21 main version (g1 changes dropped here).
- bin/tzlib.py features: union of g2 + g3 keys.
- NOTICE and docs/OPEN-SOURCE-INTEGRATION-LEDGER.md: union.
- bin/tz-guard.py, bin/tz-start.py: both hook blocks kept.
## Open items (honest)
- Windows deferred: 11 CI failures (test_smoke 8, test_stuck 2, test_g03_ruflo 1).
- LICENCE: g3 deleted `third_party/claude-squad/LICENSE` (660 lines, possibly AGPL) and added `PROVENANCE.txt`; the diff also deletes `third_party/token-optimizer/LICENSE` (130 lines). Needs licence review before release. Do not ship as is.
- g1 `tz budget` semantics vs v21 UNVERIFIED (bin/tzbudget.py kept as v21).
- Remote group branches (g1-g3) not deleted: needs owner OK.
- Owner must run `./install.sh` themselves (never run on live ~/.claude by Claude).
- Paid `tz ab` trials need owner OK.
Worktrees ~/tz-wt-g00, ~/tz-wt-g1, ~/tz-wt-repos-g2, ~/tz-wt-repos-g3: never delete.
