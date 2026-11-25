# TZ v2.1 usage

## Install
Plugin:
```bash
claude plugin marketplace add rishavm713-create/token-zombie
claude plugin install token-zombie@token-zombie
```
That installs what is published on GitHub. v2.1 is not pushed or released as of 2026-11-25.

From a local checkout: `./install.sh --dry-run` shows the changes; `./install.sh` applies them. Other flags: `--check`, `--uninstall`, `--restore`, `--statusline-only`. Keep the checkout directory named `token-zombie` (the installer matches `token-zombie/bin/`).

## Commands new or extended in v2.1
Run as `tz …` (or `python3 bin/tz …`). `tz help` does not list `toolprune`, `mem`, `find-code` or `bench matrix` yet.

| Command | What it does |
|---|---|
| `tz toolprune [--json]` | Report tools that were listed but never called. |
| `tz toolprune --apply` / `--restore` | Add / remove deny rules in `<project>/.claude/settings.local.json`. Read the report first. |
| `tz mem index [DIR]`, `tz mem search "query" [-k N]` | Local keyword memory search. |
| `tz next dep TASK --dep OTHER` | Add a task dependency; cycles are refused. |
| `tz rank --tokens N`, `tz rank --mention "text"` | Ranked repo map within a token budget (EST), biased to names in the text. |
| `tz find-code "task text" [--n N] [DIR]` | Likely files for a task. |
| `tz impact --diff` | What the current diff may affect (text-based). |
| `tz agent TASK … --wall SECONDS --max-errors N` | Stop an agent run on wall time or repeated errors. |
| `tz bench matrix [--trials N] [--json] [--out FILE] [--read-guard deny|advice|off]` | Offline per-feature comparison. Characters only; no model calls. |
| `tz bench harbor` | Print Harbor commands. Runs only with `--run` (spends your usage). |

`skills/tz-craft` holds debug, test, refactor, review, plan, perf, React, git-safety, learn and verify notes, loaded on demand.

`bin/tztips.py` (`instr`, `defaults`, `breakdown`, `mcp-unused`) can be run with `python3 bin/tztips.py …`. It is not wired into hooks or `tz` yet (in progress, other session). `defaults --apply --yes` and `instr --fix --apply` change your files; `--restore` undoes them.

## Feature switches
Order: mode `off` turns every feature off; else env `TZ_FEAT_<NAME>` (`0`, `off`, `false` or empty = off); else `"features"` in `~/.claude/token-zombie/config.json`; else the default.

| Name | Default | Controls |
|---|---|---|
| `cache_ttl_auto` | on | Measure prompt-cache life from the chat log. |
| `dup_skeleton` | on | Put a file outline in a duplicate-read denial (needs `read_guard: "deny"`). |
| `stuck_detect` | on | Repeated-failure / loop advice. |
| `mcp_dedup` | on | Advice on a repeated identical read-only MCP call. |
| `plan_reinject` | off | Re-insert the plan head after compaction (adds context). |
| `safety_net` | on | Listed, but **no code reads it** at 8c703c3: setting it to 0 does not turn the safety check off. Use `TZ_SAFE=0`. |

Config example:
```json
{"features": {"stuck_detect": false}, "read_guard": "deny"}
```
Ship fast (on by default): for a prompt with several independent tasks, or one large build task (keyword heuristic), TZ tells Claude to start one session per independent piece (max 5, own worktree), use parallel Sonnet/Haiku subagents inside each, build first and test once, merge and run the full suite once, estimate the time in hours and keep pieces to 30 minutes or less. It is advice to Claude (a hook cannot start sessions), it never allows a push, tag or publish without your OK, its effect on speed and token use is not measured, and parallel sessions can use more tokens. The same orders carry the ship flow: merge, run the full suite once, push, watch CI on all OSes, fix without weakening tests, report each session's link and status. When your own short prompt is a go-ahead such as "yes push", TZ quotes it back and tells Claude to forward it to the session that holds the work; a push approval never covers a tag, and a tag or release needs green CI. Detection is a narrow keyword match that ignores questions, negations, pasted text, and messages tagged as coming from another session or an event; an untagged first message written by another session cannot be told apart from yours. Switch: `tz speed on|off|status` (`features.ship_fast` in config.json, env `TZ_FEAT_SHIP_FAST=0`); with `TZ_FEAT_AUTO_SPLIT=0` it proposes session cards instead of starting them.

Other switches: `TZ_SAFE=0` (Bash safety check), `TZ_OUT=0` or `"out_trim": false` (output trim), `read_guard` = `advice` (default) / `deny` / `off`, `tz mode off|lite|full|ultra`.

## Usage and stats
- `tz stats`: savings labelled measured or estimated, minus TZ's own overhead.
- `tz status`, `tz forecast`: context %, tokens, burn rate; 5 h / 7 d limits only if the host provides them.
- There is **no `tz usage` command**. The v2.1 usage additions in `bin/tzusage.py` show in `tz status`: usable context % [est], cache hit rate (when the log has cache counts), and a 5 h block estimate (only when the host gives no limits).
- `tz config`: effective settings and their source. It shows settings; it does not set them.
- `python3 bin/tztips.py breakdown [transcript]`: context breakdown (not wired).

## Troubleshooting
| Symptom | Do this |
|---|---|
| A safe command is blocked | Read the reason. Ask the owner, or run it with `TZ_SAFE=0`. |
| "safety check crashed (fail closed)" | Retry; if it repeats, use `TZ_SAFE=0` and report the command. |
| A big Read is denied once | Read with offset/limit, or repeat the same Read: it is then allowed. |
| Trimmed output hides what you need | `tz recall ID --grep PATTERN` or `--lines A-B`. |
| Loop or duplicate advice is noise | `TZ_FEAT_STUCK_DETECT=0` or `TZ_FEAT_MCP_DEDUP=0`. |
| A needed tool vanished after toolprune | `tz toolprune --restore`. Nothing restores it automatically. |
| Hooks seem silent | `tz doctor`, `./install.sh --check`; check `tz mode` is not `off`. |
| Turn TZ down or off | `tz mode off` turns the v2.1 feature switches off, but output trim stays on (set `TZ_OUT=0`, or `"out_trim": false` in config.json). The destructive-command guard has its own switch, `TZ_SAFE=0`. `./install.sh --uninstall` removes the install. |

Env variables must be set where the hooks run (Claude Code's environment), not only in one tool command.
