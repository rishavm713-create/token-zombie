# Changelog
## Unreleased
- 4 new mods (30 in total): `tz-secret-guard` (blocks commands that would expose secrets), `tz-danger-guard` (blocks destructive commands; `/danger off|on`), `tz-turn-nudge` (toast every N turns to save a handoff; `/nudge <turns>`), `tz-auto-checkpoint` (`/checkpoint` shows the last prompt to resume from). Website updated.
- The 24 `mods/` ship with the plugin: `plugin.json` lists them as dependencies and `marketplace.json` registers each, so `claude plugin install token-zombie@token-zombie` installs them all (checked in a clean config dir).
- Skills `careful-zones` and `breaker-agent` added (from TZ Studio).
- Fix: `test_cont` and `test_out` set `TZ_DEDUPE=0`; the 5 s hook dedupe swallowed their repeated payloads (8 false failures).
- Bundled TokenEconomizer (Microsoft, MIT; third_party/tokeneconomizer): learned repo facts, unused-tool pruning and a stuck-loop guard run as extra hooks; `tz te <args>` runs its CLI and `tz te backfill` imports earlier Claude Code sessions for every project now, so no project starts blank. Commands `/token-zombie:te-*`.
- Offline auto-note: a hook refreshes a small continuation note (git changes, last test, last ask, next step) after each turn and every 2 min of work, with no model call. A new chat in the same folder reads only that note, and only when work was left open (limit hit or crash). The same hook also writes `handoffs/YYYY-MM-DD-auto.md` (done / left / next, at most 30 lines) in projects that already have a `handoffs/` folder. Switch: `TZ_FEAT_AUTO_NOTE=0`.
- Model switches now record the chat size at the switch, so the uncached re-read cost is visible.
- Fix: `tests/test_live.sh` sent an identical payload twice within 5 s and the hook dedupe dropped it (5 false failures); the test now sets `TZ_DEDUPE=0`.
- Auto handoff at 100k tokens: the end-of-turn hint writes `handoffs/YYYY-MM-DD.md` (done / left / next, at most 30 lines) and tells the owner to start a fresh chat; the bar shows "Start a new chat · handoff saved".
- Reading and searching go to cheap subagents (one line in the core rules); output trim now also covers stderr and Agent/Task results.

## v2.1.0 (2026-11-25; tag v2.1.0 on main 78743eb)
- Fix: install.sh recognises its own hooks whatever the checkout/cache directory is named (was: duplicates, failed uninstall/restore unless the path contained token-zombie/bin).
- Fix: stuck detector deletes its state file on reset and ignores tool hooks without a tool name.

Added:
- Feature switches (`TZ_FEAT_<NAME>`, config `features`).
- Prompt-cache life measured (1 h or 5 min) for idle and fresh-chat advice.
- Duplicate-read denial (`read_guard: deny`) carries a file outline.
- Shell command parser behind the safety check (`tzshell`).
- Stuck-pattern advice (`tzstuck`, adapted from OpenHands, MIT).
- `tz toolprune` (rules ported from TokenEconomizer, MIT) and duplicate read-only MCP call advice.
- Hook text cap (`tzfit`), optional plan re-injection (off by default).
- `tz mem index|search`, task dependency cycle refusal, `tz find-code`, `tz impact --diff`, `tz rank --tokens/--mention`.
- `tz agent --wall/--max-errors`, claim leases.
- 5 h usage blocks, cache hit rate, usable context % in `tzusage`.
- Offline `tz bench matrix`; optional harbor adapter.
- `skills/tz-craft`.
- `bin/tztips.py` (spec tips) wired into the hooks and `tz tips | instr | defaults | stats --breakdown`; advice on by default, blocks opt-in.

Changed:
- Bash safety check fails closed if it crashes (before: allowed), and uses the working directory.
- One loop warning per call (stuck detect replaces the older line).

Measured (offline, 1 trial, characters, scripted agent): net 46,929 with 2.0 behaviour (fp 1, fn 1) vs 51,356 with all v2.1 features (fp 0, fn 0). Most of both comes from the 2.0 output trim. Provider tokens: UNKNOWN. See `docs/LIMITATIONS.md`.

Docs: `docs/LEDGER.md`, `docs/COMPETITIVE-ANALYSIS.md`, `docs/USAGE-V2.1.md`.

