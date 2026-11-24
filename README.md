<p align="center"><picture><source media="(prefers-color-scheme: light)" srcset="docs/img/logo-light.svg"><img src="docs/img/logo.svg" width="560" alt="TOKEN ZOMBIE. Make every single token count."></picture></p>

# TOKEN ZOMBIE

**Stop paying for tokens Claude Code wastes.**
Free. Runs on your computer. Nothing is sent anywhere.

[![License](https://img.shields.io/badge/License-MIT-4c9a1a)](LICENSE) [![macOS](https://img.shields.io/badge/macOS-supported-000000?logo=apple&logoColor=white)](COMPAT.md) [![Linux](https://img.shields.io/badge/Linux-CI-1f6feb?logo=linux&logoColor=white)](COMPAT.md) [![Built on](https://img.shields.io/badge/Built%20on-Claude%20Code-d97757)](docs/INSTALL.md) [![Local first](https://img.shields.io/badge/Local--first-no%20telemetry-83ffa0)](SECURITY.md) [![GitHub Stars](https://img.shields.io/github/stars/rishavm713-create/token-zombie?style=social)](https://github.com/rishavm713-create/token-zombie)

![TOKEN ZOMBIE demo: status, lossless trim, free replay benchmark](docs/img/demo.gif)

[Website](https://rishavm713-create.github.io/token-zombie/) · [Install guide](docs/INSTALL.md) · [Docs](#docs) · [Discussions](https://github.com/rishavm713-create/token-zombie/discussions)

![TOKEN ZOMBIE toolbar inside Claude Code](docs/img/toolbar-live.svg)

## What it does

Long Claude Code chats quietly burn your usage limit on repeated file reads, duplicated sub-agent work and context that fills up and is lost. TOKEN ZOMBIE:

- **Shows** where your tokens go, with every number labelled *measured* or *estimate*.
- **Warns** you before a long chat runs out of room.
- **Saves your place** with a short note, so a fresh chat picks up where you stopped.

It advises and never blocks. Everything stays on your computer. No telemetry, no AI calls in the core.

## Install (one minute)

In Claude Code:

```
/plugin install token-zombie --marketplace rishavm713-create/token-zombie
```

Restart Claude Code, then run:

```
/token-zombie:tz
```

Shell form: `claude plugin install token-zombie --marketplace rishavm713-create/token-zombie`

Verification and a clean rollback are in the [install guide](docs/INSTALL.md).

## How it works

| Step | What happens |
|---|---|
| **Detect** | Flags repeated reads and sub-agents that duplicate or stall. |
| **Contain** | Trims noisy tool output. The original is kept and can be recalled. |
| **Warn** | Tells you early, while there is still time to save the work. |
| **Revive** | A handoff note lets a fresh chat continue without re-explaining. |

A small bar inside Claude Code shows quick signals, and a local dashboard shows the details.

![Dashboard](docs/img/dashboard.png)

**Workflow defaults:** `tz code [task]` (coding pipeline: plan, build all first, debug, test once, review, simplify, ship, each with a model and the best installed coding skill; the prompt hook points engineering prompts at it), `tz split "task A" "task B"` (one session per task, model pick, worktree, build-first-then-one-live-test), `tz lock acquire|release NAME` (serialise shared live tests), `tz hsize` (handoff size check), `tz similar QUERY` (read-only GitHub search for similar tools). Policy advice also flags test-skipping edits (fake green) and more than 6 subagents per session (ideas from karanb192/claude-code-hooks). The prompt hook now suggests `tz split` when one prompt holds 2+ independent tasks. Advice and local lock files only; tz starts nothing.

## Honest status

- Claude Code is the supported host. Other tools get experimental rules files only.
- **Measured, for free:** `tz bench replay` replays your own chat logs offline (no model call, no cost). On 1,025 real chats (48,338 replies) TZ's automatic output trims saved **0.58% of input tokens net**, after subtracting the text TZ itself adds. Repeat-search advice adds at most 0.02% more. Answer quality is not measured offline. Run it on your own logs; your number will differ. See [limitations](docs/LIMITATIONS.md) and the [benchmark method](docs/BENCHMARK-METHOD.md).
- Some hook payloads and UI behaviour still need checks on a live host: [implementation matrix](docs/IMPLEMENTATION-MATRIX.md).

## Docs

| Guide | Purpose |
|---|---|
| [Install](docs/INSTALL.md) | Install, verify, roll back |
| [CLI](docs/CLI.md) | Command reference |
| [Modes](docs/MODES.md) | OFF / LITE / FULL / ULTRA |
| [Metrics](docs/METRICS.md) | What each number means and its source |
| [Limitations](docs/LIMITATIONS.md) | Known constraints |
| [Security](SECURITY.md) | Privacy and safety boundaries |
| [Contributing](CONTRIBUTING.md) | First contributions and checks |

## Creator

Built by [Rishav Mishra](https://rishavm713-create.github.io/). Built because the problem was real, and open source so the fix is not another limitation for someone else. Also see [EditSutra](https://editsutra.github.io/).

MIT licence. © 2026 Rishav Mishra.
