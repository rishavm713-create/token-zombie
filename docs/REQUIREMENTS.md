# TOKEN ZOMBIE: master requirements, status and roadmap
Goal: the same task at equal or better quality, with fewer resources and less human intervention.
Rules: never trade correctness for tokens. No savings claim without a valid OFF-vs-ON benchmark (`tz preflight --validate` = VALID).
Keep this file short. Detailed evidence: `handoffs/2026-11-21-requirements-audit.md` (code audit), `handoffs/2026-11-21-competitor-audit.md`.
Status: IMPL = code + regression test | PARTIAL = gap named | MISSING | NV = not verified live | HOST = Claude Code cannot do it.
Savings proven so far: **none**. The only paid A/B (2026-11-21) is INVALID: 5-11 permission denials per arm, 0 files changed.

## Requirements log (append each new owner requirement: date, one line)
- 2026-11-21 R1-R10: core tokens, skills, agents, models, continuity, context, supervisor, measurement, consolidation, product.
- 2026-11-21 R11 workflow: fresh session per independent task; one compact main handoff + a sub-handoff per task; best-cost model
  per task/agent; skills off by default; agents only when parallel work helps; test each task, review independently, then
  integrate + test all; no duplicate work, file conflicts or needless context transfer between agents.
- 2026-11-21 R12: baseline hook execution time before optimising; measure TZ's own overhead.
- 2026-11-21 R13: skills are installed / enabled / discovered / loaded / invoked: five metrics, never confused.
- 2026-11-21 R14: tool dedupe is context-aware and conservative; never suppress a needed command or a side effect.
- 2026-11-21 R15: benchmark preflight before any paid A/B: a tiny task must edit files, run commands, pass acceptance.
- 2026-11-21 R16: finish the current task in its chat (the 100k mark is not a hard stop); a NEW task goes to a fresh chat.
- 2026-11-21 R17: integrate the strongest competitor techniques rather than rebuild existing tools; verify host support live; measure TZ's own overhead.
- 2026-11-21 R18: reuse licence-compatible open-source code (keep notices, attribution, licence files); ideas only for restrictive licences; keep a reuse register (docs/REUSE.md).

## Status by area (2026-11-21, suite `bash tests/run_all.sh` 580/0, Mod `claude plugin test .` 14/0; dev repo, uncommitted, not installed live)
| Area | IMPL | PARTIAL / MISSING |
|---|---|---|
| Measurement | in/out/cache split + cost (tzusage, tzab); EST vs MEASURED labels; hook wall-time baseline `tz hooks bench`; per-event live hook ms + injected chars (tzlive, `tz live`) | live hook ms NV until installed; agent/skill token split MISSING; competitor arm MISSING |
| Benchmark | `tz preflight` offline checks; `--validate` marks old run INVALID; `--smoke --yes` paid tiny task (edit + command + acceptance) tested with fake CLI; B arm hooks = hooks.json | paid smoke NOT RUN (needs owner OK); valid A/B MISSING |
| Skills (R13) | five states in `tz live skills`; Mod bar SKILLS USED = invoked this session; tzcap advise/duplicates/vet | auto-park unused MISSING; unload HOST |
| Agents | lifecycle starting/running/done/failed from hooks; model, background flag; SubagentStop registered; one note for 60+ min background agent | per-agent tokens MISSING; queued state HOST (not in hooks); file-conflict claims MISSING |
| Dedupe (R14) | Read (tzopt, existing); Grep/Glob advice when no possibly-mutating tool ran since; WebSearch/WebFetch within 30 min; advised once per key; cleared on compaction; never a deny; Bash never | Glob/Grep after an external edit (outside hooks) can be stale: advice says "repeat allowed" |
| Hook overhead (R12) | tool events skip tzsup import + transcript head scan (base cached) | each extra hooked tool (Grep/Glob/Web/Agent) now costs ~25-31 ms; net effect NV |
| Continuity (R11) | handoff/resume/MASTER/DAILY/task json, lean start, compaction note | per-task sub-handoff md + task index PARTIAL; review + integration gate MISSING |
| Models | tzroute advice + override log | escalation on failed check MISSING; main-model switch HOST |
| Product | plugin, Mod bar/pane, dashboard, mascot 5 states, local-first | public GitHub MISSING; other agents rules-only |

## Hook time baseline (MEASURED, this Mac, 20 MB transcript, median of 7, `tz hooks bench`)
| Event | before | after stage A |
|---|---|---|
| PreToolUse (Read) | 50.6 ms | 31.3 ms |
| PreToolUse (Grep) | 50.8 ms (not hooked live before) | 24.9 ms |
| PostToolUse | 51.0 ms | 36.6 ms |
| Stop | 57.6 ms | 46.3 ms |
| UserPromptSubmit | 57.8 ms | 57.7 ms |
Bare python start: ~16 ms. These are hook-time numbers, not token savings.

