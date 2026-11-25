<p align="center"><picture><source media="(prefers-color-scheme: light)" srcset="docs/img/logo-light.svg"><img src="docs/img/logo.svg" width="560" alt="TOKEN ZOMBIE. Make every single token count."></picture></p>

<h1 align="center">TOKEN ZOMBIE</h1>

<p align="center"><b>Stop paying for tokens Claude Code wastes.</b><br>Trims noisy tool output, warns before a chat overflows, saves your place. Free · Local · No telemetry · No AI calls of its own</p>

<p align="center"><a href="https://github.com/rishavm713-create/token-zombie/actions/workflows/ci.yml"><img src="https://github.com/rishavm713-create/token-zombie/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-4c9a1a" alt="MIT"></a> <a href="../.github/SECURITY.md"><img src="https://img.shields.io/badge/Local--first-no%20telemetry-83ffa0" alt="Local-first, no telemetry"></a> <img src="https://img.shields.io/badge/Platforms-macOS%20%7C%20Linux-555" alt="macOS and Linux"> <img src="https://img.shields.io/badge/Python-3-3776ab" alt="Python 3"></p>

```bash
claude plugin marketplace add rishavm713-create/token-zombie && claude plugin install token-zombie@token-zombie
```

![TOKEN ZOMBIE demo](docs/img/demo-bench.svg)

## What it does to one session (measured)

Scripted agent session, offline, 5 trials, no provider calls ([bench matrix](docs/bench/matrix-2026-11-25.md)):

| | TZ off | TZ all hooks on |
|---|---:|---:|
| Chars kept out of context | 47,724 | 54,852 |
| Chars TZ injects (its own overhead) | 199 | 1,880 |
| **Net chars saved** | 47,525 | **52,972** |
| False positives / false negatives | 0 / 0 | 0 / 0 |

Run `tz gain` to see your own number: it prints saved minus TZ's own overhead and says which part is measured and which is estimated.

## What you get

| Claim | Evidence |
|---|---|
| Long build/test/tool output trimmed, every failure line kept, original recallable with `tz recall` | Lossless by design; behaviour MEASURED in [bench matrix](docs/bench/matrix-2026-11-25.md) (offline chars, 5 trials) |
| Repeat reads, repeat MCP calls and stuck loops flagged early | MEASURED in the same matrix (false positives/negatives listed per arm) |
| Handoff note plus checkpoints, so a fresh chat continues | Covered by the test suite |
| Honest numbers: every figure labelled MEASURED / EST / UNKNOWN, TZ's own overhead subtracted | `tz stats` |
| Test suite | MEASURED 3685 pass, 0 fail, 2 skip on v2.1.0: [TEST_EVIDENCE](docs/TEST_EVIDENCE.md) |

**Honest size of the saving:** on a free replay of 1,025 real chats the net input saved after TZ's own overhead was **0.58%** (MEASURED, [gap analysis](docs/COMPETITIVE-GAP-ANALYSIS.md)). Provider tokens and answer quality: **UNKNOWN** (paid `tz ab` A/B not run). Your own number: `tz stats`.

## Quick start

