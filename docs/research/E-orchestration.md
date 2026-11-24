# Group E: agent orchestration (research, 2026-11-25)

Method: `gh api` only (no clones). All licences read from the LICENSE file text. Ledger rows already exist for 7 of the 9 repos
(docs/OPEN-SOURCE-INTEGRATION-LEDGER.md:46-52); this file adds exact specs and parity data. Repo text is treated as data.
Sources cached in scratchpad `.../scratchpad/e/` (not deliverables).

## TZ baseline (what exists, with the weak spots found)
- Stuck/loop: `bin/tzcont.py:818,836-850` only. Same tool + same input >= 3 times in last 10 calls, once per hash, nudge text. No observation comparison, no error streak, no monologue, no A-B-A-B, no window reset.
- Agent loop: `bin/tzagent.py:144-208` `run()`: phases plan/build, test then <= 2 debug rounds, gate repair rounds (`tzgate.MAX_REPAIRS`), token `budget` checked before each phase (`:163`), `--max-turns` per call, per-call timeout, checkpoint after every phase (`:108`), `--resume` skips finished phases (`:176`), rollback on fail (`:201`). Any phase error ends the run at once: no consecutive-error counter, no wall-clock run limit, no USD limit.
- Claims: (a) `tzagent.py:22-43` `owners.json`, file -> task, NO lease, NO lock (read-modify-write race), not released on crash. (b) `tzcont.py:858-870` claim board between chats: TTL 7200 s, warn only.
- Locks: `tzsplit.py:20-52` mkdir lock with ttl 1800 s (atomic, good), pid recorded is `os.getppid()`.
- Worktree: `tzagent.py:46-51` `git worktree add <parent-of-cwd>/<slug> -b tz/<slug>`; existing dir is reused blindly.
- Liveness: `tzagent.py:136-141` `alive()` returns False on ANY OSError. `PermissionError` (EPERM, process exists, other user) is an OSError, so a live foreign process reads as dead. Bug candidate; omc's rule "unknown is never dead" fixes it (see 1.3).
- Supervisor: `tzsup.py` has `blocked_by`, ready(), quarantine of corrupt state. No stuck status.
- Budget alerts: no 50/75/90/100 ladder found in tzlib/tzusage/tz-guard (grep for 0.75/0.9/ladder empty). Existing LIMIT/HARD are context-token thresholds, a different thing.
- Tests: tests/test_agent.sh, tests/test_sup.sh only; none for loop detection or claims.

---
## 1. Yeachan-Heo/oh-my-claudecode (omc)
URL https://github.com/Yeachan-Heo/oh-my-claudecode | licence MIT (LICENSE: "MIT License, Copyright (c) 2025 Yeachan Heo"); commit 9f2a74b6b6.
Files inspected: src/team/recovery-saga.ts (133 lines), src/team/state/tasks.ts (claimTask :177-250, renew :428-470, requeueRecoveredTask :600), src/team/task-recovery-checkpoint.ts, src/team/git-worktree.ts, tests src/team/__tests__/recovery-saga.test.ts, task-claim-renewal.test.ts.
Decision: B for the claim-lease + checkpoint-integrity model (TS to Python, small, MIT, needs NOTICE line); C (rebuild, ideas only) for saga ordering; D for the tmux/pane machinery (345 KB runtime-v2.ts, tmux-bound). Status REVIEWED -> SELECTED (1.1, 1.2, 1.3).

