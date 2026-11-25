<p align="center"><picture><source media="(prefers-color-scheme: light)" srcset="docs/img/logo-light.svg"><img src="docs/img/logo.svg" width="560" alt="TOKEN ZOMBIE. Make every single token count."></picture></p>

<h1 align="center">TOKEN ZOMBIE</h1>

<p align="center"><b>Stop paying for tokens Claude Code wastes.</b><br>Free · Runs on your computer · Nothing is sent anywhere</p>

[![CI](https://github.com/rishavm713-create/token-zombie/actions/workflows/ci.yml/badge.svg)](https://github.com/rishavm713-create/token-zombie/actions/workflows/ci.yml) [![License](https://img.shields.io/badge/License-MIT-4c9a1a)](LICENSE) [![Local first](https://img.shields.io/badge/Local--first-no%20telemetry-83ffa0)](SECURITY.md)

![TOKEN ZOMBIE demo](docs/img/demo.gif)

TOKEN ZOMBIE (TZ) trims noisy tool output, warns before a chat runs out of room, and saves handoffs so a fresh chat continues where you stopped. It adds no AI calls of its own.

## Install

```bash
claude plugin marketplace add rishavm713-create/token-zombie
claude plugin install token-zombie@token-zombie
```

Restart Claude Code, then run `/token-zombie:tz`. Or `npm i -g token-zombie` for the `tz` CLI alone (needs python3). Verify and roll back: [install guide](docs/INSTALL.md).

## Commands

| Command | Use |
|---|---|
| `tz status` `forecast` `stats` | Context, burn, savings (MEASURED / EST / UNKNOWN) |
| `tz handoff` `resume` `recall` | Save, continue, restore trimmed output |
| `tz budget` `ccusage` `claim` `stale` | Budgets, usage cross-check, session notes, stale branches |
| `tz clihelp` `debt` `diag` `facts` `fast` | CLI listing, shortcut ledger, post-edit check, project facts, profiling |
| `tz gitguard` `line` `memsearch` `obs` | Git safety, status line, note search, observations |
| `tz sandbox` `scrub` `sg` `spec` | Bounded run, secret scrub, structural search, specs |
| `tz squad` `tbench` `team` `trace` `ts` | Parallel tasks, benchmarks, multi-worker run, token trace, tags |
| `tz depth` `impact` `condense` `sym` | Depth advice, callers, history condense, symbol lookup |

One line per command: [docs/COMMANDS.md](docs/COMMANDS.md). Every `tz` subcommand: `tz help`.

## Safety

Local only, no telemetry. Destructive commands are caught and checkpoints allow rollback. Details: [SECURITY.md](SECURITY.md).

## More

[Overview](docs/OVERVIEW.md) · [Install](docs/INSTALL.md) · [CLI](docs/CLI.md) · [Modes](docs/MODES.md) · [Metrics](docs/METRICS.md) · [Benchmark method](docs/BENCHMARK-METHOD.md) · [Limitations](docs/LIMITATIONS.md) · [Contributing](CONTRIBUTING.md) · [Brand policy](BRANDING.md) · [Website](https://rishavm713-create.github.io/token-zombie/) · [Discussions](https://github.com/rishavm713-create/token-zombie/discussions)

Created by [Rishav Mishra](https://rishavm713-create.github.io/). Copyright © 2026 Rishav Mishra. [MIT licence](LICENSE); credits: [NOTICE](NOTICE).
