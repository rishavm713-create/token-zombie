# Competitive gap analysis (web-researched, 2026-11-23)

Replaces the earlier repo-only version. Sources: `COMPETITIVE-INTELLIGENCE.md` (21 competitors, VERIFIED vs CLAIM) and `FEATURE-PARITY-MATRIX.md`.

| Pri | Gap | Why it matters | Effort |
|---|---|---|---|
| P0 | No real A/B run (only measured 153,372 tokens; no controlled baseline) | Every leader leads with a number; TZ must not publish one it cannot prove | Needs real sessions: `tz bench` runner exists; owner runs it |
| P0 | Live-host verification: re-run `./install.sh`, check toolbar look, 9 hook events | Several features read UNAVAILABLE until then | Owner, ~15 min |
| P1 | MCP / tool-schema cost signal | Token Optimizer audits MCP; a big hidden cost | Small–medium |
| P1 | 30-second demo GIF of the real toolbar | RTK/Ponytail convert on a visual | Small, needs real capture |
| P1 | Handoff chain id + import of crashed-session JSONL | REMvisual and vasilispapg do this | Small |
| P2 | Official 5h/7d usage view | Usage-Monitor, ccstatusline show it | Medium (host data) |
| P2 | JS/TS skeleton compression | LeanCTX 27 langs | Medium |
| P2 | Rework/retry scoring | Matrix row 9 | Medium |
| P2 | CI-failing startup audit | Claude Token Optimizer | Small |
| P3 | Real adapters beyond Claude | ccusage ~20 agents | Large; low value for Claude-first tool |
| REJECT | Nine-tab UI, RTK clone, full Claude-Mem replacement, auto agent spawning, early vector memory, lossy compression, blocking tools | Owner decisions | — |

TZ advantages confirmed: subagent ROI flags (no competitor page states them), MEASURED/EST labelling on every number, MIT licence with no telemetry, fail-open lossless trimming with `tz recall`, compaction-survival check.
