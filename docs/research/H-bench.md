# H - Benchmarking research (offline matrix benchmark for TZ v2.1)
Date 2026-11-25. Evidence via `gh api` (no clones). TZ files read: bin/tzab.py, bin/tzbench.py, bin/tzharbor.py, bin/tzreplay.py, bin/tzlib.py:19-56, docs/BENCHMARK-METHOD.md, bin/tzfeatures.json.

## 0. Verdict
Build ONE offline harness, `tz bench matrix`, on top of a **scripted-agent replay** (no model, no Docker, no API): a task ships a recorded
tool-call trace plus an oracle; each hook event is fed to the real `tz-guard.py` under an arm's env/config; we measure the tokens the model
WOULD see (MEASURED from bytes/4 + hook text) and whether the task still passes. Real `claude -p` runs stay in tzab.py as the optional
paid confirm layer; Harbor/Terminal-Bench stays an optional command emitter. Statistics (mean, stdev, bootstrap CI, paired deltas, flips) are
ported from the TokenEconomizer compare script (MIT) and the fast-anything Stats struct (MIT).

## 1. microsoft/TokenEconomizer
URL https://github.com/microsoft/TokenEconomizer | MIT (LICENSE line 1 "MIT License", "Copyright (c) 2026 Microsoft"; SPDX MIT, main, pushed 2026-11-24) | status SELECTED (B selective port, NOTICE needed).
Files read: experiments/README.md; experiments/scripts/compare_arms.py (171 lines); experiments/scripts/sweep_plan.py; experiments/te_bench/arms.py:25-55;
experiments/workloads/swebench.json; experiments/tests/test_answer_key_guard.py; tokeneconomizer/pricing.py:250-264; tokeneconomizer/ledger.py:33-41.
Capabilities:
- Arms registry with a stated canonical order (`ARM_ORDER`, arms.py:29-50) and an import-time check that no arm is missing/unknown (arms.py:43-48). Arms include
  baseline, mechanism-alone arms (inject-only, untool-only, spiral-only), combined (trimech), and external baselines (rtk, serena, repomap, trimech-rtk). That is exactly
  "off / each alone / combined / combined + other tool".
- sweep_plan.py: matrix = arms x repos x seeds; `--format cells` (one `arm<TAB>repo<TAB>seed` per line) and `--format estimate` (task-runs, wall, dollars) BEFORE any run; rates declared and printed.
- compare_arms.py: per-task `row.json` (latest run dir per instance wins, lines 32-50); cost = `pricing.effective_tokens(row) + ledger.overhead(row)` (cache-aware, mechanism overhead charged to the arm);
  pairs by instance, drops unpaired and `usage_incomplete` rows and prints them; prints resolved counts, mean/median/pooled effective tokens, mean steps, per-task paired delta (mean, median, "arm cheaper on k/n"),
  overhead total, resolve FLIPS lost/won (lines 100-120), injection telemetry split with-prefix vs without; `--json` writes everything. Warns when agent/model/effort/endpoint/cli differ between cells (describe(), line 57).
- Answer-key guard (test_answer_key_guard.py): benchmark answers must not be fetchable by ANY arm incl. baseline; corpus of abusive vs legitimate calls with "0 false positives / 0 misses" claim -> template for TZ false-positive corpora.
- Row fields used: instance, resolved(bool), agent, model, effort, cli_version, num_turns, input_tokens, cache_read_input_tokens, cache_creation_input_tokens, output_tokens, tokens_total, overhead keys.
TZ overlap: tzbench.compare (bin/tzbench.py:66-77) does means only over chat logs; tzbench.quality (79-102) does pass rate + tokens-per-pass, no stdev/CI/pairing/flips; tzab.plan (tzab.py:125-142) is a trial/cost plan for 2 arms only; no arm registry, no tasks dir.
Decision: B for compare_arms.py logic (paired delta, flips, unpaired exclusion, effective tokens) and sweep_plan.py cell enumeration; C (rebuild) for arm registry (TZ arms differ). Do not take the SWE-bench Docker harness (te_harness/) - D.
Parity examples (behaviour to test): (1) baseline rows {a:100,b:200}, arm {a:80,b:220}: deltas -20%, +10%, mean -5%, median -5%, arm cheaper 1/2. (2) task only in arm -> listed "unpaired", excluded.
(3) baseline resolved a, arm not -> flips_lost=[a]. (4) row without usage -> excluded as usage_incomplete. (5) overhead 30 added to arm cost: arm 80+30=110 -> delta +10%.
Conflicts: none; replaces tzbench.compare's bare means.

