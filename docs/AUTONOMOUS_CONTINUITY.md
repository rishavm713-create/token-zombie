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
