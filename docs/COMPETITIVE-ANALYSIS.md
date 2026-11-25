# TZ v2.1 competitive analysis

Written 2026-11-25 from repo research notes (`docs/research/A-H`) and the ledger (`docs/LEDGER.md`). No competitor was benchmarked against TZ, so nothing here says TZ is better or cheaper than another tool. Other projects' own savings claims were not reproduced and are not quoted. The older web-researched gap list is `COMPETITIVE-GAP-ANALYSIS.md` (2026-11-23).

## What others do, and where TZ stands
| Area | Others (reviewed) | TZ v2.1 | Open gap |
|---|---|---|---|
| Shell output filtering | RTK: broad per-command filters | 2.0 output trim with `tz recall`; no new v2.1 filters | Far narrower than RTK. TZ does not replace it. |
| Context compression / gateway | headroom, lean-ctx, context-mode | Python outline, JSON outlier keep, outline on denied duplicate read | No proxy, gateway or log compressor. Those three were reviewed unevenly (lean-ctx and context-mode shallowly). |
| Unused tool pruning | TokenEconomizer toolprune, token-optimizer | `tz toolprune`: report, deny on `--apply`, `--restore` | No idle parking or auto-restore. |
| Prompt-cache awareness | opencode-dynamic-context-pruning (history rewriting) | Measures 1 h vs 5 min cache life and uses it in idle / fresh-chat advice | TZ does not rewrite history. |
| Memory | claude-mem, memsearch, Continuous-Claude-v3, beads | `tz mem` (local SQLite FTS5, keyword), handoff files, task dependencies | No semantic search, no background worker. |
| Repo intelligence | aider, serena, ast-grep, repomap | `tz rank`, `tz find-code`, `tz impact --diff`, `tz sym`, `tz exists` | No LSP, no AST pattern search. Text-based references. |
| Skills | superpowers, mattpocock, anthropics, vercel, everything-claude-code | One `tz-craft` skill, references loaded on demand | Much smaller catalogue by choice. |
| Orchestration | oh-my-claudecode, ruflo, claude-squad, ai-maestro, OpenHands, mini-swe-agent | Stuck detect, claim leases, wall-clock and error limits in `tz agent` | No multi-agent dashboard, budget ladder or crash restart. |
| Shell safety | cc-safety-net, humanlayer | Parsed destructive-command check (`tzshell`), parity tests | A guard, not a sandbox. No approval service. |
| Usage view | ccusage, ccstatusline, langfuse | 5 h blocks, cache hit rate, usable context % (in `tz status`; the 5 h block only when the host gives no limits) | No money costs in v2.1 additions, no tracing backend. |
| Benchmarks | SWE-bench, terminal-bench, harbor | Offline `tz bench matrix`; optional harbor adapter | No task-quality benchmark has been run. |

## What TZ can say about itself
- Local only, stdlib hooks, no telemetry, MIT.
- Output trims keep the original (`tz recall`).
- Numbers are labelled MEASURED / EST / UNKNOWN.
- The offline matrix counts false positives and false negatives next to characters saved.

## What TZ cannot say
- That it saves a given share of anyone's bill. The one earlier zero-cost replay (2.0, 2026-11-23) measured net 0.58% input-equivalent saved on one machine's logs. The real usage database showed TZ 2.0 saving about 0.07% of the last 24 h of usage (from the task brief, not rerun here; a different method). Neither covers v2.1.
- That answers are as good or better with TZ: no quality A/B has run.