### 1.1 Task claim with lease (duplicate-work prevention) , TZ target `bin/tzagent.py claim/release` + new `claims.json`
Semantics (tasks.ts:37,177-232): `TASK_CLAIM_LEASE_MS = 15 min`. claimTask(task_id, worker, expected_version|None):
1. worker must exist, task must exist. 2. all `depends_on`/`blocked_by` tasks must be `completed` else `blocked_dependency` (checked before AND after taking the lock). 3. Under a per-task lock: if `expected_version` given and != task.version -> `claim_conflict`. 4. terminal status -> `already_terminal`. 5. `in_progress` -> `claim_conflict`. 6. a recovery reservation present -> `claim_conflict`. 7. `pending|blocked` with a claim, or an owner other than caller -> `claim_conflict`. 8. Else write status=in_progress, owner, claim={owner, token=uuid4, leased_until=now+15min}, version+1, atomically (tmp+rename).
Renew (tasks.ts:428-462): only the holder with the matching token; never renews an expired lease (`lease_expired`); not for terminal tasks; not while a recovery reservation exists; version unchanged by renewal (tests: "preserves version-bound checkpoints across renewals").
Transition/release: needs the token and an unexpired lease, else `lease_expired`.
TZ spec: `claim(key, owner, ttl=900) -> {ok, token} | {error}` using `os.mkdir`/`O_EXCL` lock dir (as tzsplit.lock) around read-modify-write of one JSON; `renew(key, token)`; `release(key, token)`; expired lease is reclaimable by anyone (this is the dead-worker recovery). Replace file->task map by `{key: {owner, token, leased_until, version}}` where key = sha1(task text)[:12] (task level) and per-file keys keep the same lease. Edge cases: expired renew refused; wrong token refused; double claim same owner still conflict (omc rule 5), terminal refused; clock only `time.time()`.
Parity examples (from task-claim-renewal.test.ts):
- claim at t0, renew at lease-60 s with right token -> ok, new leased_until > old; transition to completed at lease+60 s with the original token -> ok (renewal carried it).
- renew with lease already expired -> `lease_expired`, nothing written.
- renew when task is not in_progress or is terminal (even with stale claim attached) -> rejected.
- renew when lock denied -> `claim_conflict`, nothing written.
- claim of a task whose dependency is not completed -> `blocked_dependency` listing the incomplete ids.
Conflicts: TZ `tzcont` claim board (per-file, warn-only, 7200 s) is a separate advisory layer; keep it, make agent claims authoritative. Humanlayer's O_EXCL marker (3.2) is the lock primitive.

### 1.2 Checkpoint integrity (`task-recovery-checkpoint.ts`) , TZ target `tzagent.checkpoint/load_run`
Rules: checkpoint = {schema_version 1, task_id, sequence >0 int, task_version >0, claim_token, resume_payload, resume_payload_hash = sha256(payload), updated_at}. Payload max 64 KiB (`MAX_TASK_RECOVERY_CHECKPOINT_BYTES`). Files immutable per sequence (`.../<sequence>.json`) plus a `latest` pointer updated only if `sequence >= existing`. Re-publishing the same sequence with identical content = `replayed: true` (idempotent); different content = `publication_conflict`. On load, ANY malformed file in the directory -> whole selection `malformed` (fail closed). Hash mismatch -> invalid.
TZ spec: add `sha` over json of `rows` to checkpoint(); `load_run` rejects (returns None, quarantines like tzsup `_quarantine`) on mismatch; cap size 64 KiB (rows notes are already truncated). Ex: tamper one row note -> load_run returns None and file moved to `.corrupt`; same rows re-saved -> identical bytes (idempotent).

### 1.3 Recovery saga ordering and "unknown is not dead" , TZ target `tzagent --resume`
recovery-saga.ts:53-133. Order (asserted by test): `liveness, list owned in-progress tasks, validate checkpoints, requeue (reserve) each task, spawn replacement, persist, activate, adopt all continuations, repair services, run`. Rules: liveness `unknown` -> fail `worker_liveness_unknown`, nothing else called (test "never treats unknown pane liveness as a dead worker": order == ['liveness']). Liveness alive and not a committed replacement -> `already_running`, nothing changed. Any checkpoint invalid -> fail BEFORE any transition. Requeue failure on task 2 -> failed with `reservationsWritten:true`; replay with the same recovery id completes (idempotent). Only the uncommitted spawn attempt is killed if persistence throws; a committed replacement is never killed. An idle dead worker (no tasks) skips checkpoint/adopt (`order = liveness,list,spawn,persist,activate,repair,run:idle`).
TZ spec: `liveness(pid) -> 'alive'|'dead'|'unknown'`: `os.kill(pid,0)` ok -> alive; ProcessLookupError -> dead; PermissionError -> alive (fixes `alive()`); pid==0/missing -> unknown. `--resume` on unknown refuses with message; on alive refuses ("already running"). Resume validates checkpoint first (1.2), then continues; idempotent on repeat.
Parity: same four assertions (unknown -> no state change; alive -> no change; dead + valid -> proceeds; dead + corrupt checkpoint -> fails before any write).
Decision for the saga itself: C minimal. TZ has one process, not panes, so the 10-step saga collapses to liveness -> validate -> resume.

