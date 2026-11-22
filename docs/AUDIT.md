# Gap audit against the code (2026-11-22)

Labels: BUILT (code + test), PARTIAL, NOT BUILT, UNVERIFIED (code exists, no proof on a real run), HOST (depends on what Claude Code sends).
Basis: read of `bin/`, `install.sh`, `tests/`. Not a claim of savings; savings need real A/B runs.

## Proof layer
| Item | Label | Where / note |
|---|---|---|
| Hook overhead benchmark, all 18 events | BUILT (this round) | `tz hooks bench` now covers every registered event, MEASURED wall ms |
| Live per-event hook time | BUILT, UNVERIFIED | `tz hooks live`; needs the hooks installed |
| A/B runner with token caps | BUILT | `bin/tzab.py`, `tz bench compare`; zero real trials recorded yet = no proof |
| Net savings (savings minus TZ overhead) | BUILT (synthetic) | `tz bench`; real-session net needs A/B runs |
| Rework / retry-loop / repeated-edit counts | BUILT (this round) | `tz rework` (`bin/tzrework.py`, `tests/test_rework.sh`); counts only, not proven waste |
| Quality-adjusted savings | NOT BUILT | needs A/B runs with identical acceptance tests |
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
| Interrupted / cancelled agent states | NOT BUILT (host sends no signal) |
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
