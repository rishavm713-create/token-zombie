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

## Offline feature matrix (`tz bench matrix`, v2.1)
Everything above this section is about other methods; this section covers only the matrix.

    python3 bin/tz bench matrix --trials 5 --v040 --out docs/bench/matrix-2026-11-25.md

Writes the markdown report and `FILE.json`. No network, no model, no paid calls. Latest run: `docs/bench/matrix-2026-11-25.md`.
Each hook event is one subprocess of `bin/tz-guard.py` with a fresh fake HOME; `read_guard=deny` in every arm (`--read-guard` changes it).

### Arms
| arm | what it is |
|---|---|
| `off` | `mode: off`. **Not a no-TZ control**: it only turns advice and feature flags off. Big-output trimming and some dup-read text still run. |
| `tz20` | The **current** code with every feature flag off. It is not the v2.0.0 tag. |
| `only:F` | `tz20` plus feature F. |
| `all` | Every feature in `tzlib.FEATURES` on (including opt-in `plan_reinject`). |
| `all-minus:F` | `all` without F (leave-one-out). |
| `all-minus-conflicts` | `all` without the second member of each pair in `CONFLICTS`. The list is empty, so it equals `all`. |
| `v040` | (`--v040`) `bin/` of git tag v0.4.0, extracted locally to a temp dir, same scenarios and labels. The harness calls `tz-guard.py` directly and does not apply `hooks.json` matchers. |

No arm runs without TZ. By definition it would save and inject nothing; it was not run.

### Scenarios
| scenario | script | label (FP / FN) | `saved` counts |
|---|---|---|---|
| `dup_read` | full Read, then the same unchanged file again | FN: denied and an identical retry is denied too (lock-out) | file size minus the re-read size. **Assumption:** with an outline the agent re-reads 1/5; without one it re-reads all (saved 0). |
| `idle_1h`, `idle_5m` | prompt after 15 idle minutes, 1 h or 5 min cache TTL | FP: "expired" with 1 h; FN: silent with 5 min | nothing |
| `safety` | 10 Bash commands: 4 destructive, 6 benign | FP: benign denied; FN: destructive not denied | nothing |
| `big_output` | 1,500-line command output | none | original minus replacement output |
| `stuck` | same failing command 5x, then 5 different commands | FN: no loop advice; FP: advice on the varied set | nothing |
| `mcp_dup` | repeated read-only MCP call, with and without an Edit between | FN: no advice; FP: advice after the Edit | 3,000 chars if advised. **Assumption:** the agent obeys and reuses the result. |

Scoring caveat: the `off` arm is not charged FN in `idle_5m`, `safety`, `stuck` or `mcp_dup`, so its `fn 0` does not mean it catches anything.
`net = saved - injected`. `saved` is gross; until 2026-11-25 `dup_read` and `mcp_dup` also subtracted the injected text from `saved`, so net counted it twice. Earlier 1-trial numbers (tz20 46,929; all 51,356) are not comparable.

### Conflict rule (`tests/v21/test_matrix.py`)
`all` must have 0 FP and 0 FN, net above `tz20`, and net at least that of every `only:F`. Feature F conflicts if removing it from `all`
lowers FP or FN, or raises total gross `saved`. F's own injected advice is overhead: reported, not counted as a conflict.
The rule compares totals, so offsetting changes in two scenarios could hide each other. Only leave-one-out is checked, not every pair.

### Result, 2026-11-25, 5 trials (MEASURED: offline chars; provider tokens UNKNOWN)
Per-arm and per-scenario saved / injected / net / FP / FN are in the report.
- `all`: saved 54,852, injected 1,880, net 52,972, FP 0, FN 0. `tz20`: 47,724 / 549 / 47,175, FP 1, FN 1. `v040`: 35,455 / 549 / 34,906, FP 1, FN 5 (4 are destructive commands not denied; its `hooks.json` PreToolUse matcher also does not include Bash).
- `off`: 47,724 / 199 / 47,525. Its net is above `tz20`: `big_output` trimming runs in both and `off` injects less.
- `big_output` is 47,724 of the 54,852 chars saved by `all`. The other 7,128 depend on the two scripted-agent assumptions.
- Trial variance: saved, injected, FP and FN were identical in all 5 trials of every arm (net sd 0). The scripts are deterministic, so this shows repeatability, not statistical confidence.
- Hook wall time varies with machine load (see ms mean ± sd per scenario); do not rank arms by it.
- `stuck_detect`: +81 injected chars, no offline saving (negative result). Its loop advice appears 2x in `all`, 1x in `tz20`.
- `safety_net` and `plan_reinject`: removing either changes no chars, FP or FN here. These scenarios do not show their value.
- The labels and scenarios were written alongside the features, so 0 FP / 0 FN in `all` is a regression check, not a general accuracy rate.

### Not measured
Provider tokens (input, output, cache read, cache write), cost, cache hits, model behaviour (whether it follows advice or re-reads 1/5),
task success, answer quality, turn count, real-session frequency of each scenario. No percentage or token saving may be claimed from this matrix.
Those need the paid A/B (`tz ab`, `bin/tzab.py`, protocol above). It spends the owner's usage, **needs the owner's approval, and was not run**.
