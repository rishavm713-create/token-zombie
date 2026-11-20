---
description: "Write a continuation note, then give the exact /compact line"
allowed-tools: Bash(python3 *)
---
Run `python3 "${CLAUDE_PLUGIN_ROOT}/bin/tz" checkpoint` then `python3 "${CLAUDE_PLUGIN_ROOT}/bin/tz" resume`. Then print one line the owner can paste: `/compact <keep: task, changed files, last test result, next step>` using what resume printed. A command file cannot run /compact itself; do not claim it did.
