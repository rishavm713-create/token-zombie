# Contributing

- Python 3 standard library only. Keep scripts short; match the style of the file you edit.
- Run the full suite before every PR: `bash tests/run_all.sh` (must end `fail 0`).
- Tests use a fake HOME (a temp dir). Never read or write the real `~/.claude`, `settings.json` or `~/.claude/token-zombie` from a test.
- Never weaken, skip or delete an existing test to make a change pass. Add tests for new behavior (`ok "name" 'cond'` helpers; end with a `pass N fail N` line so `run_all.sh` can sum it).
- No network calls, no telemetry, no uploads. Every metric is MEASURED (from a real file or host event) or labelled EST / UNKNOWN; no invented numbers and no savings claims without an A/B baseline.
- No personal paths, usernames, tokens or `.log` files in the repo (`tests/test_repo.sh` checks this).
- Security issues: see SECURITY.md, do not open a public issue.