## 2. SWE-bench/SWE-bench
MIT (SPDX MIT, main, pushed 2026-09-18); status REVIEWED, decision D (reference only; ledger row already REJECTED for Docker use - keep).
Files: docs/guides/evaluation.md, docs/assets/evaluation.md, swebench/harness/reporting.py:36-125.
Useful format ideas (not code): predictions JSONL {instance_id, model_name_or_path, model_patch}; report JSON with id lists completed/resolved/unresolved/error/incomplete/empty_patch + infra_failure and ambiguous_failure
(reporting.py:36-108, failures classified but kept in the denominator). TZ should copy the CLASSIFICATION: pass | fail | error(harness) | incomplete | empty. An infra error must never count as "TZ broke it".
Task = repo at base commit + problem statement + FAIL_TO_PASS and PASS_TO_PASS test lists. PASS_TO_PASS is the regression guard; TZ's "false positive" check maps to it (see 6).
Parity: report with resolved={a}, unresolved={b}, error={c} -> resolved rate = 1/3 (denominator includes error).

## 3. laude-institute/terminal-bench
Apache-2.0 (SPDX; last push 2026-07-11, superseded by harbor); status REVIEWED, D (format reference).
Files: original-tasks/hello-world/{task.yaml, run-tests.sh, solution.sh, tests/, Dockerfile, docker-compose.yaml}.
task.yaml keys seen: instruction (block text), author_*, difficulty, category, tags, parser_name: pytest, max_agent_timeout_sec 900, max_test_timeout_sec 180, run_tests_in_same_shell.
run-tests.sh bootstraps uv+pytest then runs tests/; per-test results parsed (pytest). solution.sh = oracle. A canary GUID line is placed on top of every file so benchmark data stays out of training corpora (copy the idea).
Offline TZ mapping: instruction -> prompt.md; run-tests.sh -> test.sh (no apt/curl; stdlib unittest/pytest only); solution.sh -> oracle.sh; timeouts -> per-task `timeout_sec`.

## 4. laude-institute/harbor
Apache-2.0 (SPDX; main; pushed 2026-11-24); status SELECTED as optional adapter (existing tzharbor.py kept), format adopted.
Files: docs-mintlify/tasks/overview.mdx, verifier.mdx; (instruction.mdx, solution.mdx, configuration.mdx, results/ exist, not all read).
Task layout (overview.mdx): `instruction.md`, `task.toml`, `environment/` (Dockerfile), `solution/solve.sh`, `tests/test.sh`. Verifier writes `/logs/verifier/reward.txt` (single number, usually 1/0) or `reward.json`
(labelled numeric metrics; json wins if both). Trial = one attempt: start env -> agent -> verifier -> reward + trajectory; rewards aggregate across the eval. Harbor trial view shows reward, cost, tokens, timing.
DECISION: TZ task dir adopts the Harbor layout so a TZ task can be run by Harbor unchanged (environment/ optional, absent offline). Reward = `reward.json` {"passed":1,"fp":0,...} or `reward.txt`.
TZ overlap: bin/tzharbor.py (21 lines) only prints two `harbor run` commands; correct to keep (nothing invented). Needs: `-n` flag meaning verified (ledger notes tzharbor.py:10 uses -n); add `--results-dir` to import Harbor result JSON into the same matrix schema (section 7).

