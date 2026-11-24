---
description: "Run the TOKEN ZOMBIE benchmark (MEASURED vs EST vs UNKNOWN)"
allowed-tools: Bash(python3 *), Bash(python *), Bash(py *)
---
Run `python3 "${CLAUDE_PLUGIN_ROOT}/bin/tz" bench $ARGUMENTS`. Report the table as printed. Make no savings claim unless a valid baseline comparison exists in the output; label EST and UNKNOWN items as such.

If `python3` is not found (Windows), run the same command with `python` or `py -3`.
