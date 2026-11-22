# Autonomous project continuity (`tz next`)
Local files only. No network, no telemetry, no session launching.

## Use
```
tz next add <id> --title T [--dep ID]... [--gate paid|commit|install|publish] [--goal G] [--file F]... [--next A] [--model M]
tz next                      # list + NEXT eligible (deps done); gated NEXT = "stop and ask the owner"
tz next start <id> [--approved]   # one active task; gated needs --approved (owner said yes)
tz next done <id> --test "<cmd>" --yes   # runs the test; done only if it passes; result stored
tz next pack | checkpoint | measure [--transcript F]
```
State: `handoffs/tasks/T-<id>.json` (id, title, deps, status done|active|blocked|pending, gate, goal, files, next, model, test{cmd,ok,result,time,src}, checkpoint).
Duplicate id/title refused; done tasks never restarted/overwritten; corrupt files skipped.

## Automatic parts (hooks, silent)
- `tz-start.py` (SessionStart): appends the pack (<=8000 chars ~2k tok) of the ACTIVE task only, after the handoff head. Fresh session resumes from the pack, no rediscovery.
- `tz-guard.py` PostToolUse: a Bash test command (run_all/pytest/npm test/test_*.sh/plugin test) whose output shows pass and no FAIL -> records `test` on the active task + `tzhandoff.checkpoint` (git snapshot). No output emitted.
- `tz-guard.py`: at HARD token growth (PostToolUse/UserPromptSubmit) -> same checkpoint (`before-limit`), then the existing handoff advice.

## Gates
paid/commit/install/publish tasks are never started or run by TZ. `start` refuses without `--approved`; the pack lists ready gated tasks as "do NOT run, ask owner".

## Measure
`tz next measure`: startup (reply 1 input+cache), pack (est), repeated ctx (cache_read after reply 1), work, verify (turns whose tool call is a test cmd), TZ overhead (hook output chars/4, est, from tzlive ledger). Savings vs old 30-80k discovery is NOT proven until a real fresh-session demo.

## Host limits
TZ cannot start/close sessions itself; it advises (`mcp__ccd_session__start_session` or "new chat, read handoff"). Plan-% limit checkpoint is token-growth based inside hooks; exact provider quota only where `tz status --rate-limits` is given. Test-pass detection is output-text heuristic.

## Context continuity (v0.4, `bin/tzcont.py`)
- `tz state`: builds `handoffs/STATE.md` (<=60 lines) from the repo: Master (README objective, top-level dirs, last MASTER.md decisions, limits), Current work (tz next tasks done/active/blocked/pending, changed files, git, last test, next action), Session handoff (newest note + resume line). Each section's hash sits in a comment line; the file is rewritten only when a section's facts change. HANDOFF.md and dated notes are never rewritten.
- `tz expensive`: signals from the chat log (`usage` lines: context [actual], turns, input-equivalent spend [est] with cache read 0.1x, write 1.25x, output 5x) plus repeated unchanged reads from `reads-<session>.json` [measured]. Expensive when context >= `limit`, spend >= 20x `limit`, or >= 3 repeated reads with context >= limit/2. Then: `tz next` checkpoint, STATE.md refresh, and a check that STATE.md's git line equals git now (VERIFIED or NOT verified). Prints the MANUAL STEP line: the desktop host has no API to open a new chat, so the owner opens it.
- Hook: `tz-guard.py` UserPromptSubmit, once per session (`cont-<session>` marker), only when growth past chat start >= limit/2 and the `next_task` advice is on (off in mode `off`). Below the limit it speaks alone; at the limit it is appended to the existing limit message.
- `tz waste-audit`: duplicated lines (>=40 chars) across handoffs/*.md + HANDOFF.md, notes over 4k chars, repeated reads across sessions, user messages >= 2000 chars (pasted briefs) and their repeats. No chat log => briefs shown as unknown.
- `tz stats`: ledger events with basis other than measured/est are counted as unknown events, never as tokens. NET = measured avoided - TZ overhead. Cache reads are never counted as waste or savings.
- Tests: `tests/test_cont.sh` (25 checks, offline, temp HOME), incl. the guard `output-trim` ledger write.
