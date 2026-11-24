# What is left (2026-11-22)

Source: gaps in [VISION.md](VISION.md). Done and skipped: per-day (24 h) savings window, live panel updates.
Order = priority. Gated items need the owner's yes first.

## Build (no approval needed)
1. [x] **Prevent, not detect.** (built 2026-11-22: `tzcont.churn_tool/churn_prompt/compact_hint`, tests in test_cont.sh §5) Spot churn early and offer a checkpoint plus a fresh chat before 100k. Signals: the same file edited or re-read 3+ times, 3+ images in the chat, chat growing fast while edits stay small, the same instruction repeated. Hook: `tz-guard.py` UserPromptSubmit/PostToolUse; logic in `tzcont.py`. Never force a stop mid-task. When a task closes past 100k, tell the user to run `/compact`. The PreCompact note (`tz-compact.py`) keeps only done, left and next, so the next message re-sends a few k tokens, not the whole chat.
2. [~] **Savings beyond Bash.** (2026-11-22: deny entry + reversal on retry, src/calc per entry, all TZ advice counted as overhead; left: check output-trim entries reach the bar) Write a measured ledger entry when a duplicate Read is denied (`read_guard: deny`), sized as the file chars that were not re-sent. Check that output-trim entries reach the bar.
3. [x] **Subagent cost.** Per-subagent tokens from the SubagentStop transcript; show the count in `tz live agents` and `tz stats`.
4. [x] **$ cost estimate.** Tokens times the published per-model price; label EST; show in `tz stats`.
5. [~] **Task modes that act.** (2026-11-22: `tz route` prints per-mode read/subagent limits and matching skill packs; advice only) Map `tz classify` (quick/standard/research/engineering/audit) to concrete advice: model, read limit, agent count. Manual `tz mode` always wins.
6. [x] **Stalled or looping agent detection.** The same tool and input repeated N times, or a subagent running more than X min with no new output. Gives advice only.
7. [x] **Multi-session claim board.** `~/.claude/token-zombie/claims.json`: a session claims the files it edits; a second session editing the same file gets a warning.
8. [x] **Instruction conflict check.** `tz instructions` flags opposite rules across CLAUDE.md files (keyword pairs, EST).
9. [x] **Cleanup advice.** At task end, list skill packs turned on this session that are still on.
10. [x] **Docs.** Update `LIMITATIONS.md`, which still says no live session ran with the plugin, and add the per-day window and rtk entries. README metrics line.
11. [x] **Tests.** (2026-11-22: panel tests run with `claude plugin test .`, bun cannot resolve the host modules; e2e polls 5 s) Make `hooks/panel.test.tsx` runnable (react missing for bun). Fix the flaky `test_e2e.sh` `sleep 1` (poll up to 5 s).

