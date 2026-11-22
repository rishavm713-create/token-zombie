# Owner checklist: verify TOKEN ZOMBIE on the real Claude Code host
Nothing below is VERIFIED until you run it. I (the assistant) never run `install.sh` on your live `~/.claude`.
Evidence goes in `docs/evidence/` (create it). Mark each row PASS / FAIL / NOT RUN and paste the output.

| # | Step | Command / action | Pass evidence |
|---|---|---|---|
| 1 | Dry run | `./install.sh --dry-run` | diff shows only token-zombie hook entries |
| 2 | Install | `./install.sh`, then open a NEW chat | statusline shows the mascot |
| 3 | Check | `./install.sh --check` | reports all 18 events registered, no duplicates |
| 4 | Idempotent | run `./install.sh` again, then `--check` | still one entry per event |
| 5 | Events fire | do a normal session: prompt, Read a file, run a failing Bash command, spawn one subagent, `/compact`, switch model, exit | `tz hooks live` lists a non-zero count per event used |
| 6 | New payloads | after step 5 | `PostCompact` has `compact_summary` (else compaction check stays UNAVAILABLE); `InstructionsLoaded`, `PostToolUseFailure`, `SubagentStart/Stop` show in `tz ledger` |
| 7 | Latency | `tz hooks live` and `tz hooks bench` | live ms close to bench ms; none near the 5 s timeout |
| 8 | Agent ROI | `tz live agents` after step 5 | the subagent has start, stop, cost |
| 9 | Fail-open | `chmod 000 ~/.claude/token-zombie/tz.db`, run a prompt, restore with `chmod 600` | prompt still works, no hook error |
| 10 | Uninstall | `./install.sh --uninstall` then `--check` | no token-zombie entries left; settings backup exists |
| 11 | Restore | `./install.sh --restore` | previous settings back |
| 12 | Linux | repeat 1-4 and 10 on Linux, if you claim Linux | until then README says macOS tested only |

Report: per step expected / fired / evidence / error. Hooks verified = rows 5-7 PASS.
