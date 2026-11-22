# TOKEN ZOMBIE: Vision, Status and Path to Best-in-World

**MAKE EVERY SINGLE TOKEN COUNT.**
*Stop the waste. Control the swarm. Protect the workflow.*

AI Agent Resource Intelligence & Orchestration Layer. Claude Code is the first integration.

Source: the owner's planning chat "Token Optimization System" (ChatGPT, 2026-11), merged with the real code in this repo on 2026-11-22.
Status labels: **BUILT** = code + tests exist, **PARTIAL** = works with known gaps, **NOT BUILT** = vision only.

---

## 1. Mission

Same task, equal quality, fewer resources. Maximise verified work per token without losing quality, security or unfinished work.

- The task is the limit, not the token budget. Unfinished work is never abandoned because a session ends; it continues safely in the next one.
- The goal is not to make AI do less. It is to make AI do more useful work with less waste.
- A 30% token cut is worthless if quality drops or the task stays unfinished.

## 2. The problem (what the owner hit using Claude Code)

1. **Context piles up.** Every step re-sends the whole chat: old instructions, screenshots, long briefs, file dumps. A one-line change still pays for the full history.
2. **Rediscovery.** The AI re-reads files, re-finds decisions and redoes finished work, because nothing reliably keeps project knowledge between sessions.
3. **Two bad choices.** Keep a bloated chat, or start fresh and pay to rebuild context.
4. **Agent and tool waste.** More agents, skills, plugins and MCPs add duplicate work and coordination overhead. More agents is not more output.
5. **No visibility.** A token counter does not say where tokens went: useful work, repeated context, cache, tool noise, or the optimiser's own overhead.
6. **Workflow churn.** Simple changes turn into long cycles of planning, redesign and re-reading.
7. **Limits stop real work.** The 5-hour or context limit hits before the job is done. Momentum is lost and setup repeats.

### Real incident that shaped the design
One UI change (a size change plus a crop) used about 68% of a 5-hour limit:
- The chat passed 100k tokens, and about 60 tool calls each re-sent all of it.
- About 8 design rounds were guesses instead of a preview or a question. This was the biggest waste.
- 9 screenshots stayed in context for every later step.
- It ran on Opus, which burns the limit faster than Sonnet.
- Other sessions on the same account shared the same 5-hour limit at the same time.
- TOKEN ZOMBIE warned at 100k, but by then the tokens were already spent.

**Lessons:**
- Detection after 100k is not enough. Preserve work and prepare a fresh session *before* context gets expensive.
- UI rule: make the exact requested change, show a preview, get approval, then build. Never redesign what the user did not ask to change.
- Fix continuity and accurate savings measurement before adding features.

## 3. The idea: four intelligences, not a token counter

| Intelligence | Question it answers |
|---|---|
| Resource | What does the AI consume, and is it worth it? |
| Execution | How should the AI work: which model, agents, tools? |
| Context | What does the AI actually need to know right now? |
| Continuity | Can the AI finish what it started, across sessions? |

## 4. The seven core systems

### 01 Zombie Detection: find activity that burns tokens without moving the task
Vision: repeated tool calls and reads, duplicate tasks and outputs, runaway or stalled agents, needless agent spawning, repeated instructions, loops.
- **BUILT:** duplicate-read detection, live and from logs (`tzopt.py`, `tz optimize`). Repeated-command detection. Live session ledger with agent lifecycle and dedupe advice (`tzlive.py`, `tz live`). Waste self-audit (`tz waste-audit`).
- **PARTIAL:** dedupe is advice only. With `read_guard: deny` it denies an unchanged re-read once.
- **NOT BUILT:** stalled or looping agent detection, duplicate work across parallel sessions.

### 02 Infection Control: keep the environment clean
Vision: context pollution, redundant instructions, duplicate skills and plugins, needless MCP servers, unsafe integrations, conflicting config.
- **BUILT:** capability inventory and overlap detection (`tzcap.py`, `tz capabilities`). CLAUDE.md size and duplicates (`tz instructions`). Security grading GREEN/YELLOW/RED (`tz-vet.sh`, `tz security`, `tz audit`). Skill packs parked off by default (about 735 skills, about 57k tok/chat EST kept out).
- **PARTIAL:** overlap detection is a keyword heuristic. MCP tool-schema cost is UNKNOWN.
- **NOT BUILT:** conflict detection between instructions. Auto-disabling a plugin or MCP (needs approval and host support).

