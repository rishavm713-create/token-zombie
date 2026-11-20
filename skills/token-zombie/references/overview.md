# Overview
TOKEN ZOMBIE is a local-first token saver for Claude Code. One CLI (`python3 "${CLAUDE_PLUGIN_ROOT}/bin/tz"`), hooks, a supervisor and a statusline. No network, no telemetry; state lives in `~/.claude/token-zombie/`, project handoffs in `<project>/handoffs/`.

## Optimization engine (`tz optimize`, `tz filter`, `tz classify`, `tz stats`)
- Duplicate-read advice: path + mtime + hash; the cache invalidates when the file changes. Full reads are never blocked (the guard nudges once on big files; repeating the Read proceeds).
- Log analysis finds repeated reads, repeated commands, repeated research/exploration and oversized outputs in the chat transcript.
- `tz filter` shrinks noisy command output; `tz classify` gives task mode + cheapest capable model advice.
- `tz stats` is the savings ledger: MEASURED vs EST, with tz's own overhead subtracted.
- Advisory features (pack hints, big-Read nudge, dup-read advice, `limit` next-task suggestion) are gated by `mode`; safety controls are not.
