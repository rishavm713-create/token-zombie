---
description: "Security-grade installed skills (GREEN/YELLOW/RED)"
allowed-tools: Bash(python3 *), Bash(python *), Bash(py *)
---
Run `python3 "${CLAUDE_PLUGIN_ROOT}/bin/tz" audit`. Report RED first, then YELLOW, one line each. For a folder: `python3 "${CLAUDE_PLUGIN_ROOT}/bin/tz" security <dir>`. GREEN is not proof of safety. Never install or delete anything.

If `python3` is not found (Windows), run the same command with `python` or `py -3`.