### 1.4 Worktree isolation (`git-worktree.ts`) , TZ target `tzagent.make_worktree`
Behaviours (MIT, B-able): modes disabled/detached/named; branch `omc-team/{team}/{worker}`; leader tree dirty -> refuse to start (`leader_worktree_dirty`); existing worktree reused ONLY if clean and branch matches, else `worktree_dirty` / `worktree_mismatch` thrown, never deleted; removal never `--force` on dirty; commit counts as safe only if reachable from a non-worker branch/tag/remote (`--exclude=omc-team/*`).
TZ gaps: no leader-dirty check, blind reuse, sibling-dir path (collides across repos with same slug), no safe removal. Spec: path = `<TZ state>/worktrees/<repo-name>-<sha1(repo abs path)[:6]>/<slug>`; on existing path check `git -C p branch --show-current == tz/<slug>` else raise; dirty -> raise `worktree_dirty`, never delete; record base SHA in meta. Parity: reuse clean matching tree -> reused:true; dirty -> error code worktree_dirty and files intact; wrong branch -> worktree_mismatch.

---
## 2. ruvnet/ruflo
URL https://github.com/ruvnet/ruflo | MIT ("Copyright (c) 2024-2026 ruvnet") | commit 99aeeac722.
Files inspected: plugins/ruflo-cost-tracker/scripts/budget.mjs, plugins/ruflo-mods/hooks/cost/budget.ts (full), tree grep for stuck/claims/budget (v3/@claude-flow/claims/src/application/{claim-service,work-stealing-service,load-balancer}.ts listed, not read in depth; see ledger row 47).
Decision: B for the budget ladder (tiny, MIT; 20 lines, NOTICE); D for claims/work-stealing (needs npx memory backend); E for the rest (monolith, optional deps, marketing README). Status SELECTED (ladder) / REVIEWED.
### 2.1 Budget alert ladder , TZ target `bin/tzusage.py` (or tzlib) + tz-guard hook
Spec (budget.ts): levels by utilization u = spent/budget: u>=1.0 HARD_STOP, >=0.9 CRITICAL, >=0.75 WARNING, >=0.5 INFO, else OK. `isRaised(prev,next)` true only when next rank is strictly higher (OK0 INFO1 WARNING2 CRITICAL3 HARD_STOP4): tell the user once per rung, never on the same or lower rung. `budgetOf(x)`: accepts number or numeric string; non-finite or <=0 means budget OFF (never a zero budget that halts at once).
Parity (derived from the code, its own parity test reads thresholds from budget.mjs): u=0.49 OK; 0.5 INFO; 0.74 INFO; 0.75 WARNING; 0.9 CRITICAL; 1.0 HARD_STOP; budgetOf('0')=undefined; budgetOf('12.5')=12.5; budgetOf('abc')=undefined; isRaised(WARNING,WARNING)=false, isRaised(INFO,CRITICAL)=true.
TZ use: `tz agent --budget TOK` already hard-stops at 100% (`tzagent.py:163`); add the ladder to the per-run budget and to the weekly usage budget, message once per rung. Conflict: none; do not take ruflo's memory store.

