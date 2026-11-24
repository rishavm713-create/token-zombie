---
description: "Dashboard: build the HTML status board or show companion info"
allowed-tools: Bash(python3 *), Bash(python *), Bash(py *)
---
Run `python3 "${CLAUDE_PLUGIN_ROOT}/bin/tz" dash --out "$HOME/.claude/token-zombie/dash.html"` and give the path. For a live local page: tell the owner to run `python3 "${CLAUDE_PLUGIN_ROOT}/bin/tz" dash --serve` (127.0.0.1 only) in a terminal. Do not start servers yourself.

If `python3` is not found (Windows), run the same command with `python` or `py -3`.
