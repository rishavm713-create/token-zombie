# REUSE: ideas from public repos (2026-11-22)

Method: read-only page fetches (README, LICENSE, visible source) by a Haiku fetch agent; nothing installed, cloned or run.
**Limit:** fetches were truncated, so source-level claims are partly unverified (marked). No code was copied, so no licence notice is needed yet.
Not done: the "top 50-100 repos" survey and benchmarks of Matt Pocock / Superpowers / ECC / gstack (stars are not evidence; needs real source reads + measured runs, own task).

| Repo | Licence | Telemetry / network (claimed) |
|---|---|---|
| tomstagl/cctop | MIT (fonts: SIL OFL) | none described; optional OpenTelemetry/rate-limit shim; unverified in code |
| camtrik/agent-trail | MIT | "local-only", SQLite `data/ingest.db`, read-only upstream DBs; unverified in code |
| nateherkai/token-dashboard | MIT | none claimed; stdlib Python; pricing.py/skills.py had no network calls (server.py/cli.py unread) |
| ryoppippi/ccusage | MIT | pricing from a LiteLLM file (fetched at build time in some builds) |
| mksglu/context-mode | not extracted (unverified) | README lists URL fetch/version checks/installs; "zero telemetry" claimed; benchmark % = single-author, unverified |
| thedotmack/claude-mem | Apache-2.0 | cloud sign-in, hosted observer, optional analytics, API keys; adds its own LLM cost |

## Per repo: idea, does TZ have it, worth building (value vs token cost)
| Repo | Idea | TZ has it? | Worth it |
|---|---|---|---|
| token-dashboard | 5 min / 1 h cache-write split pricing | was missing: one 1.25x factor | **BUILT** `tzcont._w1h/ieq/calls` (1 h writes 2x), test_cont §12. Zero extra tokens, local parse. Transcripts here carry `usage.cache_creation.ephemeral_1h_input_tokens` (checked) |
| token-dashboard | incremental scan: byte offset + mtime, skip unterminated last line | no (`tzopt.fresh_file`, `tzcont.skill_effect` rescan) | later, only if logs get slow; measure first |
| token-dashboard | skill catalog tokens = chars//4 | yes: `tzcap` inventory (~tok est) | no |
| cctop | per-reply attribution (skill/plugin/agent/MCP), unattributed = user work | no. Real transcripts here show only `attributionMcpServer/McpTool`, no skill field | investigate; MCP part could split cost per server (small), skill part not available |
| cctop | limit weight (cached + uncached x10 + create x12.5 + output x50) x tier | no | reject: plan-quota formula unverified |
| cctop | trailing 15 min burn rate | partly: panel burn (`tzstatus`/`panel.tsx`) | low |
| agent-trail | subagent replay/lineage, source-reported cost preferred over estimate | partly: `tz live agents` (`tzlive.py`), `tz replay` single transcript | low |
| ccusage | 5 h billing blocks, statusline | no | skipped by owner (LEFT 13) |
| context-mode | swap tool output > 4 KB for FTS5-matched chunks | partly: trim + `tz recall` (`tzout.py`), no ranking | reject: ranking gain unmeasured, adds a store |
| claude-mem | second-LLM observer memory | no (handoffs are deterministic, `tzhandoff.py`) | reject: extra LLM tokens, cloud |

Built this pass: only the cache-write split (high value for accuracy, ~10 lines). Nothing else met "high value, small, advice only".
