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

## SKILLS ON (dashboard: SKILLS ENABLED)
- **What it is:** the number of folders in `~/.claude/skills/` that hold a `SKILL.md`. These are user-level skills that are installed and switched on, so their descriptions load into every new chat.
- **Source:** a directory listing, refreshed at most once a minute.
- **Label:** MEASURED, for the count on disk only.
- **What it is not:**
  - It does **not** count skills that were *used*. A skill that is enabled but never invoked is still counted.
  - It leaves out plugin skills, project skills (`<project>/.claude/skills`) and skills parked in `skills-off`. The dashboard lists the parked ones separately ("N kept off", with an EST token cost).
- **Actual use:** `tz startup` reads the newest chat logs and reports "skill X: not invoked in the N newest chats". That is advice from the logs, not a toolbar metric.

## TOKENS SAVED · EST
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
