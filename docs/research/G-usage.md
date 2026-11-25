# G: usage and observability (ccusage, ccstatusline, langfuse)

Read as source via `gh api` (raw). REA not used: no compiled targets.

| repo | licence | decision | what TZ takes |
|---|---|---|---|
| ryoppippi/ccusage | MIT | C (rebuilt, no code copied) | 5-hour billing blocks: start floored to the hour, new block when a reply is >5h after block start or after the previous reply, gap blocks, active flag, burn rate (tokens/min) and projection to block end. Dedup by message.id already in tzusage. |
| sirmalloc/ccstatusline | MIT | C | "usable context" = context / (window x auto-compact fraction 0.8); `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` may only lower it. |
| langfuse/langfuse | MIT core, EE dirs commercial | D (reference) | Trace/observation model only. No SDK, no network, no telemetry: TZ stays local. |

## Built (bin/tzusage.py, tests/v21/test_usage.py 10/0)
- `usable(ctx, win)` -> (usable tokens, % used) [est]
- `hit_rate(cr, cw)` = cache_read / (cache_read + cache_write) [actual from the log]
- `blocks(ents, now)` -> 5h blocks with burn and projection [est from this log only; provider rate_limits win when present]

## Already in TZ before v2.1
- 1h vs 5m cache-write split (tzusage), message.id dedup within one transcript.

## Not done (limitation)
- Cross-transcript dedup by (message.id, requestId) across sidechain/subagent files: TZ reads one transcript per report, so double counting does not arise there; a multi-file total would need it.
- Cost in money: TZ reports tokens only (plan users pay a flat fee; price tables go stale).
