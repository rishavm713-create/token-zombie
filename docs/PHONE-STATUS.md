# TOKEN ZOMBIE: upgrade status (branch upgrade/token-optimization)

Tests: full suite 927 pass / 0 fail, plus 5 new (test_upgrade).

## New in this upgrade
- tz_verify now runs the project tests (auto-detected) and reports PASS/FAIL with the handoff score.
- `tz handoff verify --run-test` does the same from the CLI.
- Prompt hook no longer says "N independent tasks" on long pasted text (over 1500 chars).
- Test suite no longer leaves the four tracked docs files rewritten.
- `tz bench harbor`: Terminal-Bench/Harbor control vs treatment commands (prints; --run executes).
- Earlier, already shipped: 9 Mods tools, 3 panel buttons, tz agent, tz map, tz xcheck (per category, per session), cost control.

## Not done (honest)
- Panel pause/approve/retry, agent orchestration: no host API in this build.
- Live check of the Mod inside a fresh chat with the plugin on.
- With/without benchmark: needs login in ~/tzab/control and ~/tzab/treatment; harbor not installed.
- Cache-aware reads: tz has no cache tracking yet.
- Replay saving is 0.58% (offline). No end-to-end or quality claim yet.
