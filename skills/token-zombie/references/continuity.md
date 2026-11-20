# Continuity and resume
A task may span sessions; never mark unfinished work done because a threshold was hit.
- `tz resume [--run-test]` compares saved handoff state with branch, HEAD, edited files and the last test result, prints drift and the exact next action. It is read-only for your files.
- SessionStart hook (`bin/tz-start.py`) injects the HANDOFF.md top block + newest daily (<= 4000 chars).
- `tz sup next-session` prints the command and 5-line brief for a fresh session. `--yes` launches a headless `claude -p` only when the owner says so; the host cannot be forced to open a session.
- Open tasks: `tz sup task <id> [open|done|blocked]`.
