# Benchmarks
- `tz bench [--chat-tokens N] [--json]`: synthetic project. Filter bytes and resume size are MEASURED; duplicate-read saving and replaced-chat size are assumptions (EST); startup context and provider cache are UNKNOWN. Net of tz overhead.
- `tz bench compare --baseline LOG ... --optimized LOG ... [--both-passed] [--overhead-tok N]`: real A/B from chat logs of the same task without and with tz.
- `tz bench results [dir]` shows A/B evidence. Runner `tests/ab/run_experiment.sh` has hard spend caps; the real A/B has not been run (needs owner approval and a cost estimate).
- RULE: make no savings claim without a valid baseline comparison (both runs passed the same acceptance test). Otherwise report MEASURED/EST/UNKNOWN as printed.