---
## 3. OpenHands/software-agent-sdk
URL https://github.com/OpenHands/software-agent-sdk | MIT ("Copyright (c) 2026 OpenHands contributors") | commit 289299ef2d.
Files: openhands-sdk/openhands/sdk/conversation/stuck_detector.py (539 lines), conversation/types.py (StuckDetectionThresholds), tests/cross/test_stuck_detector.py (624), tests/cross/test_stuck_detector_config.py, tests/sdk/conversation/local/test_stuck_detector_nudge.py.
Decision: B/C. Logic is ~150 lines of pure comparison and MIT, but it depends on the SDK's event classes; port the algorithm to TZ transcript records (C, rebuild with attribution in NOTICE). TZ target: new `bin/tzstuck.py` (pure function, stdlib), called from `tzcont.tool_advice` (PostToolUse) and from `tzagent` stream loop. Status SELECTED, highest-value item of this group.

### 3.1 Spec (thresholds from types.py:240-251)
Defaults: action_observation=4, action_error=3, monologue=3, alternating_pattern=6 (all >=1). Window: last 20 events (`MAX_EVENTS_TO_SCAN...=20`) AFTER the last user message; after a resume only events after the resume marker count (`mark_resumed`).
Early out: fewer events than min(action_observation, action_error, monologue)=3 -> not stuck.
Event equality (`_event_eq`): same type; action = same source + tool_name + action payload (+ thought for valid actions); ids, tool_call_id, response ids ignored; observation = same source + tool_name + observation content; error = same text; message = same source + content. Invalid calls (no parsed action) compare by tool_name + validated arguments with `security_risk`/`summary` keys dropped.
Scenarios (checked in this order, any true -> stuck):
1. Repeat action+observation: take the latest `N=action_observation` actions and N observations; stuck if all N actions equal the newest AND all N observations equal the newest. Needs >=N of each. Skipped if invalid calls among them share one LLM response (parallel calls are one attempt).
2. Repeat action+error: streak = number of trailing LLM responses whose action (same tool, equal action or, for invalid calls, same validation-error types/locations with list indexes normalised to 0) each got an AgentError. Parallel calls count as ONE response. Stuck iff streak > action_error (4th failure). Nudge when streak == action_error (3rd): text names the tool and the error; fired once per streak (remember the error event id so a frozen streak does not re-nudge).
3. Monologue: count consecutive agent messages from the end; condensation events are skipped; an action/observation breaks it; a user message breaks it. Stuck if count >= monologue (3). NOTE: content is NOT compared, three agent messages in a row suffice.
4. Alternating: only if len(events) >= alternating_pattern (6). Take latest 6 actions and 6 observations; stuck if actions[i]==actions[i+2] for i in 0..3 AND observations[i]==observations[i+2] for i in 0..3 (pattern A,B,A,B,A,B).
5. Context-window error loop: stub, returns False (blocked by upstream issue 282). Do not port.
### 3.2 Parity examples (from the original tests)
- test_history_too_short: 0-2 events -> False.
- 3 identical (ls, same output) pairs after a user message -> False (`...not_stuck_less_than_4_repeats`); 4 identical pairs -> True (`..._stuck`).
- Action-error: 2 identical failing pairs (`invalid_command`, "Command 'invalid_command' not found") -> not stuck, nudge None; 3rd -> not stuck, nudge not None and contains "terminal" and the error text; 4th -> stuck True, nudge None.
- Monologue: user msg then 3 agent messages ("I'm thinking... 0/1/2") -> True.
- test_reset_after_user_message: 4 identical pairs -> True; append a user message -> False; one more different pair (pwd) -> still False.
- Window: only the latest 20 events matter (`test_is_stuck_uses_only_recent_event_window`): a loop older than 20 events with different recent events -> False; a loop with no user message at all still detects (`..._without_recent_user_message...`) and with fewer than 20 events too.
- Config: thresholds {action_observation:8, action_error:6, monologue:10} -> alternating stays 6.
- Nudge tests (test_stuck_detector_nudge.py): nudge delivered before stuck; after the model self-corrects the run continues; a frozen streak does not re-nudge.
### 3.3 TZ mapping and conflict
TZ events = transcript tool_use + tool_result pairs; action key = (tool, canonical json of input), observation key = sha1 of result text (normalised: strip timestamps/pids by regex before hashing, TZ addition, flag as divergence from original). `tzcont` rule (same input 3x in 10) becomes scenario "repeat action" only; keep it as cheap fallback when results are unavailable. Add (a) obs-equality (N=4), (b) error streak 3 nudge / 4 stuck using `is_error` flags, (c) monologue = 3 assistant turns without tool_use, (d) alternating 6, (e) window reset at last user prompt. Existing LOOP_N=3 nudge at the 3rd identical call is stricter than OpenHands (which waits for 4 with identical observation); keep the earlier nudge, but only the 4th-with-same-observation as "stop" level. Output: nudge string at warn level, `stuck` boolean in tzagent -> status `stuck`, run ends and rolls back like `error`.

