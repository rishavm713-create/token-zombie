# Commands
Plugin slash commands (namespaced): `/token-zombie:tz`, `optimize`, `audit`, `review`, `compact`, `board`, `supervisor`, `benchmark`. Each runs `python3 "${CLAUDE_PLUGIN_ROOT}/bin/tz" <sub>` and reports terse. If the in-chat panel is loaded, a bare `/tz` also exists (no model call).

CLI subcommands (`tz help` is authoritative): status, forecast, startup, optimize, filter, classify, stats, handoff, task-wrap, checkpoint, resume, skills, capabilities, security, audit, instructions, profile, bench, config, report, sup, route, adapters, reg, dash, companion, mascot, overlay, mode.
Exit codes: 0 ok; 1 failure or RED/no state; 2 usage error; 3 `status` in STOP state.
Config: `tz config` shows each setting and its source; `tz mode [off|lite|full|ultra]` shows or sets the mode. Precedence: env `TZ_<KEY>` > config.json key > mode profile > defaults.
