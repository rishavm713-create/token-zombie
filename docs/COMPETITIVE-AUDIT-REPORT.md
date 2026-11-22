# Competitive audit report (2026-11-23)

**Competitors researched:** 21 (6 token-saving, 7 monitoring/observability, 8 memory/handoff/workflow) from their GitHub pages; 1 candidate dropped (404). **Capabilities compared:** 23. Facts are marked VERIFIED (page states it) or CLAIM (author's number); code of competitors was not read and no number was reproduced.

**Built and tested in TZ:** output trimming with lossless recall, shadow mode, FTS5 recall, usage and cost with 5m/1h cache split, MEASURED/EST labels, subagent lifecycle and ROI flags, compaction survival check, handoff/resume, dashboard, CLI. **Partial:** Python-only code compression, burn/forecast, startup audit, routing advice, rework scoring, unified ledger. **Not built:** MCP/tool-schema cost signal, OTLP/team analytics, vector memory (the last by decision).

**Strongest:** honest labelling, subagent ROI, MIT with no telemetry, recoverable trimming. **Weakest:** no controlled A/B number, no demo GIF, one real adapter, toolbar look unverified on a real host, no social proof.

**Build next:** P0 real A/B trial and live-host verify (owner-run); P1 MCP cost signal, demo GIF, handoff chain id. **Deliberately not building:** nine-tab UI, RTK clone, Claude-Mem replacement, automatic agent spawning, early vector memory, lossy compression, blocking tools.

**Test status:** `bash tests/run_all.sh` = 800 pass, 2 fail on the first run. The 2 failures (`test_hard`: SIGKILLed-runner partial count and orphan partial) are timing tests; `test_hard.sh` rerun alone = 51 pass, 0 fail. Not yet re-run as a full suite after the rerun.

**Is TZ differentiated?** Yes, narrowly: it is the only one found that labels every number MEASURED/EST, flags low-value subagents, and ships MIT with no telemetry. It is not yet "best": leaders have bigger numbers, demos and stars. The savings claim stays at the measured 153,372 tokens until a real A/B is run.
