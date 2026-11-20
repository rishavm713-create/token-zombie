# Checkpoints and compact handoffs
- `tz checkpoint`: refreshes the git snapshot of the active task (branch, HEAD, edited files); runs no commands. The supervisor auto-checkpoints at most every 120 s.
- `tz handoff --task T --done D --left L --next N [--test CMD] [--remember FACT]`: writes `handoffs/tasks/<task>.json`, a daily `handoffs/DATE-tz.md` (<= 30 lines) and `MASTER.md` facts. `--test CMD` runs the command you type (120 s timeout): give only your own test.
- `tz task-wrap [--test CMD] [--summary S] [--remember D] [--force]`: closes a task only if the test passes.
- PreCompact hook (`bin/tz-compact.py`): saves `~/.claude/token-zombie/compact-<session>.md` (git changed files, last test command -> result, next plan step); SessionStart with source=compact injects only that (<= 1500 chars). Subagent compactions are skipped.
- `/token-zombie:compact` writes the note and prints the `/compact <keep-text>` line; a command file cannot run `/compact` itself.
