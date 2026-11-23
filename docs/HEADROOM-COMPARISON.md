# Architecture comparison: Headroom vs TOKEN ZOMBIE (2026-11-23)
Source: Headroom README (headroomlabs-ai/headroom, Apache-2.0). Its savings numbers (21-57%) are its own claims, not verified by us. Independent code only.

| Layer | Headroom | TZ now | Decision |
|---|---|---|---|
| Interception | local proxy / library / agent wrap | host hooks (PostToolUse output replace) | Proxy NOT built: TZ has no network code by design. Hooks cover Claude Code only |
| Content router | ContentRouter picks JSON / code / text compressor | `tzcrush.kind` picks json / diff / log / text (BUILT this round, wired into tzout.cut) | BUILT |
| JSON | SmartCrusher | `tzcrush._json`: keep head/tail/error items, drop the rest with key summary | BUILT (simpler) |
| Code | AST compressors, 8+ languages claimed | Python AST only (tzcompress); JS/TS brace skeleton | PARTIAL; JS/TS needs a parser dependency |
| Text | Kompress model (HF, ML) | none | NOT built: needs a model download |
| Logs / diffs | yes | `_log` collapses repeats, `_diff` trims context | BUILT |
| Reversible (CCR) | `headroom_retrieve` | `tz recall ID` (original always spilled first, 0600) | BUILT; MCP retrieve tool NOT built |
| Cache awareness | CacheAligner flags volatile prefix | none | NOT built |
| Output-token cut | verbosity steering via proxy + holdout measurement | terse core rules injected by hook; no counterfactual measurement | PARTIAL |
| Failure learning | `headroom learn` | `tz learn` (BUILT: repeated tool failures -> CLAUDE.local.md block, dry run by default) | BUILT (failures only; no verbosity learning) |
| Cross-agent memory | shared store | handoffs/ + tz find, Claude-only | PARTIAL |
| Agents supported | ~16 via wrap | Claude Code real; others stubs | PARTIAL |
| Benchmarks | seeded reproducible table + accuracy evals | `tz benchmark`, A/B runner; no published results | owner step |
| TZ-only | | usage/limit forecast, subagent ROI, startup audit, handoff integrity, skill finder, local OTLP export | keep |
