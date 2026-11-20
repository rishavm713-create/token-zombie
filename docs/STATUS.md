# Feature tracker v0.2.1 (BUILT / TESTED / VERIFIED / PARTIAL / BLOCKED)
VERIFIED = checked against a live Claude Code session. Nothing is VERIFIED yet: tz is not installed.
| Feature | Status | Note |
|---|---|---|
| CLI tz, handoff/resume/checkpoint/task-wrap | TESTED | |
| Usage levels, burn, 5h/7d (only if provided) | TESTED | ctx % is EST (window size is a setting) |
| Supervisor tick + status bus + tasks.json | TESTED | fed documented hook JSON; live hooks not run |
| Hook wiring (7 events) + installer/rollback | TESTED | fake HOME only, 22+12 checks |
| Activity detection | TESTED | MEASURED from hook events, else UNKNOWN |
| Auto checkpoint (throttled 120 s), handoff prep | TESTED | handoff text is written by you/the model; tz runs no tests |
| next-session | TESTED | prints command; --yes launches headless claude -p |
| Model routing | TESTED | advice only, EST costs |
| Capability profiles save/apply/rollback | TESTED | dry-run default; MCP/plugins advisory |
| Optimizer (dup reads/research/explore/oversized) | TESTED | |
| Statusline + mascot | TESTED | 5 states, no AI/network |
| Dashboard / companion (127.0.0.1, token, Host check) | TESTED | |
| Native overlay (Swift/AppKit) | PARTIAL | builds, selftest parity with python, runs; not visually verified |
| Adapters: claude | TESTED | |
| Adapters: codex cursor windsurf gemini cline roo antigravity | PARTIAL | rules generation only; capabilities declared, unverified |
| Registry | TESTED | local dirs only, no network |
| Benchmark synthetic + compare | TESTED | |
| A/B runner caps + interrupted recovery | TESTED | stub claude |
| Real A/B experiment | BLOCKED | login 401 in /Users/mac/tz-ab-config; needs your approval |
| Live end-to-end in real Claude Code | BLOCKED | needs install approval |
