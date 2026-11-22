# Startup context audit (2026-11-22)

Source: `tz startup` (reads the chat logs; no AI calls). Tags: MEASURED = from logs or `wc -c`; EST = chars/4.
Sample: 12 newest chats, one machine, desktop app, Opus 5.5. Not a benchmark.

## First reply size (MEASURED, input + cache before any work)
| | chats | median | note |
|---|---|---|---|
| Before (caveman + ponytail on) | 11 | 80k (77k–81k) | token-zombie project 80k (n=5) |
| After (both off, TZ lean rules on) | 1 | 75.9k | this chat, e3e74ebd; -5k vs median. n=1: confirm over the next chats |

## Items
Load = every session unless noted. Tok = EST (chars/4) unless MEASURED.

| Item | Load | Tok | Essential? | TZ replaces? | Verdict |
|---|---|---|---|---|---|
| Built-in tools (platform) | always | 18.8k | yes | no | keep (not changeable) |
| System prompt (platform) | always | 9.3k | yes | no | keep (not changeable) |
| Unitemised (not in logs) | always | 23.8k | unknown | no | unknown |
| MCP: Claude_Browser | always | 5.6k | optional | no | keep in app (app-managed) |
| MCP: iOS Simulator | always | 2.5k | optional (no iOS work here) | no | on-demand: app setting, owner decides |
| ccd_turn / ccd_session / terminal / visualize | always | 2.0k / 0.9k / 0.3k / 1.0k | app | no | keep (app-managed) |
| MCP instructions (chrome, computer-use, easel) | always | 1.9k | optional | no | on-demand per project |
| Deferred tool names (computer-use, chrome, premiere-pro, scheduled-tasks, mcp-registry...) | names only | 1.5k total, ~88 per server | optional | no | premiere-pro, chrome, mcp-registry, scheduled-tasks unused in 12 chats: disable at user level, enable per project (gated) |
| Skill list: anthropic-skills (16) | always | 2.5k | partly | no | keep (platform) |
| Skill list: user/built-in (19) | always | 2.1k | partly | no | keep; editsutra desc 968 chars, unused in 12 chats: shorten (~179) or park (~242) |
| Skill list: token-zombie (9) | always | 0.2k | yes (TZ) | — | keep |
| Agent list | always | 1.4k | yes | no | keep |
| `~/.claude/CLAUDE.md` | always | 3994 chars MEASURED, ~1.0k | yes | partly (core block repeats ~6 lines of it) | keep; optional trim, gated |
| `~/.claude/RTK.md` | always | 453 chars MEASURED, ~0.1k | yes | no | keep |
| Project CLAUDE.md (token-zombie) | — | 0 (none) | — | — | — |
| MEMORY.md (this project) | — | 0 (none) | — | — | — |
| caveman SessionStart + UserPromptSubmit | was always | ~1.85k (with ponytail) MEASURED from log, ~7.7k chars | style only | yes: TZ core block | DISABLED (owner yes 2026-11-22) |
| ponytail SessionStart | was always | (in the 1.85k above) | style only | yes: TZ core block | DISABLED (owner yes 2026-11-22) |
| TZ SessionStart (core block + handoff head + task pack) | always | 3091 chars MEASURED here, ~0.8k; core block 922 chars ~0.23k | yes | — | keep; capped 2500 chars for handoff part |
| TZ UserPromptSubmit hints | when matched | ~50 each | yes | — | keep (counted as overhead in ledger) |
| GSD SessionStart (check-update, path-export, session-state) | always | 0 chars output MEASURED (session-state) | optional | no | keep (no text injected) |
| Other plugins (superpowers, claude-mem, hyperframes, humanizer, ui-ux-pro-max, token-optimizer, social, last30days, example-skills) | off | 0 | — | — | already disabled |

## What TZ can still change (owner-controlled, ~4.3k EST of 76k)
- Done: caveman + ponytail off, TZ core block on: ~1.85k MEASURED -> ~0.23k EST per chat; ~2k per subagent [measured earlier].
- Gated, not done (needs owner yes, edits user settings): disable unused MCPs at user level (~88 EST each, ~350 for 4); park or shorten editsutra (~179–242 EST); drop CLAUDE.md lines the core block repeats (~150 EST).
- Not changeable by TZ: platform ~35k, app/MCP schemas ~12k, unitemised ~24k (~94% of startup).

## Rollback
- Core block: `cp` the pre-change copy, or config `{"lean_rules": false}` in `~/.claude/token-zombie/config.json`.
- Plugins: `cp ~/.claude/settings.json.bak-20261122-lean ~/.claude/settings.json` re-enables caveman + ponytail.
