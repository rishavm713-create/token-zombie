# Test evidence (2026-11-25, Mac)
## v2.1.0 (main, feat/v2.1.0 fbc9bf8 + 59cd7ea)
`bash tests/run_all.sh` on merged main (14bbb73 + docs): TOTAL pass 3624, fail 0, skip 2 (MEASURED, 2026-11-25). skips: real tree-sitter not installed. test_v21 (incl. matrix 109/0, ~12 min) pass 2588, fail 0. Windows CI (11 failures) is deferred.
## merge/g123 (v2.1.0 + g0-g3, HEAD f099af1)
suite result: pending, see log (`bash tests/run_all.sh` still running when this was written; no TOTAL line yet).
Log: /private/tmp/claude-501/-Users-mac/d0f3086d-110f-41b7-9b2a-1d6930f888e2/scratchpad/suite123.log
So far (MEASURED, partial, 51 log lines): no failing test line; e.g. test_codex 13/0, test_policy 25/0, test_upgrade 27/0, test_gate2 24/0, test_repo_intel 14/0, test_killgroup 3/0. SKIP: real tree-sitter not installed.
Update this file with the final TOTAL line when the run ends.
## Not tested
Windows (CI run 45604891823 on fafcade: pass 3040, fail 11, skip 9; deferred), macOS CI rerun, PostCompact on a real host, paid `tz ab` trials, `tz budget` g1 vs v21 semantics.
