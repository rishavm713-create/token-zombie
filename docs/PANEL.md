# TOKEN ZOMBIE panel (Claude Code Mod)

In-chat pane built only on the supported Mods API (function hooks). No DOM, no scraping,
no model calls, no network, no telemetry. Open it with `/tz` (bare command, registered by the mod).
Source: `hooks/panel.tsx`; tests: `hooks/panel.test.tsx`; state contract: `types/index.d.ts`.

## What it shows and where each number comes from
| Row | Source | Label |
|---|---|---|
| tokens in / out / cache | sum of `turn.complete` `usage` on the main loop, since the panel loaded | MEASURED (host event) |
| model | last `usage.model` seen | MEASURED |
| agent time, turns | sum of `turn.complete` `durationMs` | MEASURED |
| subagents | count of `agent.spawn` events | MEASURED |
| cost | `~/.claude/token-zombie/host.json`, written by `bin/tz-status.py` from the statusline JSON `cost.total_cost_usd`. Shown only if the file is under 10 min old. Otherwise `n/a (statusline not wired)`. Never computed from prices. | MEASURED by host |
| context % + level, supervisor state/risk/activity, open tasks, action count | `~/.claude/token-zombie/status.json` (tzsup). Older than 10 min: `(stale)` and supervisor rows read `no data`. Missing or corrupt: `no data`. | as labelled in that file |
| mode | `mode` in `~/.claude/token-zombie/config.json` (default `full`) | config |
| recent | last 5 `tool.call` / `agent.spawn` events (`runs` / `done`) | MEASURED |

Mods get no session id in events, so host.json is trusted by freshness (10 min), not by session match.
Files are polled every 5 s with `$.clock.every`; the pane redraws only when file content (or staleness) changed.
Token totals reset when the mod reloads; they are not a whole-chat total.

## Buttons (every run: no shell, `timeoutMs` 30000)
- OFF / LITE / FULL / ULTRA: `python3 <plugin root>/bin/tz mode <m>`, then re-read config.
- Copy: plain-text summary of the shown metrics via `$.ui.copy`.
- Review: `tz optimize`, first 12 lines shown.
- Audit: `tz audit`, first 12 lines shown.
- Board: `tz dash --out ~/.claude/token-zombie/board.html` (one-shot static HTML, no server); the path is shown. Open it in a browser.
- Compact: `tz checkpoint` (refresh the handoff note), then `$.command.run({command:'compact', args})`. If the host refuses, the pane shows `type: /compact ...`; on success it still shows that line as a hint, because the call result cannot confirm the compaction ran.
- Errors show as one dim line.

## Placement per surface and limits
The pane docks where the surface places panes (terminal fullscreen layout, desktop; vscode and mobile per the host). On a narrow
terminal or a surface that does not place panes, `ui.open` answers `isPlaced: false`; the mod then sets a one-line
`$.ui.status` (`TZ <mode> ctx <pct> in <k> out <k>`) updated on each file change. Buttons need a surface that takes presses.

## Fallbacks
- Statusline: `bin/tz-status.py` (also feeds host.json for the cost row).
- Dashboard: `tz dash --out FILE` / `tz dash --serve` (127.0.0.1, run by you, never by the mod).
- Companion: `tz companion` (local status server) and `tz mascot` for a one-line state.

## Manifest
`.claude-plugin/plugin.json` needs `"types": "./types/index.d.ts"`; `hooks/hooks.json` lists `"modules": ["./panel.tsx"]`.