## 5. alexgreensh/token-optimizer (comprehension check - IDEA ONLY)
LICENSE is PolyForm Noncommercial 1.0.0 (+ LICENSE-SMALL-BUSINESS.md); GitHub SPDX NOASSERTION. -> E for code, **D idea only; never copy code or wording**. status REVIEWED.
Files read: CONTROLLED-A-B-BENCHMARK.md (head). Ideas (describe, rebuild independently):
- 20 runs per side, interleaved, 1 warm-up per side discarded; tokens read from Claude's own transcript, de-duplicated by message id (TZ already does that: tzab.py:89-95 last usage per id).
- Each mechanism measured IN ISOLATION on a workload built to exercise it; do not publish a blended "X% per session" number.
- Comprehension (no-harm) check: ask a question whose answer sits in the compressed region; a saving that lost the answer is discarded. TZ rebuild: each task may carry `probe` = {question, answer_regex}; scripted agent "answers" by regex-searching what the arm showed it; fail if the needle was trimmed away without a recoverable `tz recall` pointer.
- Quarantine runs that did not do equal work before comparing. TZ rebuild: `work_equal` check = same set of oracle steps executed.
- Report floor vs not-measured list (routing, cache-drop avoidance); TZ already has the "Not measured" list in BENCHMARK-METHOD.md.

## 6. EL4CTEO/fast-anything (replay-equivalence method)
MIT (SPDX MIT, pushed 2026-11-24); status SELECTED for method (B for `Stats` shape, C rebuild in Python).
Files: src/bench.rs lines 1-60; README.md command table (`verify` = replays every recorded call; `bench` = times original vs port, interleaved).
- Method: record real calls once, replay each against ORIGINAL and PORT, byte-compare outputs; `BenchResult.output_diff` keeps the FIRST differing line. Interleaved runs so drift hits both arms equally.
- `Stats{median, mean, min, max, stddev}` (population stddev, divide by n).
TZ mapping: replay-equivalence = for every recorded tool call, the arm's hook output must equal the baseline's EXCEPT where the arm is allowed to trim; the diff is classified:
  (a) identical, (b) trimmed with recall pointer (allowed), (c) trimmed without pointer (information loss = FAIL), (d) deny/ask on a call the oracle needs (FALSE POSITIVE = FAIL).
Parity: stats of [1,2,3,4] -> mean 2.5, median 2.5, min 1, max 4, stddev(pop)=1.118; empty list -> all zeros; `output_diff` = first differing line or null.

## 7. The offline matrix benchmark - specification
### 7.1 Task format (Harbor-compatible, stdlib only), `bench-tasks/<id>/`
```
task.toml        id, category, difficulty, timeout_sec, seed, canary="tz-bench-canary <uuid>", tags
instruction.md   the prompt a real agent would get (used only by the optional paid layer)
setup/           fixture repo files copied to a temp dir per trial (no network, no installs)
trace.jsonl      scripted agent: one tool call per line {i, tool, input, needed:bool, why}; "needed" = oracle requires it
tests/test.sh    exit 0 iff end state is correct; stdlib python3 only; writes reward.json
solution/solve.sh  oracle: produces the end state directly (proves test.sh is satisfiable)
probe.json       optional {question, answer_regex, where: call index} comprehension check
fp_corpus.jsonl  optional legit calls that must NOT be denied (from real chats), see 7.5
```
Replay executes each trace call for real inside the temp dir (read/grep/edit/bash allowlist), builds the PreToolUse/PostToolUse hook JSON, pipes it to `bin/tz-guard.py` with the arm env, applies the hook's decision
(deny -> call skipped and counted; trimmed output -> replaced), then runs tests/test.sh. Hook stdout injected text counts as tokens the model sees.
Starter set: 6 tasks - dup-read (read same 20 KB file 5x), noisy-build (500-line log with 1 error), big-grep, destructive-command-near-miss (`rm -rf build/` legit vs `rm -rf ~`), stuck-loop (3 identical failing calls), long-chat compaction (plan_reinject).

