# Metrics
Every number carries a label: MEASURED (real file or host event), EST (estimate/assumption), UNKNOWN (not available). Never replace UNKNOWN with a guess.
- Tokens: MEASURED from the chat transcript (input/output/cache) and, in the panel, from turn usage events since it loaded.
- Cost: only the host-measured `cost.total_cost_usd` from the statusline JSON, saved to `~/.claude/token-zombie/host.json`. If the statusline is not wired: "n/a". No $ is computed from guessed prices.
- Context %: EST. `ctx_window` (default 200000) is a setting, not read from the provider.
- 5h/7d plan limits and reset times: shown only when Claude Code passes `rate_limits`; otherwise "not provided".
- Agent time: MEASURED turn durations; subagent cost tracking is not built.
- MCP/plugin tool-schema cost: UNKNOWN. Skill descriptions: chars/4 per chat (EST).
- Per-day tokens by model: `python3 "${CLAUDE_PLUGIN_ROOT}/bin/tz-status.py" --history [days]`.
