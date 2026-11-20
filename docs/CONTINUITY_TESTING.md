# Continuity tests
`bash tests/test_next.sh` (offline, fake HOME): persistence, deps, duplicates, bad dep/gate, gate refusal, failed vs passing done, no restart of done, pack cap + content, tz-start injection, hook pass/fail/non-test, manual + before-limit checkpoint, corrupt file, fresh-process resume, measure arithmetic, missing transcript, CLI registration.
Full: `bash tests/run_all.sh`; `claude plugin test .`. No paid runs.
Install/use offline: same installer as the rest of TZ; no extra setup, files live in the project's `handoffs/tasks/`.
