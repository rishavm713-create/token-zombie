# Multi-agent work
- Heavy reading or building goes to cheaper subagents (Haiku for reading/search, Sonnet per file for builds), each writing to its own file; the main chat only wires and checks.
- Pass a short brief + file paths, never pasted content. Subagent output returns as the tool result: ask for terse reports.
- `tz capabilities` lists skills/plugins/MCP and overlaps; `tz skills [words]` shows loaded vs parked and relevance. `tz profile <prompt> [--yes]` plans which parked packs a task needs; `--yes` runs the owner's own skillpack. A running chat does not reload skills; effect starts in a new chat.
- Supervisor adapters: only claude is REAL; others (codex, cursor, windsurf, gemini, cline, roo, antigravity) generate rules files via `tz adapters --rules <name> --out FILE`, capabilities UNVERIFIED.
