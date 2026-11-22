# The four headline metrics

The Mod toolbar (the bar above the prompt) and the HTML dashboard show the same four numbers. Both compute them from the same files with the same rules: `hooks/panel.tsx` (`writeAgents`, `countSkills`, `ledger`) and `bin/tzdash.py` (`metrics`).

Every number carries a label:
- **MEASURED**: read from a real file or host event.
- **EST**: an estimate with a stated basis.
- **UNKNOWN**: there is no data, so the number is shown as `—`.

No number is ever made up.

State files live in `~/.claude/token-zombie/`.

## AGENTS (dashboard: AGENTS RUNNING)
- **What it is:** the number of subagents with status `running` in the current Claude Code session.
- **Source:** the panel Mod calls `$.agent.list()` every 5 s. It writes `agents.json` as `{running, total, ts}` when the count changes, and otherwise once a minute.
- **Dashboard:** it uses `agents.json` only when `ts` is at most 180 s old. Otherwise it shows `—` UNKNOWN.
- **Label:** MEASURED.
- **Limits:**
  - It needs the panel Mod to be loaded. With hooks alone it is UNKNOWN.
  - It covers one session. Several open sessions write the same file, and the last write wins.
  - It counts subagents, not teammates or other Claude processes.

## SKILLS USED (Mod bar) and SKILLS ENABLED (HTML dashboard)
Five skill states, never mixed (`tz live skills` prints all five, MEASURED):
- **installed**: `SKILL.md` on disk: `~/.claude/skills`, parked `~/.claude/skills-off`, plugin cache.
- **enabled**: its description loads into every chat: `~/.claude/skills` plus skills of enabled plugins.
- **discovered**: TOKEN ZOMBIE suggested it in this session (pack hint).
- **loaded**: its body entered this chat (invoked, or the user typed `/name`).
- **invoked**: the model called the Skill tool for it in this session.
- **Mod bar SKILLS USED** = invoked skills in this session, from the hook ledger `~/.claude/token-zombie/live-<session>.json`. It shows a dash (UNKNOWN) until a hook writes that file.
- **HTML dashboard SKILLS ENABLED** = folders in `~/.claude/skills/` that hold a `SKILL.md`. That is not usage.
## TOKENS SAVED · EST
- **Window:** rolling last 24 h, all chats added together (owner 2026-11-22). Includes rtk's measured cut after each Bash call (kind `rtk`).
- **What it is:** tokens that TOKEN ZOMBIE actually cut from tool output, net of its own overhead.
- **Calculation**, over the entries in `ledger.json` (the last 2000 are kept):
  - `saved = Σ tok (basis = "measured", kind not starting "overhead") − Σ tok (kind starting "overhead")`
  - Each `tok` is `chars / 4`. The character count is measured; the char-to-token ratio is an estimate. That is why the total is labelled EST.
- **Where entries come from:**
  - `filter` entries: `tz filter` shrinking command output. The bytes removed are measured.
  - `overhead-hook` entries: the characters of advice that the guard hooks add to a chat. These are subtracted.
- **Left out:**
  - `dup-read-flagged` entries (basis `est`). A flagged duplicate read is only advice; nobody knows whether the model skipped the read.
- **Three kinds of saving:**
  - **Measured savings:** characters that were provably removed (the `filter` entries). This number is built from them.
  - **Estimated savings:** what flagged duplicate reads and similar advice *might* save. Never added to this number.
  - **Verified baseline savings:** the same task run with and without TOKEN ZOMBIE (the A/B harness in `tests/ab/`). **None exist yet.** No figure in this product is a proven end-to-end saving.
- **Limits:**
  - It measures only what passes through `tz filter`. Shorter chats from handoffs and earlier compaction are real effects, but they are not counted.

## OPTIMIZATIONS (dashboard: OPTIMIZATIONS EXECUTED)
- **Window:** rolling last 24 h, all chats.
- **What it is:** the number of `ledger.json` entries with `basis = "measured"` whose kind does not start with `overhead`. Each one is an action that actually ran, for example one filtered command output.
- **Label:** MEASURED.
- **Limits:**
  - An entry that cut 0 tokens still counts as executed.
  - Advice the model may or may not have followed is never counted.

## Mascot state
One state is picked, in this fixed order. The first rule that matches wins.

1. **alert:** status bus level CRITICAL, EXHAUSTED or APPROACHING LIMIT, or supervisor risk `high`.
2. **excited:** a task just closed, or a measured saving was logged in the last 120 s.
3. **working:** a turn is running (Mod only), a subagent is running, level ELEVATED, or hook-measured activity is `working`.
4. **sleep:** no status bus, a bus older than 30 min, or a level other than NORMAL.
5. **idle:** everything else.

`bin/tzzombie.py` (`visual_state`) and `hooks/panel.tsx` (`visual`) apply the same order. The dashboard chip shows the state that the SVG animates.

## Rolling 24h window (`tz stats`, 2026-11-22)
- `LAST 24H` = usage rows from `~/.claude/projects/**/*.jsonl` (main chats and `subagents/`), timestamp in the last 24 h, deduped by message id. Used = input + cache read + cache write + output [MEASURED]; cache reads dominate and are cheap re-sends.
- Split by main/agent and model. Ledger entries in the same 24 h: saved [measured], saved [est], TZ overhead [measured], each apart.
- History: one snapshot per local date in `~/.claude/token-zombie/history.json` (used, calls, measured, est, overhead); last 7 days printed.
- The panel's TOKENS SAVED block uses the same rolling 24 h (`tzdash.window`); the fresh-chat part is input-eq [EST].
- Fresh-chat saving [EST counterfactual from MEASURED contexts] (`tzopt.fresh_saved`): a chat started within 12 h after a chat of >= 50k in the same project; per call of the new chat, old last context - this call's context. A floor (the old chat would have grown). Written to `fresh.json` by `tz stats` and at chat start (detached). Per owner it is added into the panel/dashboard TOKENS SAVED number (today); the split "measured + fresh chats [EST]" is in the panel details and `tz stats`. Never written to the ledger as measured.
