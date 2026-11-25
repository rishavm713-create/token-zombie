# TOKEN ZOMBIE overview

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
| 💰 | **Free savings report** | `tz stats` and `tz bench replay` read your own Claude Code logs. Free, no account. Savings are labelled MEASURED / EST / UNKNOWN. |

## How it works

| Step | What happens |
|---|---|
| **Detect** | Flags repeated reads and sub-agents that duplicate or stall. |
| **Contain** | Trims noisy output; the original stays recallable. |
| **Warn** | Signals early in a small bar inside Claude Code. |
| **Revive** | Saves a handoff so the next chat picks up instantly. |


## Creator

**Created by [Rishav Mishra](https://rishavm713-create.github.io/).** Built by Rishav Mishra. TOKEN ZOMBIE started with a simple idea: make AI coding agents more efficient, reduce wasted context and help developers build better software. The project is developed as a local-first engineering efficiency layer for Claude Code.

Also see [EditSutra](https://editsutra.github.io/).

Copyright © 2026 Rishav Mishra. Code: [MIT licence](LICENSE); third-party credits: [NOTICE](NOTICE). Name, logo and forks: [BRANDING.md](BRANDING.md).