---
## 4. SWE-agent/mini-swe-agent
URL https://github.com/SWE-agent/mini-swe-agent | MIT (LICENSE.md "Copyright (c) 2025 Kilian A. Lieret and Carlos E. Jimenez") | commit 04d809ceab.
Files: src/minisweagent/agents/default.py (190 lines), tests/agents/test_default.py. Ledger row 49 already adopted process-group kill (tzworkers.run_pg). Decision: C (rebuild, 30 lines; ideas MIT). TZ target `tzagent.run()`. Status SELECTED.
### 4.1 Limits and format-error spec (default.py:19-35,120-145,100-118)
AgentConfig: `step_limit=0` (0 = off), `cost_limit=3.0` USD (0 = off), `wall_time_limit_seconds=0` (off), `max_consecutive_format_errors=3` (0 = off).
query(): BEFORE each model call: if `0 < step_limit <= n_calls` or `0 < cost_limit <= cost` -> exit_status `LimitsExceeded` (note `<=`: "stop after exceeding" means reaching it); then if `0 < wall_time_limit <= elapsed` -> `TimeExceeded`. Only then `n_calls += 1`, call, add cost.
run loop: after each clean step `n_consecutive_format_errors = 0`. On FormatError: add the failed call's cost to total FIRST (it was billed), counter += 1; if `0 < max <= counter` -> append an exit message `RepeatedFormatError`, else append the error message so the model sees it and retries. Unhandled exception -> record exit message with traceback and re-raise. `save()` runs in `finally` every step (trajectory always on disk). Loop ends when last message role == `exit`.
### 4.2 Parity examples (test_default.py)
- step_limit=1 with 2 scripted outputs -> exit `LimitsExceeded`, `n_calls == 1`.
- cost_limit=0.5 with a model charging per call -> `LimitsExceeded` before the 2nd call.
- wall_time_limit_seconds=1 (slow first step) -> `TimeExceeded`, `n_calls == 1`.
- 5 scripted format errors, max_consecutive_format_errors=2 -> `RepeatedFormatError`, `n_calls == 2` (did not burn all 5).
- error, good, error, submit with max=2 -> counter resets on the good step, ends `Submitted`.
- format errors are billed: a model that bills then raises FormatError counts toward the cost limit (`test_format_errors_count_against_cost_limit`).
### 4.3 TZ overlap and gaps
Has: token budget checked before each phase, per-call timeout, per-phase `--max-turns`, checkpoint each phase. Missing: (1) wall-clock limit over the whole run (tzagent has only per-call timeout), (2) consecutive-failure limit with retry (any `error` ends run at once; transient host error costs the whole run), (3) step limit counting calls (phases are fixed so low value), (4) `0 = off` convention, (5) failed calls billed into `spent` (TZ does `spent += tok` for errors too, fine; add parity test). Spec: `--wall S`, `--max-errors N=2` (retry the same phase up to N-1 times when `err` is transient, e.g. nonzero exit with no edits; reset on success), exit statuses `budget|time|repeated_error|stuck|ok`. Conflict: none.