## Roadmap (ranked by net saving vs effort; done = in dev repo, not installed live)
1. DONE preflight: offline + validate + paid smoke. NEXT: owner approves `tz preflight --smoke --yes` (<=250k tokens, haiku).
2. DONE invoked-skill tracking + five skill states; Mod SKILLS USED.
3. DONE agent lifecycle ledger + stale background-agent note.
4. DONE hook baseline + fast path. NEXT: one-week live `tz live` sample after install.
5. DONE conservative Grep/Glob/Web dedupe (advice only).
6. Valid OFF-vs-ON A/B rerun after smoke PASS (owner approval; caps 1.5M/session, 5M total).
7. DONE in dev repo (wired in tz-guard, not installed live) competitor #1: bin/tzout.py `trim()` cuts Read (head only, >20k chars), Grep content / WebFetch result / MCP text
   (head+tail, >12k chars), same output shape; full text in ~/.claude/token-zombie/recall/<id>.txt, `tzout.py recall <id> --grep|--lines`.
   Ledger 'out-trim' (measured chars). Off: config out_trim false or TZ_OUT=0. tests/test_out.sh 17/0. LIVE Haiku probe: Read + Grep
   trims reached the model, it used offset=723 from the marker; 3 trims = 12.2k tok hidden. 23 ms as own process, ~8 ms body.
   Wired: tz-guard PostToolUse + `tz recall`; tzlive skips trimmed keys (test_live). Suite 580/0.
   Read guard: tzopt.read_decision(), config read_guard advice (default, same as today) | deny (once per unchanged file+range,
   main agent only, >=2000 chars, not if trimmed; identical retry allowed) | off. Wired in tz-guard PreToolUse.
8. DONE (skills part) competitor #3: `tz skills` lists enabled-plugin skills, invocations per skill in the last 30 days
   (measured from chat logs), and listed-but-never-invoked skills with tok cost (now 28, ~567 tok per chat). Hidden
   (disable-model-invocation) skills count 0. Runtime ~7 s (scans logs). Subagent re-injected text: see 14.
9. Per-task sub-handoff md + task index; `tz wrap --review` gate + integration test before done (R11).
10. File-claim registry (task -> files) with overlap warning for parallel agents/sessions (R11).
11. DONE competitor #5/#6: tz-vet reports a HIGH pattern found only in tests/fixtures/bench/eval/examples/docs/CI paths or on
   comment lines as [LOW] (no exit 1). HIGH classes before->after: caveman 5->2, ponytail 1->0, token-optimizer 6->3 (its launchd
   persistence stays HIGH), context-mode 6->3, rtk 6->5. `tz stats` prints rtk's own measured Bash savings on a separate line, never
   added to TZ totals (TZ never filters Bash).
12. Public GitHub + contributor docs; competitor arm in the A/B harness.
13. NV (no live evidence yet): WebFetch and MCP output trims. Unit tests pass (test_out mcp-trim; WebFetch field `result` assumed,
   not seen in a real payload). Needed: live host run showing the replacement reaches the model for WebFetch and one MCP tool.
   Needs owner OK (paid headless run, isolated config, no live settings change).
14. PARTIAL (size measured, token delta NV): caveman + ponytail rule text re-injected into every subagent (SubagentStart).
   MEASURED from local subagent logs, last 7 days (no paid run): 440 of 442 subagents carry both; caveman 5202 chars,
   ponytail 3325 chars per subagent = ~2.1k tok EST (chars/4) = ~3.5% of a ~61.7k first-call context, and it is re-read
   on every call that subagent makes. NV: exact token delta (subagent first-call input with vs without the plugins) needs
   an A/B or tokenizer count; owner OK required for any paid run.

## Host limits (Claude Code)
Cannot unload an invoked skill's text; cannot switch the main model without cache loss; PostToolUse `updatedToolOutput` DOES replace built-in output on 2.1.318
(live probes: Read, Glob, Grep content replaced; a rewrite that breaks the output shape, e.g. Grep enum `mode`, is ignored; WebFetch + MCP NV live); no queued-agent or per-subagent token data in hooks; cannot force the
model to follow advice; plan % only from rate_limits / get_usage; Mod Text has no letter-spacing.

## Overlaps to resolve after a valid benchmark
rtk (live Bash filter) vs `tz filter`; caveman/ponytail vs SKILL.md terse rules; find-skills vs tzcap advise; owner CLAUDE.md
handoff rules vs SKILL.md section 2 (same text loads twice); tzread.py dropped: read guard is tzopt.read_decision on top of read_advice. Reuse register: docs/REUSE.md.
