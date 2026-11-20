# Modes

Set with `tz mode <off|lite|full|ultra>`; `tz mode` shows the mode, effective values and which advice is on.
Stored as `mode` in `~/.claude/token-zombie/config.json`. Missing or unknown value = `full`.

| | off | lite | full (default) | ultra |
|---|---|---|---|---|
| `limit` (next-task suggestion, tokens) | 100000 | 150000 | 100000 | 60000 |
| `hard` (safe-point handoff, tokens) | 175000 | 175000 | 175000 | 120000 |
| `read_warn` (big-Read nudge, bytes) | 40000 | 100000 | 40000 | 20000 |
| `plan_warn` / `plan_stop` (% of plan) | 90 / 97 | 90 / 97 | 90 / 97 | 80 / 95 |
| pack hints | off | off | on | on |
| big-Read nudge | off | on | on | on |
| duplicate-read advice | off | off | on | on |
| next-task suggestion at `limit` | off | on | on | on |

`off` keeps full's thresholds but silences all advice. Advice never blocks; the big-Read nudge allows a repeated Read.

## Kept in every mode (off included)
Hard-limit safe-point handoff warning (`hard`), `plan_stop`, corrupt-state quarantine, redacted `errors.log`,
installer backups/rollback, `tz-vet` HIGH findings, the task-continuity rule.

## Precedence (per threshold)
env `TZ_<KEY>` > explicit key in `config.json` > mode profile > built-in default.
`tz mode <m>` keeps explicit keys and prints a note when one overrides the profile.

## Safe writes
`tz mode <m>` refuses (exit 1, nothing changed) if `config.json` is not a JSON object, backs it up to
`config.json.bak-mode-<timestamp>`, then writes atomically (tmp + rename). Invalid mode name: exit 2, nothing changed.