### 03 Resource Intelligence: measure, don't guess
Vision: input, output, cache-read and cache-write tokens; model cost; context use; overhead; actual vs estimated savings; model fit.
- **BUILT:** usage from chat logs and burn rate (`tzusage.py`, `tz status`, `tz forecast`). Startup audit of what each new chat loads (`tzstartup.py`, `tz startup`). Hook overhead (`tzhooks.py`). Savings ledger, measured minus overhead (`tz stats`). rtk's measured Bash savings, live after every Bash call.
- **PARTIAL:** 5h and 7d limits are shown only when the host passes `rate_limits` (terminal status line). The desktop app does not, so the bar counts **per day** (local midnight), which is exact. Context % uses a 200k setting (EST).
- **NOT BUILT:** $ cost, subagent cost tracking, a proven A/B saving.

### 04 Agent Orchestration: make the agents you have more productive
Vision: task decomposition, dependencies, agent assignment, parallel vs sequential, lifecycle, output checks, duplicate-work prevention.
- **BUILT:** dependency-aware task list with a 2k-token task pack, gates and checkpoints (`tznext.py`, `tz next`). Supervisor and status bus (`tzsup.py`, `tz sup`).
- **PARTIAL:** agents are counted and tracked, not assigned.
- **NOT BUILT:** automatic task splitting and agent assignment, cross-agent duplicate-work prevention, file locks between sessions.

### 05 Context Intelligence: give the AI only what it needs
Vision: compression, relevant retrieval, repeated-context detection, targeted reads, instruction dedupe, task-specific context.
- **BUILT:** output trim with full-text recall (`tzout.py`, `tz recall`), live-verified on Read, Glob and Grep, and seen live on 2026-11-22 on a 30k-char browser MCP result. Big-Read nudge. Lean start that injects only the top handoff block (`tz-start.py`). Output filter (`tz filter`).
- **PARTIAL:** trim fires only on outputs over 12k–20k chars.
- **NOT BUILT:** semantic retrieval of only the relevant code, and context built per task type.

### 06 Resource Survival Mode: protect unfinished work
Vision: threshold monitoring, exhaustion warnings, priorities, auto checkpoints, fewer background jobs, fresh-session prep, recovery.
- **BUILT:** warning at 100k and safe-point handoff at 175k (`tz-guard.py`). Plan % thresholds. PreCompact continuation note (`tz-compact.py`). Expensive-chat detection that writes a verified checkpoint (`tzcont.py`, `tz expensive`). Corrupt-state quarantine.
- **PARTIAL:** it warns but cannot stop the host. Fresh sessions are prepared, not forced.
- **NOT BUILT:** acting *before* waste: checkpoint and switch at the first sign of churn, not at 100k.

### 07 Autonomous Project Continuity: the flagship
Vision: persistent project memory, state tracking, handoffs, fresh-session start, cross-session continuation, dependency-aware resume, no rediscovery.

| File | Purpose | Status |
|---|---|---|
| MASTER (top of `handoffs/STATE.md`) | objective, architecture, decisions | BUILT (`tz state`) |
| `handoffs/STATE.md` | done / active / blocked / pending, files, git, tests, next action | BUILT |
| `handoffs/YYYY-MM-DD.md` (DAILY) | recent progress, at most 30 lines | BUILT (owner rule) |
| Session handoff | 1–2k token note for the next chat | BUILT (`tz handoff`, `tz task-wrap`) |
| Checkpoint | recoverable state of unfinished work | BUILT (`tz checkpoint`, `handoffs/tasks/T-*.json`) |

Rules: keep exact file refs; never mark unverified work done (`task-wrap` closes only if the test passes); `tz resume` checks the handoff against git and tests.
- **NOT BUILT:** auto-launching the next session. The host gives no supported way, so `tz sup next-session --yes` only starts a headless `claude -p` on request.

## 5. Operating modes

| Vision (task modes, auto) | Built today (profiles, `tz mode`) |
|---|---|
| Quick: minimal context, fast | `off`: thresholds kept, all advice silent |
| Standard: balanced | `lite`: big-Read nudge, next-task tip at 150k |
| Research: sources, evidence, verify | `full` (default): all advice, 100k |
| Engineering: code, test, agents | `ultra`: 60k tip, 120k hard, 20 KB read warn |
| Audit: deep security and quality | |

`tz classify` / `tz route` pick a task mode and the cheapest capable model (keyword heuristic, EST).
**Gap:** the five task modes should change real behaviour (context, model, agents), not only the advice thresholds. A manual override always wins.

## 6. Capability discovery

Each resource is tracked in 5 states: **installed, discovered, enabled, loaded, invoked** (`tz live skills`). TZ recommends the right pack per task (`tz profile`, skill-pack hint on each prompt) and never loads "just in case".
**Gap:** cleaning up temporary resources after a task. MCP and plugin enable or disable (host limit).

## 7. Model routing

Simple formatting → light model. Basic code → economical model. Architecture → strong reasoning model. Research → research flow. Security → audit flow.
- **BUILT:** advisor only (`tzroute.py`). TZ cannot switch the running chat's model and never overrides a manual pick.
- **Gap:** routing subagents automatically, and measuring the quality loss of each route.

