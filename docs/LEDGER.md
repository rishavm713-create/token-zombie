# TZ v2.1 repo ledger (44 repos)

Checked 2026-11-25 against code at `8c703c3`. Detail: `docs/research/A-H`, `NOTICE`, and the older `OPEN-SOURCE-INTEGRATION-LEDGER.md` (36 rows, partly 2.0-era; this file wins where they differ).

Status (one per repo):
- **integrated**: TZ code can run or call the tool itself.
- **reused-with-NOTICE**: code or rules copied or adapted; credited in `NOTICE`.
- **idea-only**: independent code, or reference only. No source copied. A `NOTICE` idea credit may still exist.
- **rejected**: nothing taken; reason given.

"2.0" = built before v2.1. A test in the repo shows behaviour, not a token saving.

Count: integrated 2, reused-with-NOTICE 5, idea-only 29, rejected 8 = 44.

| # | Repo | Licence (as recorded in research) | Status | What TZ has / why not |
|---|---|---|---|---|
| 1 | DietrichGebert/ponytail | MIT | idea-only | 2.0 lean core rules merge its ideas (`bin/tz-start.py`). A proposed `tz debt` command is not built. |
| 2 | rtk-ai/rtk | split: `src/cmds` Apache-2.0, engine and proxy BUSL | idea-only | 2.0 strip-ANSI / collapse-blank idea (`tzcrush`, NOTICE). Porting rejected (Rust to Python cost). BUSL part not used. No new v2.1 filters. |
| 3 | mksglu/context-mode | ELv2 | idea-only | Behaviour reference only, reviewed shallowly. No source used. |
| 4 | headroomlabs-ai/headroom | Apache-2.0 | idea-only | 2.0 JSON outlier retention (`tzcrush`) and the `learn` idea (`tzlearn`). The proposed v2.1 log compressor is not built. |
| 5 | yvgude/lean-ctx | Apache-2.0 root (see its LICENSE.md) | idea-only | 2.0 re-read stub idea (`tzout`). Source reviewed shallowly. |
| 6 | obra/superpowers | MIT | idea-only | `skills/tz-craft` references, rewritten. |
| 7 | affaan-m/everything-claude-code | MIT | rejected | 328 skills, overlaps TZ; nothing needed. |
| 8 | anthropics/skills | no root licence found | rejected | Reviewed; nothing needed. |
| 9 | vercel-labs/agent-skills | no LICENSE file found | idea-only | `tz-craft` React notes written from scratch. |
| 10 | mattpocock/skills | MIT | idea-only | `tz-craft` (git safety and related), rewritten. |
| 11 | jokim1/karpathy-skills | MIT | idea-only | 2.0 `diffcheck` idea; `tz-craft` refactor rules. |
| 12 | EveryInc/compound-engineering-plugin | MIT | idea-only | `tz-craft` learn notes. No automatic learn loop. |
| 13 | EL4CTEO/fast-anything | MIT | idea-only | Rules only, in `tz-craft`. Rust CLI rejected. |
| 14 | thedotmack/claude-mem | Apache-2.0 | idea-only | Budget-fit idea in `tzfit.fit`. Its worker and Chroma stack rejected. |
| 15 | gastownhall/beads | MIT | idea-only | 2.0 ready-task idea; v2.1 dependency cycle refusal in `tznext`. |
| 16 | parcadei/Continuous-Claude-v3 | MIT | idea-only | Reference for plan re-injection (`tzfit.plan_inject`, off by default). |
| 17 | zilliztech/memsearch | MIT | idea-only | Chunker idea in `tzmem` (SQLite FTS5, own code). No vector store. |
| 18 | Fission-AI/OpenSpec | MIT | rejected | Reference read only; not adopted. |
| 19 | OthmanAdi/planning-with-files | MIT | reused-with-NOTICE | 2.0 `tail_lines` copied into `tzhandoff`; v2.1 plan re-injection rebuilt from the idea. |
| 20 | Aider-AI/aider | Apache-2.0 | reused-with-NOTICE | Repo-map ranking adapted in `tzrank`. |
| 21 | oraios/serena | `src/serena` GPL-3.0+, `solidlsp` MIT | idea-only | 2.0 `tz sym` rebuilt from behaviour; no GPL code. SolidLSP rejected as a dependency. Proposed name-path matching and `--refs` are not built. |
| 22 | tree-sitter/tree-sitter (+ py-tree-sitter) | MIT | integrated | Optional dependency for JS/TS skeletons (since 2.0.1). Not required, not extended in v2.1. |
| 23 | ast-grep/ast-grep | MIT | idea-only | Research selected a Python subset; **not built**. No `ast-grep`/`sg` call in the code. |
| 24 | SylphxAI/repomap | MIT | idea-only | Reference for impact output. Engine rejected as a dependency (Rust plus embedding model). |
| 25 | Yeachan-Heo/oh-my-claudecode | MIT | idea-only | Claim leases in `tzagent`. |
| 26 | ruvnet/ruflo | MIT (research note) | idea-only | Budget warning ladder proposed; **not built**. Claims and monolith rejected. |
| 27 | OpenHands/software-agent-sdk | MIT | reused-with-NOTICE | Stuck-pattern detector adapted in `tzstuck`. |
| 28 | SWE-agent/mini-swe-agent | MIT | idea-only | `--wall` and `--max-errors` limit behaviour in `tzagent`. |
| 29 | smtg-ai/claude-squad | AGPL-3.0 | idea-only | Behaviour list only; no code. |
| 30 | 23blocks-OS/ai-maestro | MIT | idea-only | Crash-restart backoff proposed; **not built**. Server stack rejected. |
| 31 | humanlayer/humanlayer | Apache-2.0 (research note) | idea-only | Claim-lease idea. |
| 32 | HKUDS/CLI-Anything | Apache-2.0 (LICENSE text read, commit 34f519533b) | rejected | GUI-to-CLI wrappers; no token-saving capability. `V2.1-PLAN.md` says "no licence"; research E read an Apache-2.0 file. Rejected either way. |
| 33 | ccusage/ccusage | MIT | idea-only | 5-hour blocks rebuilt in `tzusage`. |
| 34 | sirmalloc/ccstatusline | MIT | idea-only | "Usable context %" rebuilt in `tzusage`. |
| 35 | langfuse/langfuse | MIT core, EE directories commercial | idea-only | Trace model reference. No SDK, network or telemetry. |
| 36 | kenryu42/cc-safety-net | MIT | reused-with-NOTICE | 2.0 destructive-command rules adapted (`tzops`). v2.1 `tzshell` is a stdlib rebuild with parity tests; `NOTICE` has no separate `tzshell` line. |
| 37 | SWE-bench/SWE-bench | MIT | rejected | Needs Docker; reference only. |
| 38 | laude-institute/terminal-bench | Apache-2.0 | idea-only | Task format reference. |
| 39 | laude-institute/harbor | Apache-2.0 | integrated | Optional adapter `tz bench harbor`: prints the commands, runs them only with `--run` and only if `harbor` is installed. No real run done. No local bench-task set in the repo. |
| 40 | microsoft/TokenEconomizer | MIT | reused-with-NOTICE | Tool-prune rules ported (`tztoolprune`); arm-comparison method idea in `tzmatrix`. The micro-skills (repeat failure to saved fact) part is not built. |
| 41 | alexgreensh/token-optimizer | PolyForm Noncommercial | idea-only | Duplicate-read outline and duplicate-MCP advice rebuilt independently. |
| 42 | elementalsouls/Claude-BugHunter | recorded as no licence in `V2.1-PLAN.md` | rejected | Security scope engine; not a token feature. |
| 43 | ultraworkers/claw-code | MIT (LICENSE read; history and provenance unverified) | rejected | Its hooks and config overlap TZ; reference reading only, nothing taken. |
| 44 | morluto/rea | not reviewed | rejected | Reverse-engineering tool; not used (every target was readable source; no compiled targets). |

