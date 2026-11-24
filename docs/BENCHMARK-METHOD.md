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


## Observed single-session result

The project owner reports one real TOKEN ZOMBIE session with **5,000,000 tokens saved**. This is a real-world single-session observation supplied by the project owner, not a hypothetical estimate. It is not yet a controlled multi-trial A/B benchmark and must not be generalized to other sessions.

**Publication status:** awaiting the session's redacted raw usage evidence and calculation breakdown. Before presenting this as independently reproducible proof, attach:
- the redacted session usage summary or transcript-derived evidence;
- baseline / counterfactual method used to calculate the 5,000,000 figure;
- input, output, cache-read and cache-creation components separately;
- measured versus estimated portions, including any token-equivalent assumptions;
- task completion and quality validation;
- TOKEN ZOMBIE hook / output overhead and net-savings calculation.

Until those details are attached, describe it as an **owner-reported observed single-session result**. Do not call it a controlled A/B result, median saving, or typical performance.

## Zero-cost replay (`tz bench replay`, 2026-11-23)
Reads every `~/.claude/projects/**/*.jsonl` offline. Per reply it takes the logged token usage (input + 0.1 x cache read + 1.25 x cache write = input-eq).
- TZ-on chats: trims are MEASURED from TZ's own markers; refetches (`tz recall`, re-reads of a trimmed file) and TZ's injected hook text are counted as cost.
- TZ-off chats: every tool result runs through the same `tzout.cut` code TZ uses live; overhead and refetch are added at the rates measured in TZ-on chats.
- A removed block of C chars is carried for every later reply until compaction: C/4 x (1.25 + 0.1 x (k-1)). Cache expiry is ignored, which under-counts savings.
- Result on this machine: 1,025 chats, net 7.9M input-eq saved = 0.58% (~$40 EST at list price). Repeat-search advice: <= 0.02% (upper bound).
- Not measured: answer quality and turn count. That needs the optional opt-in `tz ab` A/B (spends your own Claude Code usage).
