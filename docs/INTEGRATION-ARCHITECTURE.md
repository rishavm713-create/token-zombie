# TZ v2.1 integration architecture

One install, one hook dispatcher, one config, one runtime feature registry, one state folder, one benchmark.
No v2.1 feature registers its own hook entry; every feature is a function called from `bin/tz-guard.py`
(or `bin/tz-start.py` for SessionStart, as in 2.0).

## Single points
| concern | the one place | notes |
|---|---|---|
| install | `install.sh` / plugin hooks (`bin/tzhooks.py` table) | unchanged in v2.1: no new hook entries |
| hook dispatch | `bin/tz-guard.py` | all events; fixed order below |
| SessionStart | `bin/tz-start.py` | adds `tzfit.plan_inject` + `tzfit.fit` cap |
| config | env > `~/.claude/token-zombie/config.json` > profile defaults (`tzlib.cfg`) | `mode` off/lite/full/ultra |
| runtime feature switches | `tzlib.FEATURES` + `feature(name)`; `TZ_FEAT_<NAME>=0/1` or config `features` | `mode=off` turns every feature off |
| feature status board | `bin/tzfeatures.py` + `tzfeatures.json` (`tz features`) | documentation of status, NOT runtime toggles; not a duplicate |
| state | `~/.claude/token-zombie/` (per-session JSON, atomic tmp+replace) + `tzdb` SQLite ledger | v2.1 files: `stuck-<sid>.json`, `plan-<sid>.json`, `mem.db` |
| hook output cap | `tzfit.fit()` inside `emit()` and tz-start | head 60% + tail 40%, <= 9000 chars |
| benchmark | `tz bench matrix` (`bin/tzmatrix.py`, offline) and `tz ab` (paid, owner approval) | same arms list from `tzlib.FEATURES` |

## Runtime features (v2.1)
| feature | default | module | event |
|---|---|---|---|
| cache_ttl_auto | 1 | tzcont.cache_ttl | UserPromptSubmit idle advice uses measured 1h/5m TTL |
| dup_skeleton | 1 | tzcompress.outline via tzopt | PreToolUse Read duplicate deny carries an outline |
| safety_net | 1 | tzshell (parser) via tzops.safe | PreToolUse Bash |
| stuck_detect | 1 | tzstuck.check | PostToolUse / PostToolUseFailure; UserPromptSubmit resets |
| mcp_dedup | 1 | tztoolprune.mcp_dup | PreToolUse mcp__* (advice only) |
| plan_reinject | 0 | tzfit.plan_inject | SessionStart (pointer on startup, head+tail on compact/resume, hash-gated) |

On-demand only (CLI, never in a hook): `tz toolprune` (report; `--apply`/`--restore` explicit), `tz mem index|search`,
`tz next dep`, `tz rank --tokens`, `tz find`, `tz impact --diff`, `tz usage` (5h blocks, hit rate, usable %), skill `tz-craft`.

## Fixed order inside tz-guard (per event)
- UserPromptSubmit: supervisor tick -> stuck reset -> 2.0 advice (limits, idle with measured TTL, packs, churn).
- PreToolUse: policy engine -> Bash safety (tzshell) -> file claim guard -> MCP duplicate advice -> Read guards (dup deny with outline, big Read nudge).
- PostToolUse(Failure): breaker -> **stuck patterns** -> next-task record -> churn + loop line (skipped when tzstuck already spoke) -> output trim.
- every emit: `tzfit.fit` cap, one JSON object per run.

## Overlaps resolved (no double work)
| overlap | resolution |
|---|---|
| tzcont loop line vs tzstuck | tzstuck runs first; if it speaks, the tzcont loop line is suppressed for that call (`_stuck_said`). tzcont still records history and covers calls without results. |
| tz-start newest handoff vs plan_inject on resume | plan_inject skips when the plan file IS the newest handoff. |
| PreCompact plan injection | not possible (PreCompact output is not shown to the model); plan is re-injected at SessionStart source=compact instead. |
| tzops RULES regexes vs tzshell parser | parser is primary; RULES kept as fallback for unparseable text (fail closed when dangerous raw text is present). |
| tzsup ready()/blocked_by vs tznext deps | tznext owns task-pack deps and cycles; tzsup keeps its supervisor task board (different store, documented). |
| toolprune deny list vs user settings | writes only `.claude/settings.local.json`, records its own entries, restore removes exactly those. |

## Conflict policy
`tzmatrix.CONFLICTS` lists feature pairs that must not run together. Conflict tests (tests/v21/test_matrix.py and the
matrix `all-minus:<f>` arms) found none; the list is empty and the `all-minus-conflicts` arm equals `all`.