1. **Install** with the command above, then restart Claude Code.
2. **Check:** run `/token-zombie:tz` (status) and `tz hooks live` (are the hooks firing).
3. **See your number:** `tz gain` (net tokens saved after TZ's own overhead, each line labelled MEASURED or EST).
4. **Work as usual.** Warnings and trimming happen by themselves; when a chat gets big, `tz handoff` saves your place and `tz resume` continues in a fresh chat.

CLI only, rollback and verification: [install guide](docs/INSTALL.md). The npm package `token-zombie` is not published yet (UNKNOWN until the owner publishes it), so do not rely on `npm i -g`.

## Why TZ

| | TZ | Output compressors (e.g. rtk, headroom) | Memory plugins (e.g. claude-mem) |
|---|---|---|---|
| Trims tool output | Yes, lossless with recall | Yes, their main job; stronger on raw reduction | No |
| Warns before context overflows, handoffs | Yes | Mostly no | Partly |
| Flags repeat reads, stuck loops, risky commands | Yes | No | No |
| Labels every number MEASURED / EST / UNKNOWN | Yes | Varies | Varies |
| Licence, telemetry | MIT, none | Apache-2.0 (checked 2026-11-25) | Apache-2.0 |
| Maturity and reach | New, 1 star | Far larger, battle-tested | Far larger |

TZ is not a replacement for them: use an output compressor beside it if you want deeper raw reduction. TZ's angle is waste detection, safe handoffs and numbers you can trust. Details: [competitor learnings](docs/COMPETITOR-LEARNINGS.md).

## You do not type these

Once the hooks are registered (plugin install, or `./install.sh` for the CLI), these run by themselves. `tz hooks live` shows whether they fire. Each can be switched with `TZ_FEAT_<NAME>=0/1` or `features` in config.json; `mode off` turns all of them off.

**On by default (advice and recording, no blocking):** 1 h vs 5 min cache-life detection (`cache_ttl_auto`), idle-past-cache cost (`idle_cost`), unrelated task, big paste, home-folder start and many short prompts (`task_switch`, `paste_warn`, `home_cwd`, `small_msgs`), model and plan advice (`model_advice`, `plan_advice`), oversized instruction files (`instr_advice`), repeat reads with a file skeleton (`dup_skeleton`), repeat read-only MCP calls (`mcp_dedup`), stuck patterns (`stuck_detect`), destructive-command and secret-path checks (`safety_net`), build/test log trimming that keeps every failure line (`log_compress`), SKILL.md spec lint (`skill_lint`), test output piped through head/tail (`check_pipe`), curl/wget to a host outside `.tz/scope.json` (`scope_check`), budget level warnings once a budget is set (`budget_warn`), stale-branch warning before a broad test run (`stale_warn`), parallel sessions for independent tasks (`auto_split`, `ship_fast`).

**Opt-in (default off, they block, add context or record):** `size_gate`, `size_cap`, `paste_block`, `bulk_read_block`, `read_delta`, `git_guard`, `safety_extra`, `safety_strict`, `custom_rules`, `budget_block`, `stale_block`, `plan_reinject`, `beads_prime`, `micro_skills`, `unverified_claim`, `rtk_filters`, `learn_loop`, `crash_restart`, `defaults_advice`, `obs_record`, `obs_file_context`, `obs_inject`, `line_custom_command`.

## Commands

Everything below also works on demand. You only need these when you want the detail.

| Group | Commands | Use |
|---|---|---|
| Status | `tz status` `forecast` `stats` | Context, burn, savings (MEASURED / EST / UNKNOWN) |
| Handoff | `tz handoff` `resume` `recall` | Save, continue, restore trimmed output |
| Budget | `tz budget` `ccusage` `stale` `claim` | Budgets, usage cross-check, stale branches, session notes |
| Safety | `tz gitguard` `rules` `scope` `sandbox` `scrub` | Git safety, rulebooks, allowed hosts, bounded run, secret scrub |
| Output | `tz logc` `delta` `skill-lint` `planphase` | Log trimming, re-read diff, SKILL.md lint, plan-first check |
| Search | `tz sg` `memsearch` `sym` `impact` `replayrank` | Structural search, note search, symbols, callers, replay ranking |
| Record | `tz obs` `trace` `ts` `facts` `debt` | Observations, token trace, tags, project facts, shortcut ledger |
| Parallel | `tz squad` `team` `tbench` `spec` | Parallel tasks, multi-worker run, benchmarks, specs |
| Other | `tz clihelp` `depth` `condense` `diag` `fast` `line` | CLI listing, depth advice, history condense, post-edit check, profiling, status line |

One line per command: [docs/COMMANDS.md](docs/COMMANDS.md). Every `tz` subcommand: `tz help`.

CI: the badge above is live. The Windows CI job is known to fail and is deferred; macOS and Linux are the supported platforms.

## Safety

Local only, no telemetry. Destructive commands are caught and checkpoints allow rollback. Details: [SECURITY.md](../.github/SECURITY.md).

## More

[Overview](docs/OVERVIEW.md) · [Install](docs/INSTALL.md) · [CLI](docs/CLI.md) · [Modes](docs/MODES.md) · [Metrics](docs/METRICS.md) · [Benchmark method](docs/BENCHMARK-METHOD.md) · [Limitations](docs/LIMITATIONS.md) · [Contributing](../.github/CONTRIBUTING.md) · [Brand policy](BRANDING.md) · [Website](https://rishavm713-create.github.io/token-zombie/) · [Discussions](https://github.com/rishavm713-create/token-zombie/discussions)

Created by [Rishav Mishra](https://rishavm713-create.github.io/). Copyright © 2026 Rishav Mishra. [MIT licence](LICENSE); credits: [NOTICE](NOTICE).
