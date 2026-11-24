---
description: "Review token waste in this chat and say what to do next"
allowed-tools: Bash(python3 *), Bash(python *), Bash(py *)
---
Run `python3 "${CLAUDE_PLUGIN_ROOT}/bin/tz" optimize` then `python3 "${CLAUDE_PLUGIN_ROOT}/bin/tz" status`. Summarise in 5 lines max: top waste, context level, and the one next action (continue, handoff, or fresh chat). Mark EST values as EST.

If `python3` is not found (Windows), run the same command with `python` or `py -3`.