## v2.0.1 (2026-11-24)
- Windows supported via `bin/tzpy` (Git Bash; Python 3.8+ via python3/python/py -3); CI runs on ubuntu-latest, macos-latest and windows-latest.
- Verified 2026-11-24 against real Claude Code: hooks fire in a live `claude -p` session, slash commands run, MCP tz_* tools load, install from the GitHub-hosted marketplace works.
- Creator and brand: BRANDING.md (copyright vs brand, fork and commercial-use rules, India/international legal notes, questions for counsel); creator statement in README and site; plugin/marketplace author set to Rishav Mishra. MIT licence unchanged. TZ Studio stays a possible future product in a separate repo (docs/OPEN-CORE-DECISION.md).
- Docs: `tz ab` and `tz preflight --smoke` described as optional, opt-in (spend your own Claude Code usage); free benchmark path is `tz bench replay` / `tz stats`. Savings stay labelled MEASURED / EST / UNKNOWN.
- Tree-sitter: tested with the real `tree_sitter` + `tree_sitter_typescript` packages on 40 EditSutra JS/TS files (all parsed; skeletons 14% of original vs 60% with the built-in scanner). Optional dep; without it the scanner is used. The suite's real-package test runs when `TZ_TS_PYTHON` points at a Python that has it, else prints SKIP.
- `tests/run_all.sh` prints SKIP lines and a skip total; skips are never counted as passes.
- EditSutra acceptance: see docs/EDITSUTRA-ACCEPTANCE.md.
## v2.0.0 (2026-11-24)
Built and tested (tests/run_all.sh; counts in docs/MASTER-BUILD-ROADMAP.md section 10):
- Workers: `tz worker` registry (cli/http/offline), `tz hw`; worker timeout kills the whole process group (test_killgroup).
- Agent: `tz agent` pipeline with `--gate` (diff/ownership/safe/secrets/tests-ran/API drift (Python)/regression link/lint-type-audit detect), bounded repair, killed-run `--resume`, `--rollback` (restores only files the failed run changed).
- Repo intelligence: `tz sym`, `tz exists`, `tz rank` (aider repomap idea, Apache-2.0, in NOTICE), `tz map`, `tz worktree` with file ownership, task dependencies in `tz next`.
- Token/context: re-read stub, ANSI strip, JSON outlier keep, handoff tail (planning-with-files, MIT, in NOTICE), destructive-command rules (cc-safety-net, MIT, in NOTICE).
- Supervisor detectors (queued/failed/abandoned/stalled), install via plugin marketplace proven with a local-path marketplace in a temp config dir.
Untested: real `claude -p` session with the plugin active, MCP tools/skills/commands loading from an installed plugin, GitHub-hosted marketplace install, JS/TS API-drift check, lint/type/audit with real tools, tree-sitter with the real package, paid A/B benchmarks.
## v0.1 (2026-11-20, release candidate, not installed/published)
Added: bin/tz CLI; tzhandoff (handoff/resume/memory); tzusage (context, tokens, burn, 5h/7d, warn states); tzopt (dup reads, log analysis, filter, classify, ledger); tzcap (inventory, overlaps, advice, GREEN/YELLOW/RED); installer --dry-run and --restore; tests run_all.sh (164 checks); docs.
Changed: tzlib gets `ctx_window` setting; tz-guard adds dup-read advice (additionalContext only) to its Read hook.
Unchanged: all v3.1 hooks, tz-status.py flags, tz-vet.sh. Baseline test_tz.sh still pass 60 fail 0.

## v0.1.1 (unreleased)
Added: task-wrap, checkpoint, DAILY.md; tz bench; usage levels NORMAL..EXHAUSTED; tz instructions; tz profile (--yes); subagent model advice; installer --restore skips backups that already contain tz.
Fixed: test_tz.sh no longer reads real settings.json.

## v0.2.0 (2026-11-20, unreleased, not installed)
Added: tzsup (supervisor + status bus ~/.claude/token-zombie/status.json, tasks.json, auto checkpoint, next-session brief; tz-guard calls tick, TZ_SUP=0 disables), tzroute (model advice, override, routing.jsonl), tzadapters + adapters/ (8 agents, only claude real), tzreg (local repo registry, no network), tzdash (static HTML, 127.0.0.1 server), tzcompanion (token-auth localhost status server), tzmascot (5 states), tz profile save/apply/rollback (dry-run default), tz optimize: repeated research/exploration/oversized outputs, tz bench results. Tests: test_sup, test_e2e (272 checks total).
Not built: native always-on-top overlay (needs Swift/Electron toolchain approval); live A/B run (login 401, needs approval).

