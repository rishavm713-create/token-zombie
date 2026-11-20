# Changelog
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