## Gated (ask the owner first)
12. [skip] (owner 2026-11-22: skip) Optional opt-in A/B run (`tzab.py`, spends your own Claude Code usage). Free path: `tz bench replay`.
13. Real 5-hour reset (`rate_limits.resets_at`, Claude's "resets X" message). Owner said skip for now.
14. Public GitHub repo, release package, website, public install. Needs a publish yes.

## Next (owner spec 2026-11-22, not built): Session Economics
15. [x] (built 2026-11-22: `tzcont.measure/econ/econ_lines/econ_track`, econ.json, tests test_cont.sh §8; panel row not run in a test, react missing) Continue / COMPACT / FRESH calculator with 5/10/20-turn projections, per-model $ (API-equivalent, apart from plan quota), cache hit rate, projected vs actual after a switch. Extend `tzcont.stay_or_fresh`, `tz stats`, `tz route`, panel; no new ledger. Built so far: rolling 24h usage by model/agent, fresh-chat counterfactual (EST) in TOKENS SAVED.

## Built 2026-11-22 (guard batch)
16. [x] File guard before the write, circuit breaker (3 failures), `tz skills --effect`, `tz replay` (tzcont.py, test_cont.sh §12).
17. [x] REUSE.md done (6 repos, read-only, partial fetches); built the 1 h cache-write pricing split. The 50-100 repo survey + benchmarks of big frameworks stays out of scope (stars are no evidence).
18. [ ] Optional: PostToolUseFailure hook event (needs install.sh EVENTS + ~/.claude settings change, owner yes).

## Built 2026-11-22 (research round)
19. [x] docs/GITHUB-CAPABILITY-RESEARCH.md (baseline = pasted research, no full audit); next-call cost line in `tz stats`; `tz recall --search` (FTS5, independent code).
20. [ ] Open: memory retrieval over handoffs (reuse tzout.search), subagent ROI + MCP attribution, PostToolUseFailure/PostCompact (owner yes, see 18).

- Coding row (2026-11-22): `tzcont.code_test/code_line/untested_advice`; `tz stats` prints edits/test runs/last result/untested; one Stop advice line when edits have no test since. Pass/fail is read from output text (heuristic). Panel row NOT added (UI dropped). Optimisation list (output trimmed, dup reads, overhead, net) still not built.

- `tz systems` (2026-11-22): `bin/tzsystems.py`, 8 systems (resource, context, zombie, infection, agents, survival, continuity, quality) from state files only, writes `systems.json`. Panel NOT wired (panel.tsx has no 9-tab UI; owner said both "leave the UI" and "UI approved": needs one decision). UNSUPPORTED/owner-gated: SubagentStart/Stop lifecycle, InstructionsLoaded, loaded/invoked capability states, per-agent cost, stalled-agent monitor via hooks. Not built: duplicate-assignment/minimum-agent advice, incremental transcript offsets, hook-overhead measurement for new code.

- Memory retrieval (2026-11-22): `tz recall --search WORDS --handoffs` also indexes ./handoffs/*.md (reuses tzout FTS5, no new store). Research baseline re-pasted by owner = already mapped in GITHUB-CAPABILITY-RESEARCH.md.

- Panel pane now has a coding row (hooks/panel.tsx, reads coding.json written by tzcont._pub_code; hidden if >24h old). UI layout/tiles unchanged. Panel test added (19/0).

## Hook events registered (2026-11-22, owner: "all the research")
- SubagentStart, InstructionsLoaded, PostCompact, PostToolUseFailure added to hooks/hooks.json and install.sh (12 events, tz-guard x11). Live ~/.claude/settings.json is NOT changed: owner runs install.sh.
- tzlive: agents tracked by exact agent_id (start/stop), instr files (bytes MEASURED, tokens EST size/4), compaction list. Test in tests/test_live.sh.
- Built: duplicate agent assignment advice (same type+description, advice only; tzlive PreToolUse Agent). Still not built: event engine, shadow-mode tests, code-aware compression, minimum-agent advice.

## Built from the GitHub research (2026-11-22, round 2; owner: "make it tz complete")
- Agent ROI (cctop/Agent Trail): `tzlive.agent_costs/roi`, `tz live roi`; cost joined to hook agent_id; flags small/empty/failed/duplicate (advice only; tokens MEASURED, $ EST). Shown in `tz systems` agents row.
- Compaction verification (Hermes): `tzlive.verify_compact` on PostCompact compares the continuation note with `compact_summary`; weak => one advice at next prompt naming the note (deterministic fallback); no summary text => `unknown`, never guessed. Needs the live host to send `compact_summary` (UNVERIFIED on real host until install.sh is re-run).
- Progressive retrieval (Claude-Mem): `tz recall --search W [--handoffs] [--memory]`, then `tz recall h:<file>|m:<file> [--lines A-B]`; ids path-safe.
- Shadow/canary (Caveman): config `out_trim: "shadow"` logs cuts without applying; `tz shadow` shows cuts, would-save chars, and recall re-reads as a quality-risk proxy. Default stays live trim.
- Not built: incremental byte-offset scans (no slowness measured), AST code compression (research: reject for now), vector memory, unified SQLite ledger (existing JSON ledger kept; no duplicate system), hook overhead of the 4 new events not benchmarked.

## Round 3 (2026-11-22): final brief
- Added hook events PostToolBatch, PreModelSwitch/PostModelSwitch, WorktreeCreate/Remove (repo files only; owner re-runs install.sh to activate). 17 events total.
- Stalled-agent flag in `tz live roi` (running, transcript quiet >10 min).
- See docs/IMPLEMENTATION-MATRIX.md. Not built: thinking-token split, incremental scan, AST compression, vault index, CANARY/ACTIVE gates, unified SQLite ledger, FileChanged, 9-tab UI (owner decision).
- Full suite + plugin test: all pass (19/0). Nothing committed. GitHub upload + website: waiting for repo visibility answer.

## Round 4
Built: tzdb ledger, alerts outcome, vault index, tz compress (Python), incremental scan, accounting labels. Nine-tab UI dropped by owner. Not built: semantic memory, non-Python AST, task vault index, auto promotion.

## Round 5
See docs/AUDIT.md: item-by-item labels. New: tz rework, hooks bench for 18 events. Open: real A/B trials, quality-adjusted savings, host verification, hook-event audit, website.
