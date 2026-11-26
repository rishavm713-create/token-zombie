---
name: tz-stale-guard
description: Keep stale plans and notes from sending the agent on side quests: code is truth, ask before acting on old notes, sweep after direction changes. Use when plans changed or the agent works on unasked things.
license: MIT
---
# tz-stale-guard
Own wording from a video on Google's side-quest study (2026). Full sweep: TZ Studio `context-sweep`.
1. Code is the source of truth; if CLAUDE.md or a plan disagrees, report it, do not follow it.
2. Do not act on old bug notes or TODOs nobody asked about.
3. New request: check it against existing plans first. One task per session.
4. After a direction change run the sweep (read-only, checker verifies, owner OKs edits/archive).
