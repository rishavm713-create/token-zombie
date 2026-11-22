# Benchmark method (A/B). STATUS: zero real trials recorded. No savings are claimed until this has run.
Principle: same task, same start repo, same model and settings, same acceptance tests. Only TOKEN ZOMBIE differs.

1. Pick 3 small tasks with an independent acceptance test (a script that exits 0 only if the task is done). Keep them in `bench-tasks/`.
2. For each task, run N>=5 control trials (no TZ) and N>=5 treatment trials (TZ installed in a separate `CLAUDE_CONFIG_DIR`), alternating order.
   Runner: `bin/tzab.py` (headless `claude -p`, hard token caps, raw stream kept as evidence; uses only the config dir you pass).
3. After each trial run the acceptance test; record pass/fail. A failed trial stays in the data.
4. Compare: `tz bench compare --baseline LOG... --optimized LOG... --both-passed` (counts input + output + cache write + cache read; cache is not free).
5. TZ's own cost: hook text and handoff are already inside the treatment log totals; time overhead from `tz hooks bench`.
6. Report per task: all raw totals, median, spread, pass rate, rework (`tz rework LOG`). Never only the best run.
7. Quality-adjusted savings = tokens per PASSED task, control vs treatment. `tz bench quality TRIALS.json` (list of {arm, task, tokens, passed}); verdict PROVEN only with 5+ trials per arm and no pass-rate drop.
Cost warning: 3 tasks x 10 trials is 30 real sessions on your plan. Start with 1 task x 5+5 to see the spread.
Limits: few trials = anecdote; one model; synthetic tasks; results do not transfer to your project automatically.
