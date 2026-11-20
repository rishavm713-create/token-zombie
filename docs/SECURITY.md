# Security and privacy
Local only: no network calls, no telemetry, no uploads. `tz` never installs, enables, disables or edits skills/plugins/MCP/settings; only install.sh touches settings.json (backup, dry-run, restore).
`tz security`/`audit` run tz-vet.sh: RED = HIGH pattern (exfiltration, hidden code, injection, hidden unicode); YELLOW = docs mention danger, minified code, config/hooks/MCP touch; GREEN = nothing found. Static scan only: GREEN is not proof of safety.
`tz handoff --test CMD` runs the command you give it with your permissions (120 s timeout): give only your own test command.
Records stay in ~/.claude/token-zombie/ and project handoffs/.
