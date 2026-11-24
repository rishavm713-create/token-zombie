---
description: "Supervisor status, tick, tasks, next-session brief"
allowed-tools: Bash(python3 *), Bash(python *), Bash(py *)
---
Run `python3 "${CLAUDE_PLUGIN_ROOT}/bin/tz" sup ${ARGUMENTS:-status}` (subcommands: start, tick, status, next-session, task). Report state, risk, activity, open tasks terse. next-session only prints the command; never add --yes unless the owner said so.

If `python3` is not found (Windows), run the same command with `python` or `py -3`.
