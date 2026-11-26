# Supervisor
`tz sup start|tick|status|next-session|task`. Hooks drive it: tool events take a cheap path; a full tick runs on prompt, compact and stop. A tick: usage level + burn -> auto checkpoint (120 s throttle) -> handoff prep at CRITICAL -> writes `~/.claude/token-zombie/status.json` (read by statusline, dash, companion, panel).
Levels: NORMAL, ELEVATED (skip optional research/background agents), APPROACHING LIMIT (finish the active task, checkpoint), CRITICAL (handoff now, continue fresh), EXHAUSTED (save progress; resume when capacity returns; tz cannot bypass provider limits).
Activity (working/idle) is MEASURED from hook events only; no event for 15 min while working => UNKNOWN.
A damaged state file is renamed to `<file>.corrupt[.N]` (never overwritten) and a fresh one starts. Off: env `TZ_SUP=0`.
