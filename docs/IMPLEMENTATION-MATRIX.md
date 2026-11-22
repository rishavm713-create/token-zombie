# Implementation matrix (final research brief, 2026-11-22)

Status: DONE = built + tested; PART = partly; HOST = needs owner to re-run `install.sh` (hooks are registered in repo files only); NO = not built.
Labels in output: MEASURED (read from files/hooks), EST (derived), UNAVAILABLE (host gives no data), NOT YET SUPPORTED.

| # | Requirement | Existing / built | Missing | Status | Test |
|---|---|---|---|---|---|
| 1 | Resource intelligence | econ.json, 5m/1h cache split in tzusage, burn, next-request cost | incremental byte-offset scan, Ledger/Priced/Mixed/Unpriced state. Built: 5m/1h cache split + thinking-token EST in `tzusage.totals` | PART | test_usage, test_tz |
| 2 | Context engine | compact note + `verify_compact` (deterministic), spill + FTS5 recall (handoffs, memory), shadow mode | AST compression, vault index by task/file/tool | PART | test_cont, test_out, test_live |
| 3 | Agent lifecycle | SubagentStart/Stop by agent_id, running/done states, duplicate-agent advice, ROI flags (small/empty/failed/duplicate/stalled/no-hook-record) | PENDING/INTERRUPTED/CANCELLED (host gives no signal) | PART | test_live |
| 4 | Zombie alerts with evidence | alerts carry evidence from ledger; compaction-weak advice | intervention/outcome tracking | PART | test_live |
| 5 | Terminal output optimisation | tzout trim, spill, recall, shadow | — | DONE | test_out |
| 6 | Capability/instruction intel | caps.jsonl, InstructionsLoaded -> `instr` (file, reason, bytes, est tokens) | — | DONE (HOST) | test_cap, test_live |
| 7 | Hook integration | 17 events registered in hooks.json + install.sh plan: + SubagentStart, InstructionsLoaded, PostCompact, PostToolUseFailure, PostToolBatch, PreModelSwitch, PostModelSwitch, WorktreeCreate, WorktreeRemove | PostCompact payload shape unverified; FileChanged registered (18 events) | DONE (HOST) | test_install*, test_plugin, test_live |
| 8 | Project continuity | STATE.md, handoffs, `tz resume`, tz state | — | DONE | test_continuity |
| 9 | Quality intelligence | compaction survival verdict, ROI flags | rework/retry scoring | PART | test_live |
| 10 | Shadow lifecycle | `out_trim=shadow` records would-be cuts, `tz shadow` report | none: `tz shadow` shows stage RECORD/RECOMMEND/SHADOW/CANARY/ACTIVE (advice only) | PART | test_out |
| 11 | Skill effectiveness | `tz live skills` | outcome correlation | PART | test_live |
| 12 | Unified ledger | live-<sid>.json (hooks, agents, calls, instr, compact, events, models, worktrees) + shadow.jsonl | single SQLite ledger | PART | test_live |
| 13 | Nine-tab UI wiring | `tz systems` -> systems.json (8 systems); UI untouched per owner | 9-tab panel does not exist in panel.tsx; owner decision | BLOCKED (owner) | plugin test |
| 14 | Overhead/security | all hooks file-only, flock, no model calls, path-traversal refused, timeout 5s | measured bench of new events | PART | `tz hooks bench` |
| 15 | Process | this matrix, LEFT.md, handoff | — | DONE | — |

Host approval needed: re-run `./install.sh` to activate the 9 new hook events (not run by the agent). Until then those fields read UNAVAILABLE.

## Update (round 4)
Built since the table above: `tzdb.py` single SQLite ledger (events/alerts/vault), alert evidence -> intervention -> outcome, vault index (by session, tool, file; original vs shown chars), `tzcompress.py` Python AST skeleton (validated, fail open, reversible via recall), `tzusage.totals_inc` incremental scan, `acct_state` Ledger/Priced/Mixed/Unpriced. Dropped by owner: nine-tab UI. Still not built: semantic memory, non-Python AST, task-level vault index, auto canary->active.

## Update (gap round, 2026-11-23)
All tested by `tests/test_gaps.sh`. DONE: (1) `tzstartup.mcp_cost` per-server MCP schema cost in `tz startup`: MEASURED chars from the logged request shape (tokens = chars/4 EST), or EST from deferred names only (130 tok/tool); (2) handoff `chain` id + `seq` kept across handoffs, `tz import --from CHAT.jsonl` rebuilds facts (last asks, edited files, last errors) from a crashed log, MEASURED, no model call; (3) `tzstartup.ci_audit` prints the newest GitHub Actions result via `gh` (MEASURED) or UNAVAILABLE, advice only; (4) `tz compress` handles .js/.jsx/.ts/.tsx/.mjs/.cjs by brace matching (bodies of top-level/class functions -> `{ ... }`), fails open, no JS AST; (5) `tz rework` adds a 0-100 rework score = weighted ratio of MEASURED counts (not a quality or saving claim). Open from research: agent-ROI view (ROI flags exist in `tz live agents`). Internal docs moved to `docs/internal/`. plugin.json already 0.4.0.