---
## 5. smtg-ai/claude-squad (AGPL, behaviour only, no code copied)
URL https://github.com/smtg-ai/claude-squad | AGPL-3.0 (LICENSE.md: "GNU AFFERO GENERAL PUBLIC LICENSE Version 3, 19 November 2007") | commit 070eb9387c. Files read: session/git/worktree.go, worktree_ops.go, session/instance.go (Pause :423-510), tests list. Decision: D/C: reference design, TZ rebuilds independently from this behaviour list. Status REVIEWED.
Observed behaviour (facts, not code):
- Worktrees live under the app config dir `worktrees/`, one directory per session named from the branch plus a nanosecond-time suffix, so two sessions never collide. Branch = configured prefix + sanitised session name.
- Base commit (HEAD at creation) is recorded for later diffing. If the branch pre-existed, a flag marks it so cleanup never deletes it.
- Setup first force-removes any stale worktree at the same path, then `worktree add -b branch path <head>`; for an existing branch, orphaned directory is removed first (test: `RemovesOrphanedDirectory`, `RecordsBaseCommit`).
- Pause: refuse if not started/already paused; if worktree is orphaned (missing path or .git) skip dirty check, delete leftover dir, `worktree prune`, set Paused; else if dirty, commit locally with message "[claudesquad] update from '<title>' on <date> (paused)" (abort pause on commit failure to avoid corrupt state), detach terminal, remove the worktree but KEEP the branch, prune. Resume re-adds the worktree for the kept branch.
- Cleanup of all: `worktree list --porcelain`, delete session branches, prune.
TZ lessons (independent rebuild, goes into 1.4 spec): unique suffix path outside the repo parent; record base SHA; "existing branch is never deleted" flag; pause = commit-then-remove-keep-branch (this gives a safe `tz agent --pause`; omc's refuse-if-dirty and claude-squad's commit-if-dirty are the two safe policies, choose commit on a `tz/` branch only); orphan detection + prune. Conflict: omc preserves dirty trees untouched, claude-squad commits them; TZ choice: preserve untouched on failure/rollback, commit only on explicit pause.

---
## 6. 23blocks-OS/ai-maestro
URL https://github.com/23blocks-OS/ai-maestro | MIT ("Copyright (c) 2025 Juan Pelaez / 23blocks") | commit ead48472b0. Files: lib/crash-restart.ts (full), tests/crash-restart.test.ts. Decision: C (pure function, 30 lines, rebuild; or B with NOTICE). Status SELECTED (low priority; TZ has no auto-restart yet).
### 6.1 Crash-restart decision with backoff , TZ target `tzsup.tick` / `tzagent --resume --auto`
`crashAction(input)` order: not at shell -> none (running); already failed -> none; no hook record ever -> none; last record status `ended` (quit on purpose) -> none; terminal active within `QUIET_MS=60 s` -> none (never interrupt a person); recent restarts = those within `WINDOW_MS=30 min`; if count >= `MAX_RESTARTS=6` -> `fail` (mark failed, notify once, stay down until a person starts it); else wait until `last + BACKOFF_MS[min(count,5)]` with `BACKOFF_MS=[0,30s,60s,120s,240s,300s]` -> `wait`; else `restart` and append now. At most 3 restarts per pass.
Parity (tests): base state -> restart; atShell false / ended / null record / failed -> none; lastActivity = now-59 s -> none; one restart 10 s ago -> wait; 40 s ago -> restart; six restarts in window -> fail; six restarts all 31 min old -> restart; pass of 5 crashed agents restarts 3 then 2; after fail, next pass returns [] (stays down) and notify called once.
TZ mapping: a killed `tz agent` run = `state=running` + dead pid (tzagent.py:108). tzsup tick could resume at most N times per 30 min with this backoff. Value is small until TZ runs unattended; rank 7.

