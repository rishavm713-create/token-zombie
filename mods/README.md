# Claude Code mods (30 in tz; first 26 also in tz-studio)
Each folder is one mod. Try one: `claude --plugin-dir <this folder>/<mod>` (terminal only; panels/status do not show in the VS Code extension).
All are idle until their slash command is used, except `tz-chat-thermometer` (status line, no model call) and `tz-rule-enforcer` (checks Bash calls against stored rules).
Opt-in prompt additions: `/plain on`, `/fake on` (off by default, so no extra tokens).
Model calls (Haiku, only when you type the command): `/enhance`, `/jargon`.
`studio-tasks` reads ~/tz-studio-data/state; `tz-load` wraps ~/.claude/skillpack.

- tz-secret-guard: blocks Bash that exposes secrets
- tz-danger-guard: blocks destructive Bash (/danger off to pause)
- tz-turn-nudge: handoff reminder every N turns (/nudge N)
- tz-auto-checkpoint: /checkpoint shows last task for a fresh chat
