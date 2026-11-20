---
description: "TOKEN ZOMBIE status (context, tokens, burn, warn state); pass a tz subcommand to run it"
allowed-tools: Bash(python3 *)
---
Run `python3 "${CLAUDE_PLUGIN_ROOT}/bin/tz" ${ARGUMENTS:-status}` (subcommands: status, forecast, stats, config, mode, report, ...). Report terse. Keep MEASURED / EST / UNKNOWN labels as printed; never invent numbers.
