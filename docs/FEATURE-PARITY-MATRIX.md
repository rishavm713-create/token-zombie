# Feature parity matrix (2026-11-23)

TZ column is checked against `docs/IMPLEMENTATION-MATRIX.md`, the modules in `bin/` and `bash tests/run_all.sh`. Labels: BUILT+TESTED · PART (partial) · NOT BUILT · HOST (needs real-host check) · N/A (rejected by owner).
Leaders = competitors whose page states the capability (VERIFIED on their page).

| # | Capability | TZ | Leaders | Note |
|---|---|---|---|---|
| 1 | Shell/tool output trimming | BUILT+TESTED (`tzout`, test_out) | RTK, LeanCTX, Context Mode | TZ has fewer filters than RTK (no per-tool filter catalogue) |
| 2 | Lossless recovery of trimmed text | BUILT+TESTED (spill, `tz recall`) | Headroom, LeanCTX, Token Optimizer | parity |
| 3 | Shadow / dry-run of savings | BUILT+TESTED (`tz shadow`) | LeanCTX | TZ also stages RECORD→ACTIVE |
| 4 | Code compression (AST) | BUILT+TESTED: Python + JS/TS (`tzcompress`, test_jsskel) | LeanCTX 27 langs, Headroom | other languages not covered |
| 5 | Search index over spilled/old output | BUILT+TESTED (FTS5) | Context Mode, Claude-Mem | TZ has no vector search (deliberate) |
| 6 | Usage + cost from local logs | BUILT+TESTED (`tzusage`, 5m/1h cache split) | ccusage, Usage-Monitor | ccusage covers ~20 agents; TZ real adapter = Claude only |
| 7 | Burn rate / limit forecast | PART (burn, next-request cost) | Usage-Monitor, ccstatusline | no official 5h/7d % view |
| 8 | Provenance labels (MEASURED/EST) | BUILT+TESTED | Usage-Monitor | TZ labels every number |
| 9 | Statusline / toolbar | BUILT; look not visually verified (HOST) | ccstatusline, Ponytail band | |
| 10 | Dashboard | BUILT+TESTED | LeanCTX, Token Optimizer, ai-observer | |
| 11 | Subagent lifecycle + ROI flags | BUILT+TESTED | none of the above state it | TZ-only |
| 12 | Compaction survival check | BUILT+TESTED (`verify_compact`) | Token Optimizer (checkpoint), Context Mode | |
| 13 | Handoff / resume | BUILT+TESTED (STATE.md, `tz resume`) | the 3 handoff tools | no crashed-session JSONL import, no handoff chain id |
| 14 | Startup-context audit | BUILT+TESTED (`tzstartup`, `tz audit`, CI run status via gh) | Claude Token Optimizer, Token Optimizer | |
| 15 | Skill/instruction cost intel | BUILT (HOST) (`tzcap`, InstructionsLoaded) | Token Optimizer | |
| 16 | MCP / tool-schema cost signal | BUILT+TESTED (`tz startup` per-server schema cost, `tz attr` per-server calls/tokens) | Token Optimizer (audits MCP) | |
| 17 | Model/cost routing | PART (`tzroute` advice) | claude-code-router acts, Token Optimizer nudges | TZ advice only (deliberate: no blocking) |
| 18 | OTLP / team analytics | NOT BUILT | ai-observer, claude-code-otel | out of scope for solo, local-first |
| 19 | Controlled A/B savings proof | PART: zero-cost replay `tz bench replay` on real logs (MEASURED net 0.58%); paid `tzab` A/B not run | Ponytail (self-reported) | answer quality still unmeasured |
| 20 | Real-host verification | HOST: 9 new hook events not live until install re-run | n/a | P0 gap |
| 21 | Persistent semantic/vector memory | NOT BUILT | Claude-Mem, Ruflo | N/A by decision |
| 22 | Nine-tab UI, RTK clone, auto agent spawning | N/A | n/a | rejected |
| 23 | Zero default telemetry, MIT, local-only | BUILT | Context Mode, Token Optimizer (none); RTK opt-in | TZ edge on licence |

Counts: 23 capabilities compared against 21 competitors. TZ: 13 built+tested or built, 6 partial, 2 not built, 2 rejected/N-A (rows overlap two statuses where noted).
