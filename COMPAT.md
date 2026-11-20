# Compatibility
**EXPERIMENTAL / rules-only: every non-Claude adapter (Codex, Cursor, Windsurf, Gemini, Cline, Roo, Antigravity).** They only get a generated rules file; no hooks, no statusline, no supervisor. Capabilities are declared and UNVERIFIED. Only Claude Code is real. Claude Code >= 2.1.318 tested; macOS tested; Linux expected via CI; Windows untested.

## Other agents
Rules (skills/token-zombie/SKILL.md sections 1-6) are plain text and work anywhere. Hooks/statusline are Claude Code only.

- Codex CLI: copy this folder to `~/.codex/skills/token-zombie/` (Codex reads SKILL.md skills) or paste sections 1-5 into `~/.codex/AGENTS.md`. No hooks: check size with `/status`; start a new session per task by hand. Model rule: cheap model (e.g. mini) for reading, main model for builds.
- Antigravity / Gemini: paste sections 1-5 into the workspace rules (`.agent/rules/` or `GEMINI.md`). No hooks; handoff files work the same.
- Cursor / others: put sections 1-5 in the project rules file. Keep it under ~60 lines; it loads every chat.
- Everywhere: HANDOFF.md top block + `handoffs/YYYY-MM-DD.md` format is the shared memory between tools.
- Not portable: `tz-guard.py` (Claude hook JSON), `tz-status.py` (Claude statusline), `skillpack` (Claude skills dir).

## Adapters (v0.2.0)
`tz adapters` lists capabilities. claude = real. codex/cursor/windsurf/gemini/cline/roo/antigravity = declared, UNVERIFIED; `tz adapters --rules <name> --out FILE` generates a rules file from skills/token-zombie/SKILL.md sections 1-5.
