# Live verification milestone 2 (prepared 2026-11-20, not run yet)
Goal: prove each of the 7 hook events on the real machine, with evidence. Feature work is frozen until this passes.
Baseline: suite 377/377 pass. Fixes in place: `tz sup status` no longer quarantines a valid status.json; quarantine
never overwrites (.corrupt, .corrupt.1, ...); tz-guard logs redacted errors to ~/.claude/token-zombie/errors.log.
Rules: no settings change, no reinstall, no commit/publish. Unprovable item = NOT VERIFIED.

State files (all in ~/.claude/token-zombie): activity.json (last event, ts, session), status.json (last tick),
errors.log (should stay absent), compact-<session>.md (PreCompact note).
Check helper (read-only): `python3 -c "import json;print(json.load(open('$HOME/.claude/token-zombie/activity.json')))"`

| # | Step (owner does it in a NEW chat unless noted) | Pass evidence |
|---|---|---|
| 0 | Before: note status.json ts, list `status.json.corrupt*`, check errors.log absent | baseline noted |
| 1 | SessionStart: open a new chat | activity.json event=SessionStart (or later), new session id |
| 2 | UserPromptSubmit: send a short prompt | status.json ts newer; activity session = new id |
| 3 | PreToolUse (Read) + PostToolUse: ask the model to Read a small file | activity event=PostToolUse right after |
| 4 | Stop: after the reply ends, in ANOTHER chat or terminal read activity.json | event=Stop, activity idle |
| 5 | Statusline: look at the bar while working and after Stop | 🧟 while working, idle mascot after Stop; number near status.json ctx |
| 6 | PreCompact: owner types `/compact` in a small test chat (safe, manual) | compact-<id>.md written; activity event=PreCompact; new status tick |
| 7 | SessionEnd: owner closes/exits that chat, then reads activity.json elsewhere | event=SessionEnd, same session id |
| 8 | TZ_SUP=0: in a terminal `TZ_SUP=0 claude`, send one prompt, exit | activity.json and status.json ts unchanged |
| 9 | `tz sup status` twice (via full path or alias) | prints status, no new `.corrupt*` file |
| 10 | After all: errors.log | absent, or only redacted lines, each explained |

Report per step: expected, fired yes/no, evidence (file + ts), errors. End verdict: operational / not.
Known gaps: activity.json keeps only the last event (no history), so steps 4 and 7 must be read before the next event.
