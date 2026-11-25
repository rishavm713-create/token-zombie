# v2.1 integration status (2026-11-25)
Branch `integration/v2.1` (de9e503) = feat/v2.1.0 (617e051) + speed, g3, g1, g2, g0 merged in that order. NOT merged into feat/v2.1.0, not tagged, not pushed.
Branches: feat/v2.1-speed f20ddd2, feat/v2.1-repos-g3 5e1b00d, tz-repos-g1 422c45d, feat/v2.1-repos-g2 9aa478c, feat/v2.1-g00 d263d4c.
Conflicts fixed: g1 tzbudget vs g3 ruflo tzbudget (g1's renamed tzdepth); tzcrush crush(text, cmd) + build-log stage; bin/tz dispatch (+impact, condense); NOTICE/STUDIO-DEFERRED union; plan.md/review.md deduped under size caps.
Tests: all 45 tests/v21/test_*.py script files pass fail 0 (test_matrix 61/0, shell_parity 124/0). Run as `python3 file.py` from a path outside /tmp (guard treats /tmp as safe, so rm -rf checks fail there).
Not done: Windows run + Windows fix (11 uncommitted files in ~/token-zombie-v2.1, breaks macOS tests), paid benchmark, tag/publish.
Next: owner approves `git merge integration/v2.1` into feat/v2.1.0, then tag after the Windows test.