## 8. Autonomous task loop (target workflow)

1. Understand the objective: deliverable, requirements, constraints.
2. Analyse resources: models, tools, skills, agents, context.
3. Plan: dependent, verifiable work units.
4. Pick a strategy: least overhead that does the job.
5. Execute: coordinate, watch for repeats, trim context.
6. Verify: test the output against the request.
7. Preserve: save state, unfinished work and the next action.
8. Report: done, cost, savings, limits.

## 9. Live HUD

Toolbar above the prompt (desktop Mod `hooks/panel.tsx`), dashboard (`tz dash`) and terminal status line (`tz-status.py`).
- **Four metrics:** Agents Running, Skills Used, Tokens Saved, Optimizations Executed. Real data only; values are labelled MEASURED, EST or UNKNOWN. Savings and optimizations count today (since 00:00), across all chats.
- **Also:** mode, health, context %, model, agent activity, zombie alerts, continuity status, last checkpoint, active optimizations.
- Mascot: original 3D zombie gripping the bar's top edge. Its state is alert, excited, working, sleep or idle (see METRICS.md).
- Note: the desktop Code tab does not render custom status lines; the Mod bar is the desktop view.

## 10. Measurement

**Net savings = verified avoided consumption − TOKEN ZOMBIE overhead.**

Measure tokens before and after, repeated context avoided, reads avoided, model and agent overhead, handoff and startup cost, optimizations run, task quality and time.
- **BUILT:** `tz bench` (synthetic, MEASURED vs EST), `tz stats`, the ledger, the A/B runner (`tzab.py`) and preflight (`tz preflight`).
- **NOT BUILT:** a real paid A/B result (blocked: isolated login 401; needs owner approval and a cost estimate). Until then, website claims stay unproven.

## 11. Security, privacy, control

Local-first state in `~/.claude/token-zombie/`. No conversation uploads, no hidden telemetry, no exposed keys (redacted `errors.log`). Never auto-approves dangerous commands. Permission-aware. Manual model override always wins. No destructive cleanup without approval. Never edits `settings.json`, installs, commits or publishes without approval. Every change is reversible (`.bak` files).

## 12. Install and ecosystem

One control centre (`tz`). User-level plugin across all Claude Code chats. Light startup, no always-on MCP, no permanent context injection. Enable or disable with `tz mode`. Upgrade, recovery and safe uninstall. Adapters: Claude is REAL; 7 others generate rules files only.
- **NOT BUILT:** public GitHub repo and release package, professional website, one-command public install.

## 13. Working rules (from the v0.1 build brief)

1. Stop re-researching and re-planning. Reuse working code. Implement, don't explain.
2. Audit and finish: find unfinished or unwired features before building new ones.
3. Integrate: one CLI, one config, shared state (status bus). Keep hooks light. No needless AI calls.
4. Test everything in isolated configs. Never claim a pass without running it.
5. Ship honest docs: README, install, config, features, security, CHANGELOG, limitations, test report.
6. Safety: preserve work; no settings, install, uninstall, commit, publish or delete without approval.
7. If it can't be done reliably, document it. Never pretend.

## 14. Path to best-in-world (priority order)

1. **Prevent, not detect.** Checkpoint and offer a fresh session at the first churn signal: repeated design rounds, screenshot build-up, the same file re-read, or a chat growing fast on small edits. Don't wait for 100k.
2. **Prove savings.** Run the approved A/B on a real task and publish the measured net saving, with quality held equal.
3. **Real 5-hour window.** Use `rate_limits.resets_at` when the host sends it; read Claude's "You've hit your session limit · resets 9:50pm" message as ground truth; keep the per-day count as the fallback.
4. **Savings beyond Bash.** Count avoided duplicate reads and trimmed Read, Grep and MCP output as measured entries, so TOKENS SAVED reflects all real work.
5. **Subagent and $ cost.** Per-agent tokens, per-model cost, and the overhead of hooks re-injected into each subagent (about 2.1k tok each, EST).
6. **Task modes that act.** Quick, Standard, Research, Engineering and Audit change context, model advice and agent count, not only the thresholds.
7. **Multi-session safety.** File locks or a claim board, so parallel sessions never edit the same files.
8. **Ship it.** GitHub repo, release package, website, public install. Claims only from measured data.

## 15. Definition of done (v1)

Installs safely on approval. Audits startup overhead. Shows real context and usage. Cuts repeated work. Writes compact, verified handoffs and resumes from verified state. Forecasts usage where the host allows. Reports measured vs estimated savings, net of its own overhead. All tests pass. Clear docs. Every number on screen is real or labelled.