### 7.2 Arm matrix (explicit, written to `arms.json`, arm order fixed like ARM_ORDER)
Each arm = {mode, features:{...}, env:{TZ_*}} materialised as a throwaway CLAUDE_CONFIG_DIR/config.json + env TZ_FEAT_<NAME>.
Controls available today (tzlib.py:21-56): `mode` in off|lite|full|ultra; features cache_ttl_auto, dup_skeleton, safety_net, stuck_detect, plan_reinject via env `TZ_FEAT_<NAME>=0/1` > config `features` > default; `mode off` turns every feature off.
| arm id | definition |
|---|---|
| `off` | mode=off (no TZ behaviour; hook still invoked so latency counted) |
| `tz20` | frozen 2.0 behaviour: mode=full with all v2.1 FEATURES=0 (the reference arm for "what is new") |
| `f:<name>` | tz20 + exactly one feature on, for each name in tzlib.FEATURES (and later v2.1 additions); one arm per feature |
| `g:<group>` | groups defined in `bench-tasks/groups.json`, e.g. `g:read` = dup_skeleton+read decisions, `g:output` = trim+recall, `g:safety` = safety_net+stuck_detect, `g:memory` = handoff+plan_reinject |
| `all` | mode=full, every feature=1 |
| `all-minus:<name>` | all on except one (leave-one-out; finds the feature hurting the whole) |
| `all-minus-conflicts` | all on minus the set in `conflicts.json` (pairs found by the leave-one-out arms where `all` is worse than best subset) |
| `ultra`, `lite` | optional mode arms |
Count for 5 features + 4 groups: off, tz20, 5 f:, 4 g:, all, 5 all-minus, all-minus-conflicts = 18 arms; offline cost per trial is milliseconds-seconds, so 18 arms x 6 tasks x 10 trials = 1080 replays is fine.
External-tool arms (rtk, serena, repomap, as in TokenEconomizer arms) are allowed as `arms.json` entries with an `env`/`pre-command` hook; not required.

### 7.3 Trials and variance offline
A scripted agent is deterministic, so variance must be injected honestly, not faked: per trial `seed` perturbs (a) trace ORDER of independent reads (permutation within `shuffle_groups`), (b) which of N equivalent fixture
variants is used (file sizes +-20% via seed), (c) cache TTL phase (arm run at t0 vs t0+5 min virtual clock -> tests cache_ttl_auto), (d) hook latency measured for real. Report "synthetic variance" and say so; real-model variance only comes from the optional paid layer (tzab).
Default `--trials 10`, interleave arms round-robin with the seed shared across arms (paired by (task, seed)), 1 warm-up trial discarded (token-optimizer idea).

