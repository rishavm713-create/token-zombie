# Disable, uninstall, recovery
- Mode: `tz mode off` disables advisory features. Safety controls stay on in every mode: hard-limit safe-point handoff warning, plan_stop, corrupt-state quarantine, redacted errors.log, installer backups, tz-vet HIGH findings, task-continuity rule.
- Supervisor: env `TZ_SUP=0` makes it a no-op.
- Plugin: `claude plugin disable token-zombie@token-zombie`, or `claude plugin uninstall token-zombie@token-zombie`.
- Statusline (set by `install.sh --statusline-only`): `bash install.sh --uninstall` restores the previous statusline (kept as `prev_statusline` in config.json) and removes tz hooks of a classic install; `bash install.sh --restore` copies back the newest pre-install `settings.json.bak-tz-*` (keeps what it replaced as `settings.json.before-restore`). `--check` shows what is wired; `--dry-run` previews.
- Quarantine: bad state files are renamed `<name>.corrupt`, `.corrupt.1`, ... in `~/.claude/token-zombie/`; inspect or delete them by hand.
- Stale `settings.json.tz-tmp` from an interrupted install is removed on the next run.