---
## 7. humanlayer/humanlayer
URL https://github.com/humanlayer/humanlayer | Apache-2.0 (LICENSE file is the Apache 2.0 text; repo also has NOTICE) | commit fb899cd8cb. Files: apps/riptide-claude-code-plugin/hooks/mod.ts (:137-145,321-345), packages/session-sdk-sessions/src/claims.ts, apps/riptide-api/src/db/reject-pending-approvals.ts. Decision: B for claims.ts (20 lines, Apache needs NOTICE); C for the approval flow (backend-bound); E for the cloud stack. Status SELECTED (claims), REVIEWED (approvals).
### 7.1 Approval checkpoint flow (PermissionRequest hook)
Behaviour: the hook sends {sessionId, toolUseId, tool, input, agentId} to a server, then long-polls (15 s wait per poll) for an answer until one arrives or the hook is aborted (`signal.aborted`). Answers: `allow`, `deny` (message, optional `interrupt`), or `none`. Claude Code's own prompt stays visible meanwhile: first answer wins. Any error, abort, or "off" -> `none` -> pass through to the normal local prompt (fail-open to the human prompt, not fail-open to allow). tool_use id is recovered by matching tool name + stable-json input among running calls (same input first; a single running call of that tool matches). On shutdown/session end all pending approvals are bulk-rejected with a comment (one UPDATE).
TZ mapping: TZ is local and has no server, so build the offline subset: `tzpolicy` risky class (rm -r, force push, secrets path, > N files) -> PreToolUse `permissionDecision: "ask"` with TZ reason (host shows its own prompt), recorded in the run ledger as `approval requested/answered`; in `tz agent` (headless) a risky step without `--allow` ends the run with status `needs_approval` and a checkpoint, so `--resume --approve` continues. Parity from original: error or abort -> falls back to the local prompt (never auto-allow); deny carries message; pending approvals reject on stop. TZ today: PreToolUse deny only (tz-guard.py:199) with no `ask` path and no approval ledger.
### 7.2 Claim marker (duplicate-work prevention) , TZ target `tzagent.claim`, `tzsplit.lock`
claims.ts: `claim(dir, key)` = create file `dir/<key with non [\w.-] replaced by _>` with flag `wx` (O_EXCL), mode 0600, dir mode 0700; returns true if this process created it, false on EEXIST, other errors rethrown. `pruneClaims(dir, now)` removes markers older than 24 h (best effort). Purpose: several processes see the same event; first to create the marker runs it.
Parity: first claim(k) true, second claim(k) false; key "a/b c" -> file `a_b_c`; marker mtime 25 h old pruned, 23 h kept; unrelated OSError rethrown. TZ: use for per-task-key, per-message and per-hook-event dedupe (e.g. a fan-out of `tz agent` on the same task text; two chats receiving the same handoff). Compatible with 1.1 leases (marker is the cheap lock, JSON lease is the state).

---
## 8. HKUDS/CLI-Anything
URL https://github.com/HKUDS/CLI-Anything | Apache-2.0 (LICENSE = Apache 2.0 text) | commit 34f519533b. Contents: per-app CLI harness folders (blender, audacity, QGIS ...), plugin manifests (.claude-plugin, .cursor-plugin). Generates CLI wrappers around GUI software; no orchestration, stuck, budget or worktree logic. Decision: E (no TZ capability; unrelated to token saving). Status REJECTED. (Matches V2.1-PLAN.md:18 "Not used".)

## 9. ultraworkers/claw-code
URL https://github.com/ultraworkers/claw-code | **MIT** (LICENSE: "MIT License, Copyright (c) 2026 UltraWorkers and Claw Code contributors"), commit a5c2775e81. CORRECTS docs/V2.1-PLAN.md:19 ("claw-code (no licence)"): a LICENSE file with MIT text exists now. Re-check on release day; also note its README/PARITY.md claim to be a clean-room reimplementation of Claude Code, so provenance of individual files is unverified: treat code as B only after reading each file's header, prefer C.
Files seen: rust/crates/runtime/src/{recovery_recipes.rs (32 KB), stale_branch.rs, stale_base.rs, worker_boot.rs (89 KB), task_registry.rs, policy_engine.rs, permission_enforcer.rs}. Read: recovery_recipes.rs structure, stale_branch.rs enum/policy structure.
### 9.1 Recovery recipes with attempt ledger , TZ target `tzagent`/`tzgate`
Seven failure scenarios (trust_prompt_unresolved, prompt_misdelivery, stale_branch, compile_red_cross_crate, mcp_handshake_failure, partial_plugin_startup, provider_failure), each a recipe = ordered steps + `max_attempts` (all 1) + escalation policy (AlertHuman for 5, Abort for mcp handshake, LogAndContinue for partial plugin). Per-scenario attempt counter; at `attempts >= max` -> `EscalationRequired{reason}`; failure of step 1 escalates immediately; failure mid-way = `PartialRecovery{remaining}`; ledger entry records scenario, attempts_remaining, last command result; status report distinguishes not-attempted from exhausted. Tests: escalation_after_max_attempts_exceeded, partial_recovery_when_step_fails_midway, first_step_failure_escalates_immediately, recovery_status_report_distinguishes_not_attempted_from_exhausted.
TZ already has equivalent bounded repair (`tzgate.MAX_REPAIRS`, 2 debug rounds). Gap = a structured per-failure-kind ledger. Decision D (reference): one-attempt-then-escalate matches TZ's cost goal; add `status: exhausted|not_attempted` to ledger rows only.
### 9.2 Stale branch policy , TZ target `tzagent.make_worktree`
check_freshness(branch, main_ref) -> Fresh | Stale{behind, missing fixes} | Diverged{ahead, behind}; policy WarnOnly/Block/AutoRebase/AutoMergeForward maps freshness to action. Tests: fresh passes; fresh-and-ahead still Fresh; behind count + missing fix list; diverged detection. TZ spec: before `--worktree` start compute `git rev-list --left-right --count main...HEAD`; behind>0 -> warn (default), `--stale block` aborts. Rank low.

