# Competitive intelligence (web-researched 2026-11-23)

Method: three read-only research passes fetched each project's GitHub page. **VERIFIED** = stated on the page as fact. **CLAIM** = the author's own marketing or self-reported number; nothing below was independently reproduced. Star counts are snapshots from the fetch date. One candidate (allytag/LeanContext) returned 404 and is excluded. Code of competitors was not read; only their README pages.

## A. Token saving / output compression
| Tool | Stars | Licence | What it does (VERIFIED) | Headline number (CLAIM) | Telemetry |
|---|---|---|---|---|---|
| RTK `rtk-ai/rtk` | ~87.5k | CLI Apache-2.0; engine BUSL-1.1 | Hook rewrites shell commands, filters test/git/ls/docker output, `rtk gain`, `rtk discover`, pipelines | "up to 90% less command output" (page admits not 90% cost) | opt-in |
| Context Mode `mksglu/context-mode` | ~34.4k | Elastic 2.0 | Sandbox execution, blocks big reads, SQLite FTS5 search, compaction resume block | "99.4% of output bytes saved" (author's bench) | none |
| Claude Token Optimizer `nadimtuhin` | 662 | MIT | Trims startup context (CLAUDE.md), audit, compress, prune, hooks | "11,000 → 800 startup tokens" (one project) | not stated |
| Headroom `chopratejas/headroom` | ~80.5k | Apache-2.0 | Proxy/lib, JSON/AST/prose compressors, reversible originals, cache-aware, shared memory | "21–57% fewer input tokens" on 4 scenarios | beacon ON by default |
| LeanCTX `yvgude/lean-ctx` | 4.0k | Apache-2.0 engine | 16 read modes, shell patterns, AST (27 langs), audit/proof, dashboard | none (table withdrawn; says savings can net to break-even) | configurable |
| Token Optimizer `alexgreensh` | ~3.0k | PolyForm Noncommercial | Checkpoint/restore, quality score, audits skills/MCP, status bar, delta re-reads | "24.80M tokens saved" (9.83M metered + 14.97M estimated) | none |

## B. Usage monitoring / observability
| Tool | Stars | What it does (VERIFIED) | Gap noted |
|---|---|---|---|
| ccusage `ryoppippi` | 19.5k | Daily/session/5h-block reports from local logs, cache tokens, ~20 agents, offline pricing, statusline | read-only; no benchmark |
| Claude-Code-Usage-Monitor `Maciek-roboblog` | ~8.8k | Live terminal monitor, burn rate, forecast, official 5h/7d % when fresh, provenance label per number | plan limits are fixed estimates |
| claude-code-router `musistudio` | 38.3k | Gateway: routing, fallback, key limits, request logs | acts on traffic; sees prompts |
| ccstatusline `sirmalloc` | ~13.7k | Statusline: cost, context %, cache hit rate/timer, 5h/weekly forecast | Anthropic usage API calls |
| ai-observer `tobilg` | 298 | OTLP backend + dashboard, DuckDB, MCP query of own telemetry | OTLP counts differ from session files (own caveat) |
| claude-code-otel `ColeMurray` | 525 | Grafana/Prometheus stack, team analytics | needs Docker; team-oriented |
| Langfuse Claude Code integration | n/a | Per-turn traces, tool spans, evals | sends prompts to Langfuse host |

## C. Memory / continuity / workflow
| Tool | Stars | What it does (VERIFIED) | Proof |
|---|---|---|---|
| Claude-Mem `thedotmack` | 119k | Observer agent, SQLite+FTS5+Chroma, progressive disclosure, viewer UI | none; page says its token figures are "not a measured saving"; analytics on by default; observer adds LLM spend |
| Superpowers `obra` | 324.1k | Skills framework: brainstorm, TDD, plans, subagent review | none quantitative; no persistent memory |
| Ponytail `DietrichGebert` | 196.8k | Writes less code; live cost "band"; ledger | CLAIM: 39 tasks ×5 runs, −26% cost, −45% tokens (methodology file not checked) |
| REMvisual/claude-handoff | 76 | /handoff, handoff chain, in-place compact swap | one qualitative A/B |
| vasilispapg/claude-handoff | 1 | JSONL → handoff.md offline, hooks, redaction | none |
| marcj/handover | 11 | /handover near 80%, living file, WIP commits | none; statusline daemon spends tokens |
| Ruflo (claude-flow) `ruvnet` | 82.3k | Swarm orchestration, vector memory, 100+ agents | CLAIM only; heavy footprint |
| wshobson/agents | 42.8k | 93 plugins / 199 agents catalog, multi-tool adapters | CLAIM; no memory |

## Cross-cutting findings
1. Almost nobody publishes an independent end-to-end cost benchmark. RTK, Claude-Mem and Token Optimizer admit output savings are not bill savings; LeanCTX withdrew its table. Only Ponytail publishes a controlled-looking scoreboard (self-reported).
2. Leaders lead with one big number and a demo. TZ has neither yet.
3. Default telemetry: Headroom and Claude-Mem are on by default; RTK opt-in; Context Mode and Token Optimizer say none.
4. Licences: RTK engine BUSL, Context Mode ELv2, Token Optimizer noncommercial. TZ is MIT.
5. Memory tools add background LLM cost (Claude-Mem, handover); handoff tools are mostly manual.
