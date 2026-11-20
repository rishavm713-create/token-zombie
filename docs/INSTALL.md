# Install / rollback (tested only in fake HOME; nothing has been run on the real machine)
Preview (writes nothing):
```bash
bash ~/.claude/skills/token-zombie/install.sh --dry-run
```
Install (backs up settings.json first, refuses on invalid JSON, atomic write):
```bash
bash ~/.claude/skills/token-zombie/install.sh
```
Use the CLI (tz never edits your shell files or PATH; pick one and do it yourself):
- Alias, current shell only (add the same line to `~/.zshrc` to keep it):
  `alias tz='python3 ~/.claude/skills/token-zombie/bin/tz'`
- Symlink into a folder already on PATH (works in every shell and script; `tz` follows the link to its modules):
  `ln -s ~/.claude/skills/token-zombie/bin/tz /usr/local/bin/tz` (check first: `echo $PATH | tr : '\n'`)
- No setup: `~/.claude/skills/token-zombie/bin/tz sup status`
Rollback, either:
```bash
bash ~/.claude/skills/token-zombie/install.sh --uninstall
bash ~/.claude/skills/token-zombie/install.sh --restore
```
`--uninstall` removes tz hooks and restores your previous statusline. `--restore` copies back the newest `settings.json.bak-tz-*` (keeps what it replaced as `settings.json.before-restore`).
Config (optional) `~/.claude/token-zombie/config.json`, same keys as `tz config`:
```json
{"limit": 100000, "hard": 175000, "ctx_window": 200000, "plan_warn": 90, "plan_stop": 97}
```
Env `TZ_<KEY>` beats the file beats defaults. Restart Claude Code after install.

Check what is installed: `bash install.sh --check`. Crash-safe: a stale `settings.json.tz-tmp` from an interrupted run is removed on the next run; settings are replaced atomically; a failed install leaves settings as before.
Hooks wired: UserPromptSubmit, PostToolUse, PreToolUse(Read), SessionStart, PreCompact (guard + note), Stop, SessionEnd. Supervisor off switch: env `TZ_SUP=0`.
Optional: `python3 bin/tz overlay build` then `tz overlay run` (native window; uses the Command Line Tools swiftc, installs nothing). `tz dash --serve` / `tz companion` bind 127.0.0.1 and need the token in `~/.claude/token-zombie/companion.token`.
Config template: `config.example.json`.