---
## Ranked build list (value per re-sent-context token, highest first)
Main saving logic: every wasted step re-sends the whole chat (cache reads ~276M tok/day), so ending a loop 1-3 steps earlier beats everything else.
1. **tzstuck.py: OpenHands detector** (section 3). Pure function, 5 scenarios, nudge-at-3/stuck-at-4 error streak, window reset. Saves whole looping tails; hook cost ~0 (stdlib, hash compare). Tests from 3.2.
2. **Run limits + consecutive-error counter + wall clock** (section 4). `--wall`, `--max-errors`, `0 = off`, billed failures counted. Small diff in `tzagent.run`; stops runaway headless runs.
3. **`alive()` fix + liveness tri-state + checkpoint hash** (1.2, 1.3). Bug today: EPERM treated as dead -> `--resume` could start a duplicate of a running run (double spend). 10 lines.
4. **Claim lease + O_EXCL lock** (1.1, 7.2). Replaces racy owners.json that never expires after a crash (file owned forever). Duplicate task-run prevention via sha1(task) key.
5. **Budget ladder 50/75/90/100 once per rung** (2.1). Cheap warning before HARD_STOP, tells the user at the right moment.
6. **Worktree safety: path, clean/branch check, leader-dirty, base SHA** (1.4, 5). Prevents silently reusing a wrong or dirty tree.
7. **Approval checkpoint `ask` + `needs_approval` run status** (7.1). Medium effort, depends on host hook support for `ask`; verify with a live hook test before relying on it.
8. **Crash-restart backoff for unattended resume** (6.1). Only when tzsup runs unattended.
9. Stale-branch warn (9.2), recovery ledger statuses (9.1): minor.
Rejected/reference only: CLI-Anything (E), ruflo claims/work-stealing and monolith (D/E), omc tmux saga machinery (D), claude-squad code (AGPL, behaviour list only), ai-maestro server stack.

## Notices to add (NOTICE file) when ported
OpenHands software-agent-sdk (MIT, algorithm), mini-swe-agent (MIT, limit semantics, already listed for run_pg), oh-my-claudecode (MIT, lease/checkpoint model), ruflo budget ladder (MIT), ai-maestro crash-restart (MIT), humanlayer claims.ts (Apache-2.0: keep attribution, note changes). claude-squad: none (AGPL, no code used).

## Open items / unverified
- ruflo claims/work-stealing and ai-maestro task-registry not read in depth (D by size and backend); repo tests not executed (no clones).
- omc recovery-request-store.ts (26 KB) not read; saga behaviour taken from saga + its test.
- claw-code provenance and licence history unverified (only current LICENSE read).
- humanlayer approval timeout beyond "poll until answered/abort" not specified in the hook; server-side expiry not read.
- Claude Code `PreToolUse` `permissionDecision: "ask"` support assumed from host docs, not tested here.
