# Competitive gap analysis (web-researched, 2026-11-23)

Replaces the earlier repo-only version. Sources: `internal/COMPETITIVE-INTELLIGENCE.md` (21 competitors, VERIFIED vs CLAIM) and `FEATURE-PARITY-MATRIX.md`.

| Pri | Gap | Why it matters | Effort |
|---|---|---|---|
| P0 | Answer-quality A/B not run. Zero-cost replay done 2026-11-23: 1,025 real chats, net 0.58% input saved after TZ overhead | Number is now MEASURED but small; quality effect unknown | `tz bench replay` (free); paid `tzab` for quality |
| P0 | Live-host verification: re-run `./install.sh`, check toolbar look, 9 hook events | Several features read UNAVAILABLE until then | Owner, ~15 min |
| P1 | MCP / tool-schema cost signal | Token Optimizer audits MCP; a big hidden cost | Small–medium | DONE |
| P1 | 30-second demo GIF of the real toolbar | RTK/Ponytail convert on a visual | Small, needs real capture |
| P1 | Handoff chain id + import of crashed-session JSONL | REMvisual and vasilispapg do this | Small | DONE |
| P2 | Official 5h/7d usage view | Usage-Monitor, ccstatusline show it | Medium (host data) | DONE |
| P2 | JS/TS skeleton compression | LeanCTX 27 langs | Medium | DONE |
| P2 | Rework/retry scoring | Matrix row 9 | Medium | DONE |
| P2 | CI-failing startup audit | Claude Token Optimizer | Small | DONE |
| P3 | Real adapters beyond Claude | ccusage ~20 agents | PART: Codex usage done; others not |
| REJECT | Nine-tab UI, RTK clone, full Claude-Mem replacement, auto agent spawning, early vector memory, lossy compression, blocking tools | Owner decisions | — |

TZ advantages confirmed: subagent ROI flags (no competitor page states them), MEASURED/EST labelling on every number, MIT licence with no telemetry, fail-open lossless trimming with `tz recall`, compaction-survival check.