### 7.4 Result JSON schema (`results/<run-id>/<arm>/<task>/seed<k>/row.json`, mirrors TokenEconomizer row + Harbor reward)
```
{"schema":"tz-bench/1","run_id","arm","task","seed","trial",
 "status":"ok|error|incomplete|empty",          // SWE-bench classes; error/incomplete never counted as TZ failure
 "passed":true,"reward":{"passed":1,"probe":1,"fp":0,"work_equal":1},
 "tokens":{"input":0,"output":0,"cache_read":0,"cache_write":0,"hook_text":0,"trimmed_saved":0,"recall_refetch":0,"overhead":0},
 "effective_tokens":0,"turns":0,"calls":0,"denied":0,"denied_needed":0,   // denied_needed>0 => false positive
 "diff":{"identical":0,"trimmed_with_pointer":0,"trimmed_no_pointer":0,"first_diff":null},
 "latency_ms":{"hook_mean":0,"hook_p95":0},
 "measured":"MEASURED|EST","cli_version":"","config_hash":""}
```
effective_tokens = input + output + 1.25*cache_write + 0.1*cache_read + overhead (TZ's own replay weights, tzbench/BENCHMARK-METHOD) - keep identical to tzreplay so numbers agree.
Summary file `summary.json` + `summary.md`: per (task, arm) and pooled per arm.

### 7.5 Statistics reported
Per (arm, task): n, pass_rate, mean, stdev (sample, n-1; also population stdev to match fast-anything), median, min, max, tokens_per_pass.
Per arm vs a chosen baseline (default `off`; also vs `tz20`): paired by (task, seed): delta% per pair, mean and median delta, percentile-bootstrap 95% CI of the mean delta (10,000 resamples, fixed RNG seed, stdlib `random`),
sign count "arm cheaper on k/n", resolve flips lost/won, pass-rate difference with Wilson 95% interval, McNemar exact p on flips (stdlib `math.comb`). Pooled arm score = geometric mean of per-task ratios (so large tasks do not dominate).
Verdict per arm: WIN (CI upper < 0 and no pass-rate drop and fp=0), LOSS (CI lower > 0 or any lost flip), NEUTRAL otherwise; "PROVEN" only with n>=10 paired and CI excluding 0 (stricter than today's 5).
False positives: `fp_rate = tasks with denied_needed>0 / tasks`, plus the fp_corpus replay (legit calls from real chats, TokenEconomizer answer-key style): any deny/ask on a legit call is a reported FP; target 0.
Always print the not-measured list (answer quality with a real model, turn count, routing). Never hide a failed or errored trial.

### 7.6 What to add to bin/tzab.py (exact)
Current: tzab.py has `usage_total`, `agg_recorded`, `agg_used`, `run_session` (one capped headless session, lines 52-122), `plan` (125-142, argparse --tasks --trials --cap --agg-cap --usd-per-mtok), `main` (145-158, single run).
tzab.py is 161 lines; keep it as the PAID single-session runner and add, in a NEW module `bin/tzmatrix.py` (<=250 lines, stdlib), imported by tzab/tzbench, plus small hooks in tzab.py:
1. `tzmatrix.load_arms(path)` / `write_config_dir(arm, tmp)` -> builds a CLAUDE_CONFIG_DIR + env from an arm (mode, features). tzab.main gains `--arm NAME --arms-file arms.json` that calls it instead of requiring a prebuilt `--config` (make `--config` optional when `--arm` given).
2. `tzab.py plan` gains `--arms N|--arms-file`, `--matrix` (print cells arm x task x seed like sweep_plan `--format cells`) and computes `sessions = arms*tasks*trials` (today hard-coded `* 2`, line 133) and the ORDER as a seeded round-robin over arms (today alternating 2 values, line 134). Keep the aggregate cap 5M (line 10) untouched.
3. New subcommand `tzab.py matrix --tasks bench-tasks --arms arms.json --trials 10 --out results/ [--offline|--live]` (default `--offline` = scripted replay; `--live` = call `run_session` per cell, requires the owner OK printed by plan). Runs cells in interleaved order, writes row.json per 7.4, resumable (skip existing row.json; latest dir wins like compare_arms.py).
4. New subcommand `tzab.py report RESULTS_DIR [--baseline off] [--json]` -> 7.5 statistics (port compare_arms.py logic, MIT, NOTICE in file header; `tzbench.quality` kept for back-compat and re-implemented on top of it).
5. In `run_session`'s return dict add `parts` already present; add `hook_ms` and `status` mapping to the 7.4 status classes; put the trial dict into row.json (so paid and offline rows share one schema).
6. tzharbor.py: add `--results-dir` import (Harbor reward.txt/json + token fields -> row.json) so Harbor runs feed the same `report`. Docker stays optional and unused offline.
7. Tests (`tests/test_matrix.py`): stats parity cases from sections 1 and 6; arm builder; fp corpus; determinism (same seed -> identical rows); 18-arm matrix completes offline in under 60 s.

## 8. Conflicts / risks
- Scripted-agent results are MEASURED for the hook's byte/token effect but not for model behaviour: label `measured=MEASURED` for bytes, and never claim end-to-end savings from it (BENCHMARK-METHOD.md rule). Real-model confirm stays in `tzab live` + `tzbench quality`.
- Cache effect: a removed block is carried by every later reply (C/4 x (1.25+0.1(k-1)), tzreplay); reuse that formula, do not recompute differently.
- Feature interaction: `mode off` forces all features off even if TZ_FEAT_x=1 (tzlib.py:48-49), so the `off` arm is clean; `f:<name>` arms must start from mode=full.
- token-optimizer text is PolyForm Noncommercial: do not paste any of its wording/numbers into TZ docs.

## 9. Ranked build list (value per re-sent-context token)
1. Arm matrix + `tzab.py matrix --offline` + row.json (7.2, 7.4): lets every other group's feature be measured (blocking for all).
2. `tzab.py report` statistics with paired delta, bootstrap CI, flips, fp (7.5): turns anecdotes into a verdict; port from TokenEconomizer.
3. FP corpus replay + needed-call deny check (7.1, 7.5): protects quality; cheap and catches the worst regressions.
4. 6 starter tasks in Harbor layout with oracle + test.sh (7.1).
5. Leave-one-out and `all-minus-conflicts` arms + conflicts.json (7.2).
6. Comprehension probe per task (section 5 idea, own implementation).
7. tzharbor `--results-dir` import (optional, Docker/paid).
8. `tzab plan` matrix cell listing and cost (7.6 item 2).
