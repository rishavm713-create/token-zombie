# Security audit
- `tz audit`: GREEN/YELLOW/RED grade of every installed skill. `tz security <dir>`: same for a folder. Both use `bin/tz-vet.sh` (static scan, read-only, never installs or runs anything).
- RED = HIGH pattern (pipe-to-shell, secret reads, file/env/DNS upload, deletes outside own dir, decode-then-exec, persistence, permission bypass, prompt injection, hidden unicode). YELLOW = docs mention danger, minified code, config/hooks/MCP touch. GREEN = nothing found, not proof of safety.
- HIGH: do not install until each line is read and explained to the owner. Direct use: `bash "${CLAUDE_PLUGIN_ROOT}/bin/tz-vet.sh" <dir>` (exit 1 on HIGH).
- `tz reg [list|add <localdir>|show <name>]`: local registry of vetted repos; never fetches URLs.
- tz never installs, enables, disables or edits skills/plugins/MCP/settings. Only install.sh touches settings.json (backup, dry-run, restore). See docs/SECURITY.md.
