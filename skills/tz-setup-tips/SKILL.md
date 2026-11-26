---
name: tz-setup-tips
description: Short list of Claude Code settings that save tokens or interruptions (skill-doctor, prompt audit, lighter startup, Opus-plan, one subagent model, fewer prompts). Use on a new machine, after a model release, or when plan usage is high; skip otherwise.
license: MIT
---
# tz-setup-tips
Own wording from a video list of Claude Code tips (2026). Confirm each command name in the current version first; change settings only with the owner's OK. Full checklist: TZ Studio `claude-code-setup`.
1. Skill doctor / skills command: sort skills by token cost, trim the rest (tz already keeps packs off).
2. Prompt audit after a new model: remove outdated instructions from CLAUDE.md and skills.
3. Lighter startup: stop app connectors and artifacts loading every session (settings file).
4. Opus-plan (Opus plans, Sonnet builds) and one cheap model for all subagents.
5. Fewer-permission-prompts: allow read-only commands only.
6. Save plans in the project folder; use branch/fork/subtask instead of long chats.
7. Only build-eval and hillclimb cost API money: run with a budget.
8. Run the audit: `node ~/tz-studio/scripts/setup-audit.js` (read-only; `--apply` applies only the safe group, with diff and backup).
