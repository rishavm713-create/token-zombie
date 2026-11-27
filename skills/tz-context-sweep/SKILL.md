---
name: tz-context-sweep
description: Find outdated plans, specs, CLAUDE.md lines and old-bug notes that pull the agent into side quests, verify each against the code and git history, then report (archive only with OK). Use after a direction change, before a big build, or when the agent works on things nobody asked for; skip for small fixes.
license: MIT
---
# context-sweep
Idea source: a video on Google's "side quest" study (2026), own wording. Numbers below are the video's, not measured here: about 1 in 7 sessions met a stale note, most then chased it, and such sessions used far more actions and tokens.

## Why
The agent reads CLAUDE.md, specs and related files into context. Old specs, fixed-bug notes and unchanged docs steer it wrongly. More tools and skills give more room for side quests. An outdated CLAUDE.md is followed over the real app.

## Sweep (read-only first)
1. List sources: CLAUDE.md/AGENTS.md, specs/plans/tickets, TODO/FIXME notes, memory notes, handoffs.
2. For each claim (names, flows, "bug X open"), check the code and `git log` for proof it is current, fixed, dropped or renamed.
3. A separate checking agent re-verifies every finding before it is reported. Drop unverified ones.
4. Report a table: file, line, claim, verdict (stale / wrong / ok), proof, proposed fix.
5. Apply only with the owner's OK: edit the line, or move the file to `archive/`. Never delete.

## Prevent (rules for CLAUDE.md, owner approves)
- Code is the source of truth; report any mismatch with the plan instead of following the plan.
- Do not act on anything not asked (no fixing open-bug notes unasked).
- Check a new feature request against existing plans before building.
- Every ticket has a status: completed / in progress / not started. Fresh session per task.
- Optional hook: block reads of `archive/` (owner approves any hook).

## Cost
One sweep costs tokens: run it when direction changed, not every session. Use a cheap model for listing, a checker for verification.
