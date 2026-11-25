# RECOVERY STATE (2026-11-25, coordinator re-run; tests independently reproduced by script)
Baseline: feat/v2.1.0 @ 617e051. Prior 4 group sessions all stopped by the 5-hour limit (13:15 local); transcripts are on this machine (~/.claude/projects/-Users-mac-tz-wt-*). Not resumed; state recovered from worktrees.
Rule: NO parallel sessions/subagents (they burned the limit). One session, sequential. No merge/tag/spend without approval.

| Group | Worktree / branch | Repos (manifest) | Tests run (pass/fail) | Status |
|---|---|---|---|---|
| 0 | ~/tz-wt-g00 feat/v2.1-g00 | 12 | ai_maestro 45/0, aider 42/0, cli_anything 28/0, compound 54/0, openspec 58/0, ponytail 29/0 | 6 of 12 have tests; other 6 (fast-anything, OpenHands, planning-with-files, mini-swe-agent, SWE-bench, repomap) UNKNOWN. ai-maestro backoff: tzbackoff.py + 45 tests present |
| 1 | ~/tz-wt-g1 tz-repos-g1 | 12 | astgrep 94/0, beads 80/0, ccusage 43/**1 FAIL**, headroom 39/0, omc 87/0 | 5 of 12 have tests; 7 UNKNOWN |
| 2 | ~/tz-wt-repos-g2 feat/v2.1-repos-g2 | 12 | context_mode 31/0, langfuse 43/**1 FAIL**, mattpocock 67/0, rtk 43/0, serena 67/0, superpowers 62/0, tokeneconomizer 62/0 | 7 of 12 have tests; 5 UNKNOWN |
| 3 | ~/tz-wt-repos-g3 feat/v2.1-repos-g3 | 9 | agent_skills 40/0, claude_mem 94/0, squad 45/0, claw 60/0, ruflo 57/0, tree_sitter 49/0, memsearch **CRASH IndexError** | 7 of 9 tests; lean-ctx, ccstatusline no test file (tzline.py maybe) |

All group work is UNCOMMITTED in the worktrees (do not reset). Run tests as `python3 tests/v21/test_gNN_x.py` (not pytest/unittest).
Windows fix: uncommitted in ~/token-zombie-v2.1 (11 modified files) — quarantined, preserved, not verified here.
Speed: feat/v2.1-speed f20ddd2 (1 commit over base), unmerged, unreviewed.
Merged earlier: bench, docs, suite, tips, windows-ci branches exist as worktrees at own commits; verify ancestry before merge.
