<p align="center"><picture><source media="(prefers-color-scheme: light)" srcset="docs/img/logo-light.svg"><img src="docs/img/logo.svg" width="480" alt="TOKEN ZOMBIE"></picture></p>

<h1 align="center">Stop paying for tokens Claude Code wastes.</h1>

<p align="center">Trims noisy tool output · warns before a chat overflows · saves your place<br><b>Free · Local · No telemetry · MIT</b></p>

<p align="center"><a href="https://github.com/rishavm713-create/token-zombie/actions/workflows/ci.yml"><img src="https://github.com/rishavm713-create/token-zombie/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-4c9a1a" alt="MIT"></a> <img src="https://img.shields.io/badge/tests-3624%20pass-83ffa0" alt="3624 tests pass"></p>

## Install (30 seconds)

```bash
claude plugin marketplace add rishavm713-create/token-zombie && claude plugin install token-zombie@token-zombie
```

Restart Claude Code. Done. Remove any time: `/plugin uninstall token-zombie`.

![TOKEN ZOMBIE demo](docs/img/demo-bench.svg)

## Before / after

| One test session | Without TZ | With TZ |
|---|---:|---:|
| Noise kept out of context | 0 | **54,852 chars** |
| TZ's own cost | 0 | 1,880 chars |
| False alarms / misses | n/a | **0 / 0** |

Every failure line is kept and the original is one command away (`tz recall`). See your own number: `tz gain`.

## What it does

- **Trims** long build, test and tool output. Nothing is lost.
- **Warns** before a chat gets too big or loops on the same read.
- **Saves your place** so a fresh chat continues (`tz handoff`, `tz resume`).
- **Labels every number** MEASURED, EST or UNKNOWN.

## Learn more

[Website](https://rishavm713-create.github.io/token-zombie/) · [Full reference](docs/REFERENCE.md) · [Test evidence](docs/TEST_EVIDENCE.md) · [Limits](docs/REFERENCE.md#why-tz) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

Created by Rishav Mishra · MIT · macOS and Linux
