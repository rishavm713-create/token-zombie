# TOKEN ZOMBIE v0.1 (release candidate)
Local-first token saver for Claude Code. One CLI `tz`, hooks, statusline. No network, no telemetry, nothing leaves the machine.

## What works (all covered by tests/run_all.sh)
- **Task continuity**: `tz handoff` writes `handoffs/tasks/<task>.json` + daily `handoffs/DATE-tz.md` (<=30 lines) + `MASTER.md` facts. `tz resume` checks branch/HEAD/edited files/test result against the saved state, prints drift and the exact next action. Read-only for your files.
- **Usage**: `tz status|forecast`: context %, input/output/cache tokens from the chat log, burn rate, 5h/7d only when Claude Code passes `rate_limits`. Every number is labelled `[actual]` or `[est]`.
- **Optimization**: duplicate-read advice (path+mtime+hash, cache invalidates on change), log analysis of repeated reads/commands (`tz optimize`), output filter (`tz filter`), task mode + model advice (`tz classify`), savings ledger with tz's own overhead subtracted (`tz stats`). Full reads are never blocked.
- **Capabilities**: `tz skills|capabilities` inventory of skills, parked skills, plugins, MCP; overlaps; relevance advice. `tz security <dir>`, `tz audit`: GREEN/YELLOW/RED via `tz-vet.sh`.
- Existing v3.1 hooks (guard, lean start, compaction note, statusline, startup audit) unchanged.

## Quick start
See docs/INSTALL.md (dry-run first, rollback included). CLI: docs/CLI.md. Limits: docs/LIMITATIONS.md. Security/privacy: docs/SECURITY.md.

## Tests
`bash tests/run_all.sh` -> TOTAL pass 199 fail 0 (9 scripts, fake HOME; real settings.json never written).
