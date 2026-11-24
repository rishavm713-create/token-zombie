# Limitations (honest list)
- Savings are NOT yet measured end-to-end. `tz stats` counts only events tz recorded (filter runs, flagged duplicate reads); flagged reads are [est]. No with/without benchmark exists. All TZ advice text (every hook line) is counted as overhead [measured chars/4].
- 5h/7d and resets: shown only when Claude Code passes rate_limits to the statusline; otherwise "not provided". $ figures (`tz stats` 24h, Session Economics, `tz live agents`) are EST: tokens x list price per model (tzcont.PRICE, edit as prices change), API-equivalent, not your plan quota.
- ctx_window (default 200k) is a setting, not read from the provider: context % is [est].
- MCP/plugin tool-schema cost is UNKNOWN (not in config).
- tz cannot switch the main model, start sessions or enable/disable skills by itself; it advises. Parked-skill activation is `skillpack on`, with your approval.
- Duplicate-read detection by hook is advice; a local cache does not reduce provider tokens already spent.
- Classification and overlap detection are keyword/word-overlap heuristics.
- Benchmark (`tz bench`): synthetic project; filter bytes and resume size are MEASURED, duplicate-read saving and the replaced-chat size are assumptions (EST), startup context and provider cache are UNKNOWN. No real with/without session A/B yet.
- `tz profile --yes` runs your own `skillpack`; a running chat does not reload skills (host limit), effect starts in a new chat. MCP/plugin enable/disable is not automated.
- `tz handoff/task-wrap --test CMD` runs the command you type.
- Hooks run live in the owner's Claude Code sessions (2026-11-22: start context, prompt advice, ledger entries seen in real chats). Tests still feed documented hook JSON; autonomous operation end to end is only partly verified (see docs/STATUS.md).
- Activity (working/idle) is MEASURED from hook events only (Stop/SessionEnd => idle; no event for 15 min while working => UNKNOWN). Without installed hooks it is UNKNOWN.
- The supervisor cannot force the host to open a fresh session: `tz sup next-session` prints the command; `--yes` launches a headless `claude -p` only on your say-so.
- Adapters: only claude is REAL. The other 7 generate rules files and declare unverified capabilities.
- Overlay: built with Command Line Tools swiftc, selftest + process-alive tested; the on-screen look was not visually verified.
- Registry never fetches URLs. A/B experiment not run (isolated login 401); needs your approval and a cost estimate.
- Not built: real A/B results. Subagent cost and $ are EST (see above). RTK: each Bash call's rtk delta goes into the ledger as a measured entry (rtk's own measurement, not TZ's).
- Windows: TOKENS SAVED counts today since local midnight across all chats; `tz stats` LAST 24H is rolling; history.json keeps one snapshot per day.
- Fresh-chat saving (in TOKENS SAVED, split as [EST input-eq]): per call 0.1 x (old chat's last context - new chat's startup context), minus the new chat's measured startup write; can be negative. All inputs measured; the only assumption is the same calls in the old chat with a warm cache. Each old chat links to one new chat. Against /compact the saving is smaller. Chats are linked within 24 h when they worked in the same project folder (most frequent logged cwd other than home), wherever they were opened.
- Session Economics (continue/compact/fresh over 5/10/20 turns) is a model from this chat's measured usage; projected vs actual is printed once replies exist.
- Loop, stalled-subagent, idle-cache, same-file (claims.json) and cleanup lines are advice only. Subagent stall is a heuristic (no host signal for "still running").
- Output trim (bin/tzout.py): live-verified on claude 2.1.318 for Read, Glob and Grep content only (headless Haiku probe, isolated config).
  WebFetch and MCP trims are unit-tested only; the WebFetch field name `result` is assumed. Live check needs a paid run: NOT done.
  The host ignores a replacement that breaks the tool's output shape (the model then gets the original output, nothing breaks).
  Read keeps only the head (>20k chars) so line numbers stay right; the model must Read with offset for the rest.
  The full text is stored in ~/.claude/token-zombie/recall (dir 0700, files 0600, last 200 kept) and can hold secrets that were in the output.
  Off: config "out_trim": false or env TZ_OUT=0.
- Read guard: default is advice (same as 0.3.0). `"read_guard": "deny"` denies an unchanged re-read once (retry allowed); off for subagents.
  Saving from deny is not benchmarked.
- Subagent overhead: caveman + ponytail used to re-inject ~8.5k chars (~2.1k tok EST) into every subagent; both are off since 2026-11-22 (owner yes), TZ core rules (~922 chars) replace them in the main chat only.
- `tz skills` invocation counts come from local chat logs (last 30 days, ~7 s scan); skills run via hooks (caveman SessionStart) are not counted as invoked.
- tz-vet LOW tier: a HIGH pattern found only under tests/fixtures/bench/eval/examples/docs/CI or on a code comment line is LOW.
  .md/.txt/.mdc lines are never downgraded. LOW still needs a human glance; it is a noise cut, not a proof of safety.

- `tz agent` / `tz code --run`: the pipeline is covered by the test suite with a simulated host; its first live Claude run comes with EditSutra.