Not in the 44: `Tarquinen/opencode-dynamic-context-pruning` (AGPL, idea reference in research A). The directive's 45th entry is TZ's own repo.

`NOTICE` also credits several idea-only repos; they stay idea-only here because no code was copied.

# Spec status (25 items)

Source: `V2.1-AUTOMATION-SPEC.md`. Labels:
- **DONE**: built, wired, and covered by a test.
- **MEASURED**: DONE plus an offline measured effect (characters in a scripted run; never provider tokens).
- **EST**: works, effect only estimated.
- **UNKNOWN**: exists, behaviour or effect not verified.
- **MISSING**: not built, or built but nothing calls it. "Code only" marks the second case.

**Hook wiring of `bin/tztips.py` is in progress (other session).** At `8c703c3` no hook and no `tz` subcommand calls it. Its functions have tests (`tests/v21/test_tips.py`), so rows that depend on it show "code only". Recheck them after that work lands.

| # | Item | Status at 8c703c3 | Notes |
|---|---|---|---|
| 1 | Default model Sonnet, subagents Haiku | MISSING (code only) | `python3 bin/tztips.py defaults`; writes only with `--apply --yes`; `--restore`. |
| 2 | Earlier auto-compact | MISSING (code only) | `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` checked in docs. The tztips CLI passes no value, so it shows MISSING there. |
| 3 | Lower thinking / effort | MISSING (code only) | `effortLevel` checked in docs. Effect not measured. |
| 4 | Defer MCP definitions, park unused MCP | UNKNOWN (partial) | `tz toolprune` lists never-called tools and denies on `--apply`; on demand only. Idle parking and auto-restore not done. Deferral is the host's feature. |
| 5 | Duplicate / oversized instructions | UNKNOWN (partial) | 2.0 `tz instructions` reports on demand. v2.1 detect-and-fix is code only. |
| 6 | Duplicate read returns outline | MEASURED (opt-in) | Only with `read_guard: "deny"`; the default is advice. Matrix `dup_read` scenario: 2,717 chars saved, 1,411 injected. |
| 7 | Block whole-file big read | DONE (2.0), effect UNKNOWN | Denies once, with advice; a repeat is allowed. |
| 8 | Bulk reads to a Haiku Explore subagent | MISSING (code only) | |
| 9 | Big output trim with recall | MEASURED (2.0) | Most of the offline matrix saving comes from this (see `docs/LIMITATIONS.md`). |
| 10 | Automatic handoff | UNKNOWN (partial) | 2.0 writes a continuation note before compaction; `tz handoff` is on demand. Task-end and threshold writes: code only. |
| 11 | Next chat loads newest handoff only | DONE (2.0) | `tz-start.py`, head of the newest daily file, 30 lines max. |
| 12 | Terse rules injected | DONE (2.0), effect EST | Skipped when caveman or ponytail is enabled. |
| 13 | Task switch: offer new chat | EST (partial) | 2.0 stay-or-fresh line. Fresh chat button wording: code only. |
| 14 | Plan-mode nudge | MISSING (code only) | |
| 15 | Long instructions: offer skills | MISSING (code only) | |
| 16 | Fresh chat button at 50k | MISSING (code only) | A hook cannot press it; it can only ask. |
| 17 | Hard cap 150k, soft 50k / 100k | MISSING (code only) | 2.0 size warnings exist; the new block gate is not live. |
| 18 | Idle over 5 min: show cost | EST | 2.0 idle advice; v2.1 uses the measured cache life (1 h or 5 min). |
| 19 | Big paste: save and block | MISSING (code only, warn only) | `tztips.py` only warns; it does not block or convert a paste. |
| 20 | Model switch | MISSING (code only, advice only) | A hook cannot switch the model. |
| 21 | Chat started in home folder | MISSING (code only) | |
| 22 | Many small messages tip | MISSING | |
| 23 | Auto-archive offer | MISSING | Needs the app's settings tool and the user's yes. |
| 24 | `tz stats` context breakdown and daily totals | UNKNOWN (partial) | 2.0 `tz stats` has measured / estimated savings and 24 h figures. The breakdown is code only (`tztips.py breakdown`). |
| 25 | `tzab` combined benchmark | UNKNOWN | `tz ab` exists; no paid trial run (needs the owner's OK). Offline `tz bench matrix` is not a replacement. |

## Anthropic's 10 cost tips

| # | Tip | Rows | Status at 8c703c3 |
|---|---|---|---|
| 1 | Clear between tasks; `/compact` long chats | 13, 16, 17 | 2.0 advice live (EST). Gate and button text: code only. TZ cannot run `/clear` or `/compact`. |
| 2 | Keep CLAUDE.md short | 5, 15 | Report on demand (`tz instructions`). Detect-and-fix: code only. |
| 3 | Turn off unused MCP servers | 4 | `tz toolprune` on demand (partial). Effect UNKNOWN. |
| 4 | Cheaper model, lower effort for simple work | 1, 3, 20 | MISSING from hooks (code only). |
| 5 | Give exploration to subagents | 8 | MISSING from hooks (code only). |
| 6 | Plan mode and specific prompts | 14 | MISSING from hooks (code only). |
| 7 | Skills instead of long instructions | 15 | 2.0 skill packs stay parked; `tz-craft` references load on demand (its prompt hint `craft()` is not called by any hook). Offer: code only. |
| 8 | Hooks that cut big output | 9, 6, 7 | Live. Trim MEASURED offline. |
| 9 | Do not leave a chat idle | 18 | Live, EST. |
| 10 | Check usage (`/context`, `/cost`, `/usage`) | 24 | `tz status`, `tz stats` live; breakdown: code only. |

All tztips wiring: **in progress (other session)**.
