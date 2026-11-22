# Competitive gap analysis (repo-based, 2026-11-23)

Scope: what TOKEN ZOMBIE has not built yet, taken from `IMPLEMENTATION-MATRIX.md`, `LIMITATIONS.md` and `COMPETITIVE-POSITIONING.md`. Competitor facts come from that positioning file and were **not re-verified against live repos** in this pass. No new web research, no code changes.

## Already built (do not rebuild)
Hook ledger (SQLite), 5m/1h cache accounting, agent lifecycle + ROI flags, reversible output trim + recall, Python AST skeleton, handoffs/checkpoints/resume, retry tracking, A/B runner, toolbar, dashboard, CLI, local-first with no telemetry.

## Missing or incomplete, ranked
| Pri | Gap | Why it matters | Who does it better |
|---|---|---|---|
| P0 | Real multi-trial A/B savings result (runner exists, no trial recorded) | Every strong competitor leads with one measured number; we cannot claim savings | Claude Token Optimizer, Context Mode |
| P0 | Live-host verification of hook payloads, overlay look | "Built" is unproven until seen on a real host | n/a |
| P1 | Short memorable command (we have `/token-zombie:tz`) | Recall and sharing | RTK (`rtk gain`) |
| P1 | Real demo GIF of the toolbar warning and a handoff | Fastest way to sell it | most top repos |
| P1 | MCP/plugin tool-schema cost (UNKNOWN today) and model pricing coverage | Big hidden token cost we cannot show | none verified |
| P2 | Rework/retry quality scoring, skill outcome correlation, intervention outcomes | Turns warnings into proven advice | none verified |
| P2 | Non-Python code compression (JS/TS) | Wider coverage of output trim | Context Mode (per positioning file) |
| P2 | Real adapters beyond Claude Code (7 are rules-file stubs) | Reach, but dilutes focus | Context Mode, Superpowers |
| P3 | Semantic/vector memory, task-level vault index | Cross-session recall | Claude-Mem |
| REJECT | Full Claude-Mem replacement, RTK clone, nine-tab UI, auto agent spawning, lossy compression, blocking tools | Owner decisions already made | n/a |

## Where TZ is differentiated (unproven on savings)
Every number is labelled MEASURED or EST; non-blocking advice; recoverable trims; zombie-agent detection; handoff survival checks. No verified competitor combines all of these, but that comes from the positioning notes, not a fresh audit.

## Next step
Run one real controlled A/B (same task, with and without TZ, logs published). Until then keep the "no savings figure promised" wording.