## v0.2.1 (2026-11-20, release candidate, not installed)
Added: hook-driven supervisor (Stop/SessionEnd/PreCompact wired, activity MEASURED from hook events else UNKNOWN, checkpoint throttle, corrupt-state recovery), tzbus, installer hardening (shape checks, crash-safe, auto rollback, --check, idempotent, upgrade from v0.1), statusline mascot, adapter interface (status, installed_here, supports()), Host-header + token + CSP on dash/companion, native Swift overlay, A/B: orphan-spend counting, hard caps clamp flags, wall-clock kill. Tests: +test_install2, test_hard.
Changed: installed guard hooks 3 -> 6, PreCompact now also runs the guard.

## v0.3.0 (2026-11-20)
Added: Claude Code plugin + marketplace (`.claude-plugin/plugin.json`, `marketplace.json`; MIT); 8 namespaced commands `/token-zombie:tz|optimize|audit|review|compact|board|supervisor|benchmark`; modes off|lite|full|ultra (`tz mode`); in-chat panel Mod (`hooks/panel.tsx`, bare `/tz`); `host.json` (cost from the statusline `cost.total_cost_usd`, MEASURED by host); `agents.json` written from the panel; dashboard with 4 metrics and an SVG zombie mascot; `install.sh --statusline-only`; skill moved to `skills/token-zombie/`; repo files for publishing (README, LICENSE, CONTRIBUTING, SECURITY, CI, issue templates).
Added (toolbar): the panel Mod's default view is one slim horizontal bar above the prompt. It shows the mascot, TOKEN ZOMBIE, a mode pill, four metrics (AGENTS, SKILLS ON, TOKENS SAVED · EST, OPTIMIZATIONS), a status dot, and a chevron that opens the detail pane (same as `/tz`). Desktop draws the SVG mascot hanging on the bar's top border; the terminal shows an emoji. The dashboard uses the same bar as its collapsed `<details>` summary, with the full cards inside. How each metric is calculated: [docs/METRICS.md](docs/METRICS.md).
Changed: the skills metric is labelled SKILLS ON (dashboard: SKILLS ENABLED), because it counts enabled skills on disk, not skills that were used. The dashboard's mascot chip shows only the animated state (it used to show the status-bus state and the visual state side by side, e.g. "SLEEP · excited"). Mascot priority is fixed: alert, excited, working, sleep, idle.
Fixed: dashboard bar labels were cut off with an ellipsis between about 640 and 820 px. The bar now wraps its metrics to a second row at 820 px and below. Checked at 375, 600, 674, 780, 860, 1100 and 1440 px, both collapsed and expanded.
Privacy: tests use generic fixture names and a throwaway HOME only. No test reads the real home folder.
Tests: 377 -> 517 shell checks (`bash tests/run_all.sh`), plus 14 Mod tests (`claude plugin test .`).

## v0.4.0-rc1 (2026-11-21, release candidate: uncommitted, not installed, no paid benchmark)
Added: output trim + local recall for big Read/Grep/WebFetch/MCP results (bin/tzout.py, `tz recall`; Bash left to rtk);
tzopt.read_decision (read_guard advice|deny|off); `tz stats` shows rtk gain; `tz skills` shows plugin skill cost, 30-day
invocations and never-invoked skills; tzlive live ledger (skill states, agent lifecycle, Grep/Glob/Web dedupe advice);
tzhooks hook-time bench; tzpreflight A/B readiness; SubagentStop hook; docs/REUSE.md, docs/REQUIREMENTS.md.
Changed: PreToolUse matcher Read|Grep|Glob|WebSearch|WebFetch|Agent|Task; tool events skip the supervisor tick;
tz-vet HIGH -> LOW for test/fixture/CI/comment-only hits (.md never downgraded); recall store private (0700/0600).
Tests: bash tests/run_all.sh 584/0; claude plugin test . 14/0. Limits: docs/LIMITATIONS.md.

