# Gap audit against the code (2026-11-22)

Labels: BUILT (code + test), PARTIAL, NOT BUILT, UNVERIFIED (code exists, no proof on a real run), HOST (depends on what Claude Code sends).
Basis: read of `bin/`, `install.sh`, `tests/`. Not a claim of savings; savings need real A/B runs.

## Proof layer
| Item | Label | Where / note |
|---|---|---|
| Hook overhead benchmark, all 18 events | BUILT (this round) | `tz hooks bench` now covers every registered event, MEASURED wall ms |
| Live per-event hook time | BUILT, UNVERIFIED | `tz hooks live`; needs the hooks installed |
| A/B runner with token caps | BUILT | `bin/tzab.py`, `tz bench compare`; controlled multi-trial A/B remains incomplete |
| Net savings (savings minus TZ overhead) | BUILT (synthetic) | `tz bench`; real-session net needs A/B runs |
| Rework / retry-loop / repeated-edit counts | BUILT (this round) | `tz rework` (`bin/tzrework.py`, `tests/test_rework.sh`); counts only, not proven waste |
| Quality-adjusted savings | BUILT as `tz bench quality` (calculator); no real data | needs real A/B trials |
| Real-host hook verification | HOST / owner | run `./install.sh`, then `tz hooks live` |

## Accounting
| Item | Label |
|---|---|
| Incremental scan, partial last line, byte offsets | BUILT (`tests/test_usage.sh`) |
| SQLite ledger, alert outcomes, vault index | BUILT (`tzdb.py`) |
| Cache 5m/1h split, thinking estimate | BUILT (thinking is EST) |
| Model pricing completeness | PARTIAL |
| Subagent / MCP cost attribution | PARTIAL |
| Subscription quota vs API-equivalent | PARTIAL |

## Intelligence
| Item | Label |
|---|---|
| Agent start/stop/ID, ROI, stalled flag | BUILT; stalled is inferred (EST) |
| Interrupted agent state | PARTIAL: agent still running at SessionEnd is marked interrupted (test_hooklive); user-cancel mid-session has no host signal |
| Idle-agent, overlapping-agent detection | PARTIAL |
| Skill effectiveness vs outcomes | PARTIAL (no outcome correlation) |
| Instruction conflict detection | PARTIAL (`tzcap.py`) |
| Compaction verification | BUILT, HOST (needs `compact_summary` from host) |
| Reversible output + recall | BUILT |
| Python AST compression | BUILT; other languages NOT BUILT |
| Keyword memory | BUILT; semantic/vector NOT BUILT (not needed yet) |
| Task-level vault index | NOT BUILT |
| Shadow lifecycle | BUILT, advice only; auto CANARY->ACTIVE NOT BUILT (deliberate) |

## Host integration
| Item | Label |
|---|---|
| Idempotent install, `--check`, `--dry-run`, `--restore`, `--uninstall` | BUILT (`install.sh`, `tests/test_install*.sh`) |
| Duplicate-hook protection | BUILT (install touches only token-zombie commands, idempotent) |
| Official hook-event coverage audit | NOT DONE: 18 events used; the host has more, choose by value and measure overhead |
| Non-Claude adapters labelled experimental | PARTIAL |

## Product
Website redesign: lowest priority by owner decision. Real demo video and launch: owner.

## Not building (decided)
Nine-tab UI, RTK-style clone, full Claude-Mem replacement, auto agent spawning, vector memory before keyword retrieval proves insufficient, lossy source compression, blocking tools to save tokens.

## Final audit table
Real-host status is NOT VERIFIED for every row until the owner runs docs/HOST-VERIFY.md. Evidence = test file in this repo (synthetic data).
| FEATURE | IMPLEMENTATION | TEST | REAL-HOST | EVIDENCE | REMAINING LIMITATION |
|---|---|---|---|---|---|
| 18-event hook ledger | BUILT | test_install*, test_live | NOT VERIFIED | suite 795/0 | host payload fields unconfirmed |
| Hook overhead | BUILT | tz hooks bench | live NOT VERIFIED | 28-89 ms/event on dev machine | live p50/p95/fail counts BUILT (tz hooks live, test_hooklive), need install to fill |
| Incremental scan + accounting | BUILT | test_usage | n/a | suite | pricing/MCP/subagent attribution PARTIAL |
| SQLite ledger, alerts, vault | BUILT | test_out | NOT VERIFIED | suite | task-level index NOT BUILT |
| Agent lifecycle/ROI/stalled | BUILT | test_live | NOT VERIFIED | suite | stalled is EST; interrupted at SessionEnd BUILT; mid-session cancel NOT BUILT |
| Compaction verification | BUILT | test_out | HOST DEPENDENT | suite | needs `compact_summary` |
| Python AST compression | BUILT | test_out | n/a | suite | Python only |
| Rework counts | BUILT | test_rework | NOT VERIFIED | suite | counts, not proven waste |
| Install/uninstall/restore | BUILT | test_install, test_install2 | NOT VERIFIED | suite | Linux unverified |
| A/B runner + compare | BUILT | test_ab, test_bench | NOT RUN | none | zero real trials: no savings claim |
| Quality-adjusted savings | BUILT (calculator) | test_bench | NOT RUN | synthetic only | no real trials to feed it |
| Website | PARTIAL | none | n/a | docs/index.html | redesign pending, lowest priority |
Launch readiness verdict: NOT launch-ready. Engineering substantial; proof (A/B, host verification), demo and website outstanding.
