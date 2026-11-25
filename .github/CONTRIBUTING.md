# Contributing

- Python 3 standard library only. Keep scripts short; match the style of the file you edit.
- Run the full suite before every PR: `bash tests/run_all.sh` (must end `fail 0`).
- Tests use a fake HOME (a temp dir). Never read or write the real `~/.claude`, `settings.json` or `~/.claude/token-zombie` from a test.
- Never weaken, skip or delete an existing test to make a change pass. Add tests for new behavior (`ok "name" 'cond'` helpers; end with a `pass N fail N` line so `run_all.sh` can sum it).
- No network calls, no telemetry, no uploads. Every metric is MEASURED (from a real file or host event) or labelled EST / UNKNOWN; no invented numbers and no savings claims without an A/B baseline.
- No personal paths, usernames, tokens or `.log` files in the repo (`tests/test_repo.sh` checks this).
- Security issues: see SECURITY.md, do not open a public issue.


## First contributions

Focused contributions are welcome: reproducible bug reports, installation/documentation fixes, compatibility verification and tests for existing behaviour. Open an issue before larger changes so scope and safety constraints can be agreed.

## Pull request checklist

- Explain the user problem and the smallest proposed change.
- Add or update a test, or include a precise manual verification procedure.
- Run `bash tests/run_all.sh` and report the result.
- Update documentation when commands, behaviour or compatibility change.
- State the Claude Code version and OS actually tested; mark host-dependent behaviour unverified when it was not tested.
- Never include real transcripts, tokens, personal paths, credentials or unredacted logs.

## Project principles

Prefer evidence over claims. Preserve fail-open behaviour and recoverability. Keep core hooks local, fast and free of model/network calls. Never trade task correctness or developer control for a lower token count.
