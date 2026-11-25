# Test evidence, v2.1.0 (2026-11-25, Mac)
Command: `bash tests/run_all.sh` on feat/v2.1.0 (fbc9bf8 + test_split fix 59cd7ea).
Result of the run: TOTAL pass 3068, fail 1, skip 2 (test_v21: 2033 pass, 0 fail; skip = real tree_sitter not installed).
The 1 failure was `subagent-cap` in `tests/test_split.sh`: the real `~/.claude` config turned off `pack_hints`. Fixed in 59cd7ea (HOME isolated to a temp dir). After the fix `bash tests/test_split.sh` = pass 13, fail 0. The full suite was NOT rerun after that one-line test change.
Not tested: Windows (CI run 45604891823 on fafcade: pass 3040, fail 11, skip 9; deferred), macOS CI rerun (was queued), PostCompact on a real host, paid `tz ab` trials.
