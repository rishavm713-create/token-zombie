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
All tested by `tests/test_gaps.sh`. DONE: (1) `tzstartup.mcp_cost` per-server MCP schema cost in `tz startup`: MEASURED chars from the logged request shape (tokens = chars/4 EST), or EST from deferred names only (130 tok/tool); (2) handoff `chain` id + `seq` kept across handoffs, `tz import --from CHAT.jsonl` rebuilds facts (last asks, edited files, last errors) from a crashed log, MEASURED, no model call; (3) `tzstartup.ci_audit` prints the newest GitHub Actions result via `gh` (MEASURED) or UNAVAILABLE, advice only; (4) `tz compress` handles .js/.jsx/.ts/.tsx/.mjs/.cjs by brace matching (bodies of top-level/class functions -> `{ ... }`), fails open, no JS AST; (5) `tz rework` adds a 0-100 rework score = weighted ratio of MEASURED counts (not a quality or saving claim). Agent-ROI view already exists (`tz live agents`, tzlive.py), so nothing from the research list is open. `gh run list` parsing checked against the real repo. Internal docs moved to `docs/internal/`. plugin.json already 0.4.0.

## Update (gap round 2, 2026-11-23)
DONE + tested (`tests/test_gaps.sh`): `tz attr` per-MCP-server and subagent calls/result size from a chat log (MEASURED chars, EST tokens; cost attribution only for results, schema cost is in `tz startup`); `tz conflicts FILE...` heuristic always/never contradictions across instruction files; churn -> checkpoint advice in `tz rework` (score >= 30 or a retry loop). Still not built: task-level vault index, cross-agent file-overlap warning, skill-outcome correlation, 5h/7d usage view (needs host data), non-Claude adapters, semantic memory (deferred by owner), dashboard-vs-ledger savings reconciliation.

## Update (gap round 3, 2026-11-23)
DONE + tested (`tests/test_gaps.sh`, `bin/tzmore.py`): `tz reconcile` (ledger.json vs tz.db vault, AGREE/MISMATCH within 10%); `tz vault-find WORDS` (task-level keyword retrieval over spilled outputs, originals via `tz recall`); `tz overlap SESSION_DIR` (files edited by 2+ subagents); `tz skills-outcome` (per-skill average rework score, correlation only). Already existed before this round: skill/plugin inventory, park/unpark profiles, per-prompt skill advice, instruction conflicts (`tz capabilities`/tzcap), skill security vetting (`tz-vet.sh`). Still not built: 5h/7d official usage view (host data), non-Claude adapters, installing/registry discovery of third-party skills (needs owner approval + licence/security gate), semantic memory (deferred by owner), pricing coverage beyond econ.json.

## Round 4: model recommendation and instructions
- `tz route <prompt>` now prints a `/model <name>` line to type (EST, advice only; tz cannot switch the running chat model) and the subagent model.
- `tz route --write [FILE] [--yes]` writes a marked "model per task" rules block (haiku bulk, sonnet default, opus hard) into CLAUDE.md. Dry run without `--yes`; idempotent; only touches text between its markers. Test: tests/test_gaps.sh.

## Round 5: second competitor list, can TZ do it alone? (2026-11-23, honest; "ALONE" = no other tool needed)
Token/usage/context group (RTK, Context Mode, Claude Token Optimizer, Headroom, LeanCTX, Token Optimizer, ccusage, Usage Monitor, ccstatusline, Langfuse/otel/ai-observer, Claude Code Router): see FEATURE-PARITY-MATRIX. TZ does output trim, spill+recall, FTS search, AST/JS skeleton compression, usage/cost/burn, statusline, dashboard, startup+MCP audit, routing advice. NOT alone: official 5h/7d % (host data), OTLP/team export (rejected, local-first), real model switching/proxy routing (host limit; advice + CLAUDE.md rules only), real A/B proof (owner run).
Memory/handoff group: Claude-Mem (vector memory: not built, rejected), REMvisual/vasilispapg/marcj handoffs (BUILT: STATE.md, chain id, JSONL import, daily handoffs), Hermes compression (tz compact note + PreCompact), Caveman shadow (tz shadow), Agent Trail/Token Dashboard (tzusage parsing; tz attr), Context7 (live library docs: NOT built, needs network; out of scope), wshobson/agents + Superpowers + gstack + Ponytail (workflow/role skill packs: NOT built; TZ gives lean rules + `tz route --write`, not a methodology framework).
Skill collections (Everything Claude Code, Matt Pocock, Karpathy, Anthropic Skills, Osmani, UI UX Pro Max, Impeccable, Claude SEO, Humanizer, Planning with Files, Anthropic Plugins, Google/OpenAI/Copilot/HF skills): these are CONTENT, not token tools. TZ can inventory, grade, conflict-check and cost them (tzcap, tz-vet, tz conflicts, tz overlap, tz skills-outcome) and its core rules cover the Karpathy-style points (smallest change, read before edit, state assumptions); planning-with-files is covered by STATE.md/handoffs. TZ does NOT ship design/SEO/writing skills and will not claim to.

## Round 6: improvements picked from the competitor review (all local, MEASURED)
- `tz export [CHAT.jsonl] [--out F]`: usage totals as one JSON line (schema tz.export.v1) to a local file for jq/Grafana/DuckDB. No network; not OTLP.
- `tz find WORDS..`: task-level search over handoffs/*.md (all words match, file:line). Step 1 of Claude-Mem's 3-step retrieval; no vectors.
- `tz doctor`: one-screen health check (ledger, savings agreement, hooks, rules block).
- `tz reconcile` narrowed to `output-trim` rows (RTK rows are RTK's own savings, not in TZ's vault). Real data still MISMATCH: ledger 79,229 vs vault 7,450 tok. Cause not found; do not quote the dashboard savings figure.
- Host finding: no TZ hooks in ~/.claude/settings.json on this machine (install.sh re-run still owner-only).
