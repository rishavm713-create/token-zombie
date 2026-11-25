# Limitations (honest list)

## v2.1 limitations (2026-11-25, code at 8c703c3)

### Measurement
- Provider tokens for any v2.1 saving: UNKNOWN. No paid baseline-vs-TZ run; no answer-quality A/B.
- Offline matrix (`tz bench matrix --trials 1`, scripted agent, characters; saved / TZ-injected / net, false positives, false negatives): `tz20` 47,478 / 549 / 46,929, fp 1, fn 1. `all` 53,236 / 1,880 / 51,356, fp 0, fn 0. Difference in net: 4,427 chars in synthetic scenarios. One trial; the 5-trial run is not done.
- That matrix has no true no-TZ arm: the `off` arm (mode off) still shows 47,724 chars saved from output trimming. So most of the net figure is the 2.0 trim, not v2.1.
- The matrix runs with `read_guard=deny`; the product default is `advice`.
- `stuck_detect` has no offline saving: `all-minus:stuck_detect` nets 81 chars more than `all`. Its possible value (shorter loops) is not measured.
- `tz find-code` gain is small. Earlier recorded hit@10 0.742 -> 0.758 (adding `tzrank`). Rerun 2026-11-25 on 128 commits: 0.742 -> 0.750 (recall@10 0.583 -> 0.589). It depends on the commit history.
- `tz rank --mention` changes ordering; no retrieval or token gain is measured for it.
- Hook time in the matrix run: about 108-167 ms per hook on one Mac.

### Features
- `bin/tzfit.py` caps hook text by keeping head and tail. The dropped middle is not saved for recall.
- Duplicate-MCP advice (`mcp_dup`) is approximate: "read-only" and "nothing written since" are judged from tool names and the transcript. It cannot see changes made outside the chat. Advice only.
- `tz toolprune`: idle parking and auto-restore are not done. A denied tool stays denied until `--restore`. Evidence is past chats only.
- `safety_net` is in the feature list but no code reads it. `TZ_SAFE=0` is the real off switch. (Open fix.)
- The Bash safety check parses commands; it is not a sandbox and cannot catch every destructive form. In v2.1 it fails closed if the check itself crashes.
- `tz-craft`: the prompt hint (`tzondemand.craft`) is not called by any hook.
- `bin/tztips.py` (spec tips) is not wired at 8c703c3; wiring is in progress in another session. Its paste check can only warn.
- Not built although research proposed them: budget warning ladder, crash-restart backoff, `tz sym` name paths and `--refs`, AST pattern search, log compressor, `tz debt`, repeat-failure-to-fact memory.
- REA (reverse engineering) was not used: there were no compiled targets.

### Not possible from a plugin
- A hook cannot press buttons or run `/clear` or `/model`.
- It cannot merge or delete messages.
- It cannot rewrite a prompt; it can only block it or add context.
- It cannot switch the main model.

### Verification
- `tests/test_v21.sh`: 411 pass, 0 fail (rerun 2026-11-25, macOS).
- Full suite: last recorded on the v2.1 branch as 1352 pass, 14 fail (install / uninstall / hook count / state size / vet self-scan). Not rerun for these docs; not confirmed pre-existing. A sibling note says install tests fail when the checkout directory is not named `token-zombie`; that may explain part, unverified.
- v2.1 not run on Windows CI; not run on Linux for these docs. Not tried in a live Claude Code session for these docs.

---

## Earlier limitations (2.x)
- Platforms/verification (2026-11-24): macOS, Linux and Windows (Git Bash via bin/tzpy, Python 3.8+); CI on ubuntu/macos/windows-latest. Verified against real Claude Code: hooks fire in a live `claude -p` session, slash commands run, MCP tz_* tools load, GitHub-marketplace install works. Not verified: untested Windows edge cases beyond CI, JS/TS API-drift, real lint/type/audit tools.
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
- Registry never fetches URLs. Optional `tz ab` experiment not run; it is opt-in and nothing depends on it. Free path: `tz bench replay` / `tz stats`.
- Not built: real A/B results. Subagent cost and $ are EST (see above). RTK: each Bash call's rtk delta goes into the ledger as a measured entry (rtk's own measurement, not TZ's).
- Time windows: TOKENS SAVED counts today since local midnight across all chats; `tz stats` LAST 24H is rolling; history.json keeps one snapshot per day.
- Fresh-chat saving (in TOKENS SAVED, split as [EST input-eq]): per call 0.1 x (old chat's last context - new chat's startup context), minus the new chat's measured startup write; can be negative. All inputs measured; the only assumption is the same calls in the old chat with a warm cache. Each old chat links to one new chat. Against /compact the saving is smaller. Chats are linked within 24 h when they worked in the same project folder (most frequent logged cwd other than home), wherever they were opened.
- Session Economics (continue/compact/fresh over 5/10/20 turns) is a model from this chat's measured usage; projected vs actual is printed once replies exist.
- Loop, stalled-subagent, idle-cache, same-file (claims.json) and cleanup lines are advice only. Subagent stall is a heuristic (no host signal for "still running").
- Output trim (bin/tzout.py): live-verified on claude 2.1.318 for Read, Glob and Grep content only (headless Haiku probe, isolated config).
  WebFetch and MCP trims are unit-tested only; the WebFetch field name `result` is assumed. Live check (optional, uses your own Claude Code usage): NOT done.
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
