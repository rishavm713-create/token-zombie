# Security and privacy

## Reporting a vulnerability
Use GitHub private vulnerability reporting: the repository's Security tab > "Report a vulnerability". Please do not open a public issue for security problems.

## Model
- Local only: no network calls, no telemetry, no uploads. Nothing leaves the machine.
- Local servers (`tz dash --serve`, `tz companion`) bind 127.0.0.1 only and require a token (`~/.claude/token-zombie/companion.token`) plus a Host-header check; the dashboard sends a CSP.
- `errors.log` is redacted. Corrupt state files are quarantined as `.corrupt*`, never overwritten.
- `tz` never installs, enables, disables or edits skills, plugins, MCP servers or settings. Only `install.sh` touches `settings.json` (backup, dry-run, restore).
- `tz security` / `tz audit` run `tz-vet.sh`: RED = HIGH pattern (exfiltration, hidden code, injection, hidden unicode); YELLOW = docs mention danger, minified code, config/hooks/MCP touch; GREEN = nothing found. Static scan only: GREEN is not proof of safety.
- `tz handoff --test CMD` runs the command you give it with your permissions (120 s timeout): give only your own test command.
- Records stay in `~/.claude/token-zombie/` and project `handoffs/`.
- The toolbar Mod (`hooks/panel.tsx`) uses only the Claude Code Mods API. It reads state files, writes `agents.json`, and runs `python3 <plugin>/bin/tz <sub>` with no shell and a 30 s timeout. It makes no model calls and no network calls.
