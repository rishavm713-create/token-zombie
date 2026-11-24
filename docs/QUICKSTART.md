# TZ 2.0 quickstart
## Install (Claude Code)
```bash
claude plugin marketplace add rishavm713-create/token-zombie
claude plugin install token-zombie@token-zombie
```
Restart Claude Code. If you used the old `install.sh`, run `bash install.sh --uninstall` first (hooks would fire twice).
Proven 2026-11-24: plugin 2.0.0 enabled in the real ~/.claude; a real `claude -p` session fired the TZ hooks (prompt.submit, session.end). Not proven yet: installing from the GitHub-hosted marketplace (local-folder marketplace proven).
## Upgrade
`claude plugin marketplace update token-zombie`, then `claude plugin update token-zombie@token-zombie`; restart. Rollback: `claude plugin uninstall token-zombie@token-zombie`.
## Daily commands (put `alias tz='python3 <plugin dir>/bin/tz'` in ~/.zshrc)
- `tz status` context, tokens, burn, warning state. `tz stats` savings, measured vs estimated.
- `tz map` / `tz sym NAME` / `tz exists WORDS` / `tz rank --focus FILE`: read these instead of exploring the repo.
- `tz next add|start|done` tasks with dependencies; `tz worktree add NAME` + `claim FILE` for parallel work.
- `tz handoff --task T --done D --left L --next N`, `tz resume` at the start of a new chat.
- `tz agent "task" --test "CMD" --gate --rollback` run build, test, independent gate, undo on failure. `tz agent --resume last` after a kill.
- `tz worker list|test NAME` which worker runs the phases (default: claude).
- `tz bench` before/after on a synthetic project (MEASURED/EST/UNKNOWN).
## On EditSutra
1. `cd ~/EditSutra`; read `HANDOFF.md` top block only; `tz resume --run-test`.
2. Before touching code: `tz map`, then `tz sym`/`tz exists` for the thing you want; read only those files.
3. One task per chat: `tz next add "title"`, `tz next start`, work, `tz handoff ...`, `tz next done`.
4. Risky edits: `tz agent "task" --test "<EditSutra test cmd>" --gate --rollback --worktree`.
5. Past 100k tokens: finish the task, hand off, start a fresh chat.
Claude saying "done" is not proof; trust the gate output and the tests.
