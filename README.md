<p align="center"><picture><source media="(prefers-color-scheme: light)" srcset="docs/img/logo-light.svg"><img src="docs/img/logo.svg" width="560" alt="TOKEN ZOMBIE. Make every single token count."></picture></p>

<h1 align="center">TOKEN ZOMBIE</h1>

<p align="center"><b>Stop paying for tokens Claude Code wastes.</b><br>Free · Runs on your computer · Nothing is sent anywhere</p>

[![CI](https://github.com/rishavm713-create/token-zombie/actions/workflows/ci.yml/badge.svg)](https://github.com/rishavm713-create/token-zombie/actions/workflows/ci.yml) [![License](https://img.shields.io/badge/License-MIT-4c9a1a)](LICENSE) [![macOS](https://img.shields.io/badge/macOS-supported-000000?logo=apple&logoColor=white)](COMPAT.md) [![Linux](https://img.shields.io/badge/Linux-CI-1f6feb?logo=linux&logoColor=white)](COMPAT.md) [![Built on](https://img.shields.io/badge/Built%20on-Claude%20Code-d97757)](docs/INSTALL.md) [![Local first](https://img.shields.io/badge/Local--first-no%20telemetry-83ffa0)](SECURITY.md) [![GitHub Stars](https://img.shields.io/github/stars/rishavm713-create/token-zombie?style=social)](https://github.com/rishavm713-create/token-zombie)

![TOKEN ZOMBIE demo: status, lossless trim, free replay benchmark](docs/img/demo.gif)

[Website](https://rishavm713-create.github.io/token-zombie/) · [Install guide](docs/INSTALL.md) · [Docs](#docs) · [Discussions](https://github.com/rishavm713-create/token-zombie/discussions)

![TOKEN ZOMBIE toolbar inside Claude Code](docs/img/toolbar-live.svg)

## Why

Long Claude Code chats burn your usage limit on repeated file reads, noisy tool output, duplicated sub-agent work and context that fills up and is lost. TOKEN ZOMBIE fixes that inside Claude Code, with no AI calls of its own.

## Features

| | Feature | What you get |
|---|---|---|
| 📊 | **Token tracking** | See where every token goes. Each number is labelled *measured* or *estimate*. |
| ✂️ | **Output trimming** | Big tool output is cut before Claude reads it. The full text is kept and `tz recall` brings it back. |
| ⏱️ | **Early warning** | Tells you before a chat runs out of room, while there is time to save the work. |
| 🧠 | **Handoff & resume** | A short note lets a fresh chat continue where you stopped, without re-explaining. |
| 🗺️ | **Repo map** | One compact page of files and definitions, so Claude reads less to find code. |
| 🛡️ | **Safety guard** | Destructive commands are caught; checkpoints let you roll back a failed change. |
| 💰 | **Free savings report** | `tz stats` reads your own Claude Code logs. No paid test runs needed. |

## Install

```bash
claude plugin marketplace add rishavm713-create/token-zombie
claude plugin install token-zombie@token-zombie
```

Restart Claude Code, then run `/token-zombie:tz`. Verify and roll back: [install guide](docs/INSTALL.md).

## How it works

| Step | What happens |
|---|---|
| **Detect** | Flags repeated reads and sub-agents that duplicate or stall. |
| **Contain** | Trims noisy output; the original stays recallable. |
| **Warn** | Signals early in a small bar inside Claude Code. |
| **Revive** | Saves a handoff so the next chat picks up instantly. |

![Dashboard](docs/img/dashboard.png)

## Docs

| Guide | Purpose |
|---|---|
| [Install](docs/INSTALL.md) | Install, verify, roll back |
| [CLI](docs/CLI.md) | Every command |
| [Modes](docs/MODES.md) | OFF / LITE / FULL / ULTRA |
| [Metrics](docs/METRICS.md) | What each number means |
| [Benchmark method](docs/BENCHMARK-METHOD.md) | How savings are measured |
| [Limitations](docs/LIMITATIONS.md) | Known constraints |
| [Security](SECURITY.md) | Privacy and safety |
| [Contributing](CONTRIBUTING.md) | First contributions |

## Creator

Built by [Rishav Mishra](https://rishavm713-create.github.io/), because the problem was real. Open source so the fix is not another limitation for someone else. Also see [EditSutra](https://editsutra.github.io/).

MIT licence · © 2026 Rishav Mishra
