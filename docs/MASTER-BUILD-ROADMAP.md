# TZ Core master build roadmap (2026-11-24)
Scope: TZ Core only (free, MIT, offline-first). TZ Studio is a separate paid product in a separate repo and is NOT started. There is no Enterprise product or tier. No existing Core feature moves behind a paywall. Studio consumes Core only through CLI, JSON and MCP.

Classes: **1** complete and verified, **2** implemented not verified, **3** partial, **4** not implemented, **5** blocked externally, **6** obsolete or rejected.
Status below comes from running or reading the code in this repo on 2026-11-24, not from older docs. Where a doc and the code disagree, the code wins and the doc is listed in section 6 to be fixed.

## 1. Sources: what was and was not inspected
| Source | Inspected? |
|---|---|
| This repo (`bin/`, `tests/`, `hooks/`, `docs/`, git log 135+ commits) | Yes |
| GitHub issues and PRs of rishavm713-create/token-zombie (`gh`) | Yes: 2 open issues (calls for testers), 0 PRs. No code backlog is hidden there |
| Docs: BUILD-LIST, FACTORY-AUDIT, OPEN-CORE-DECISION, MODS-REPORT, LIMITATIONS, LEFT, ROADMAP, VISION | Read in this and earlier stretches of this session |
| ChatGPT responses pasted into this session (list in section 5) | Yes, only the text that was pasted here |
| ChatGPT chats from before this session, and the two ChatGPT share links | **NOT accessible**: BUILD-LIST records link 6b056444 content only as copied earlier; link 6b056307 holds only a question. Nothing beyond what was pasted can be claimed |
| Third-party repos | Licence field re-read from the GitHub API today (section 4). Code was read earlier only for karpathy-skills, cc-safety-net and beads (scratch clones). The rest were NOT re-opened |
| Claude Code host behaviour (panel pause/approve, live mod tools) | Not testable from a subprocess; see class 5 |

## 2. Backlog by item
Columns: id, requirement and source, class, where, what remains, how tested, acceptance, priority. All items are Core unless marked Studio.

### A. Workers, orchestration, safety, verification (the Studio prerequisites)
| id | Requirement (source) | Class | Files | Remains | Tested by | Acceptance | Pri |
|---|---|---|---|---|---|---|---|
| A1 | Provider-independent worker registry: offline, local HTTP, CLI workers (FACTORY-AUDIT phase 1; user mandate) | 1 for registry, cli and offline; http verified against a REAL llama-server (Qwen3-4B Q4) and a fake server | `bin/tzworkers.py` | Flags of codex/gemini/opencode/aider templates are from memory: only `claude` and `codex` are installed here and `claude` ran; others unverified | test_upgrade (cli, http fake, unknown worker); live `worker test local` returned OK on the real server | `tz worker add/test/run` works for each kind | done |
| A2 | tzagent runs phases through the registry, configurable default, per-task `--worker`, timeout, no Claude hardcoding (mandate a) | 1 | `bin/tzagent.py`, `tzworkers.default()` | Claude is still the default worker. Token usage is MEASURED only for claude; others are EST chars/4 and say so | test_agent 8/8 (fake claude), test_upgrade cli worker + offline cases | same task runs by changing `--worker` only | done |
| A3 | Verification gate independent of workers: diff scope, ownership, TZ Safe on added lines, secret scan, tests, build, checkpoint, status ladder, bounded repair of at most 2 (mandate b) | 1 | `bin/tzgate.py`, `tz gate`, `tzagent --gate` | No lint/type/dependency-audit runners yet (A7). "Regression checks" = the project's own test command; no baseline-vs-after comparison | test_upgrade: seeded leaked key, out-of-scope file, failing test, clean change, repair stops at 2 | a worker's "completed" never sets status; gate does | done |
| A4 | Same real task through offline, local model, Claude Code, other CLI worker; honest comparison (mandate c) | 3 | section 3 below | Claude and codex runs: see section 3 for exactly what ran | run logs in section 3 | results table with failures kept | high |
| A5 | TZ Safe live: block destructive Bash, `TZ_SAFE=0` off | 1 | `bin/tzops.py`, `bin/tz-guard.py` | Hook was verified by test input and live in this session; other hosts (Codex, Cursor) have no hook | test_upgrade (block `git reset --hard`, allow `ls`) | | done |
| A6 | Checkpoints and recovery | 2 | `tzagent.checkpoint`, `tzhandoff`, `tz resume` | Checkpoint rows are written and now validated by the gate; there is no `tz agent --resume RUN` that continues a half-finished run | continuity tests 32/32 for handoff; none for resuming a killed agent run | killed run resumes at its next phase | high |
| A7 | Lint, type, dependency audit, secret scan as gate checks | 3 | `tzgate.py` (secrets only) | Lint/type/dep-audit only via `--build CMD` supplied by the user; no auto-detection of ruff/eslint/pip-audit | none | `tz gate` auto-detects and runs what is installed | medium |
| A8 | File ownership and worktrees | 1 | `tzagent.claim/release/make_worktree` | Ownership is advisory by file name; two agents on one tree are not prevented by the OS | test_agent ownership + worktree | | done |
| A9 | Real multi-agent coordination (spawn, duplicate-work detection, report collection) | 3 | `tzagent`, `tzsplit`, `tznext` | Tracking exists; orchestration of parallel workers does not. Host cannot be driven from a mod | none | N tasks run in parallel worktrees, each gated, merged by TZ | high |
| A10 | Task dependencies in `tz next` (beads model) | 4 | `bin/tznext.py` | Not built | | `tz next` skips tasks whose deps are open | medium |

### B. Token and context optimisation
| id | Requirement (source) | Class | Files | Remains | Tested by | Pri |
|---|---|---|---|---|---|---|
| B1 | Tool-output filtering, reversible recall of originals, redaction | 1 | `tzout`, `tzcrush`, `tzcompress`, hooks | WebFetch/MCP trims are unit-tested only (LIMITATIONS) | test_e2e/test_hard | done |
| B2 | Reversible compression and cache-aware notes (Headroom) | 2 | `tzcrush`, recall store | Cache-awareness not measured against a provider | unit | medium |
| B3 | RTK filter coverage gap audit | 4 | none | Compare rtk filter set with `tzout`; add missing | | low |
| B4 | Bounded output with retrieval (context-mode ideas, clean-room only) | 2 | `tzout recall` | | unit | low |
| B5 | Repo intelligence: map, finder, impact, similar | 1 for map/finder/impact; 3 for symbol navigation | `tzmap`, `tzfinder`, `tzops.impact` | impact is git-grep word match, not AST or Tree-sitter; no symbol index (Serena idea) | tests | medium |
| B6 | Instruction-file organiser (core vs archive) | 4 | none | | | low |
| B7 | Savings measured end to end: with/without benchmark, `tz bench`, replay | 3 | `tzbench`, `tzreplay`, `tzab` | A/B needs two logged-in config dirs (external). Only synthetic and offline replay (net 0.58%) are measured | test_bench | high |

### C. Hardware and local models
| id | Requirement | Class | Files | Remains | Pri |
|---|---|---|---|---|---|
| C1 | Hardware detection and tier advice | 1 (detection MEASURED, fit table EST) | `tzworkers.hw` | | done |
| C2 | Local model execution via OpenAI-compatible server | 1 for llama-server + Qwen3-4B Q4 on this M3 16 GB; Ollama NOT tested (not installed) | `tzworkers.invoke` | Ollama, LM Studio, vLLM untested | medium |
| C3 | Throughput measurement (`llama-bench`) | 4 | | Server log shows 12.9 tok/s generation for Qwen3-4B Q4 on this machine under a loaded system; no controlled benchmark | low |
| C4 | Local model quality for edits | 3 | section 3 | Qwen3-4B result recorded in section 3 | |

### D. Product pipeline (Core part)
| id | Requirement | Class | Files | Remains | Pri |
|---|---|---|---|---|---|
| D1 | `tz scaffold` offline skeleton | 3 | `tzscaffold.py` | One template, no UI. Module library, UI template, payments stub, deploy files are not built | medium |
| D2 | `tz run` ten-stage front door | 2 | `tzops.run` | Dry by default; never run end to end on a real task | medium |
| D3 | `tz spec` (prompt to spec.json, assumptions, task graph) | 4 | | FACTORY-AUDIT phase 3 | medium |
| D4 | `tz modules` (auth, roles, uploads, jobs, billing stub, admin) | 4 | | phase 4 | medium |
| D5 | `tz factory` graph executor | 4 | | phase 5; depends on A9, D3 | later |
| D6 | UI templates and browser smoke tests | 4 | | phase 6; design taste needs a model or reference | later |
| D7 | `tz deploy` file generation (no deploy without explicit OK) | 4 | | phase 7 | later |
| D8 | `tz edit` and `tz run --saas` | 4 | | listed open earlier | later |
| D9 | Research before build: reuse licence audit | 1 (`tz reuse`); web/doc reader and feature matrix 4 | `tzbuild.py` | | low |

### E. Mod and host integration
| id | Requirement | Class | Where | Remains |
|---|---|---|---|---|
| E1 | One mod: panel + 9 tools shelling to `tz` | 2 | `hooks/panel.tsx`, `hooks/tools.ts` | validates; never exercised in a fresh live chat (needs session start with the plugin enabled) |
| E2 | `tz_verify` runs project tests | 3 | | `tz gate --test` now exists; the mod tool still calls handoff-vs-git |
| E3 | Panel pause / approve / retry | 5 | | no host API in this build |
| E4 | Spawning agents from a mod | 5 | | no safe API (MODS-REPORT) |
| E5 | `tool.run` hook event | 6 | | does not exist; `tool.call` is used |
| E6 | Adapters for 7 other hosts | 3 | `tzadapters` | rules files only; capabilities unverified; only claude is REAL |
| E7 | Install and upgrade validation on a clean machine | 3 | `install.sh`, test_upgrade | tested in temp dirs on this Mac only; no clean-VM or Linux run |
| E8 | Website update for new commands | 4 | `docs/index.html` | worker, hw, gate, scaffold missing; website redesign is deferred by decision |

### F. Quality and reliability
| id | Item | Class | Detail |
|---|---|---|---|
| F1 | Full suite | 3 | Last full run: 947 pass, 4 fail (below). Needs a rerun on a quiet machine |
| F2 | SIGKILL test | 1 (root cause known) | the test sleeps 1.5 s before `kill -9`; with load average above 100 the runner had not written its partial count. Passes standalone. Not a logic bug; threshold and test unchanged |
| F3 | Timing tests (tick 400 ms, statusline 250 ms, tool-event hook 200 ms) | 3 | failed only under load average 25-147 (measured 634, 469, 328 ms); passed on the earlier quiet run (938 pass, 3 timing failures at that time too). Not loosened |
| F4 | "restart on same port works" | 3 | failed once under load, unexplained, needs a quiet rerun |
| F5 | Tests rewrite four tracked docs | 3 | `docs/BUILD-LOG.md DEVELOPMENT-STATE.md HANDOFF.md NEXT-SESSION.md` change on every full run; restore with git checkout. Fix: write snapshots outside tracked files |
| F6 | Multi-task detector misfire on pasted text; sonnet-only review phase; status registry | 4 | from BUILD-LIST item 6 |

### G. Competitor-derived items (BUILD-LIST table, 13 items)
Built: 1 `tz diffcheck`, 2 `tz impact` (word match), 6 `tz safe`. Open: 3 task deps (A10), 4 staged flow (partly: plan/build/test/debug exists, no PRD stage), 5 instruction organiser (B6), 7 skill registry, 8 headroom ideas (B2), 9 RTK gap audit (B3), 10 clean-room bounded output (B4), 11 symbol navigation (B5), 12 tokens per passed task (needs login, class 5), 13 spec-to-tasks (D3).

## 3. Acceptance: same task, different workers (2026-11-24, this Mac)
Task: in a fresh git repo, `calc.py` has `add(a,b): return a-b` and `t.py` asserts `add(2,3)==5`. Command: `tz agent "fix add() in calc.py so python3 t.py passes" --worker W --test "python3 t.py" --gate --files calc.py`.
| Worker | Result | Evidence |
|---|---|---|
| offline | fails cleanly at plan, 0 tokens, says it has no model | test_upgrade |
| local: llama-server + Qwen3-4B Q4_K_M (real server, port 8089) | see below | run logs |
| claude (Claude Code) | see below | |
| codex | see below | |
Results (all four are one run each; n=1, not a benchmark):
- **local Qwen3-4B Q4 (real llama-server, 12.9 tok/s)**: attempt 1 (diff reply) FAILED: model wrote a corrupt patch, `git apply` rejected it. Changed the edit contract to whole-file blocks. Attempt 2 PASSED test and gate, but the model rewrote `add(a,b)` as `add(*args): return sum(args)`: it satisfies the test and changes the API; the gate does not detect that kind of drift. About 3 min wall time; tokens EST 217.
- **claude (Claude Code)**: fixed correctly (`return a+b`), test pass. MEASURED 81,843 tokens (plan 39.5k, build 15k, then 2 repair rounds 27k). The gate FAILED a correct change because the test run left an untracked `__pycache__` that the scope check flagged; that is a gate bug, fixed (build-noise paths now ignored). The repair rounds were wasted tokens caused by that bug. Rerun of the gate on the same result: TESTED. Wall 1:13.
- **codex**: attempt 1 made no change (`codex exec` default sandbox is read-only), gate FAILED with "worker produced no changes", 2 repair rounds also did nothing. Template changed to `--sandbox workspace-write`; attempt 2 PASSED test and gate. Tokens are EST chars/4 of prompt and reply only, not codex's real usage (UNKNOWN).
- Not tested: Ollama, aider, gemini, opencode (not installed). Local-model integration is claimed only for llama-server on this machine.
- Honest comparison: the quality order here is claude (cheapest correct fix by diff size, most tokens) vs local 4B (free, slow, changed the API) vs codex (correct after the template fix). One task proves nothing about general quality.

## 4. Open-source projects: licence (GitHub API, 2026-11-24) and verdict
Rule: reuse code only from permissive licences with notice kept; otherwise learn the behaviour and write clean-room. TZ owns orchestration, safety, verification and recovery, so no project below is a hard dependency.
| Project | Licence (API) | Verdict | Used how today |
|---|---|---|---|
| RTK (rtk-ai/rtk) | Apache-2.0 | integrate optional: ledger records rtk deltas; learn filters | B3 audit open |
| Context Mode (mksglu/context-mode) | NOASSERTION (earlier read as Elastic 2.0) | avoid code; clean-room idea only | B4 |
| Headroom (chopratejas/headroom) | Apache-2.0 | learn (reversible compression, cache) | B2, HEADROOM-COMPARISON.md |
| LeanCTX (yvgude/lean-ctx) | Apache-2.0 | learn; not yet compared in detail | none |
| Karpathy skills (forrestchang/andrej-karpathy-skills) | **none on GitHub** (BUILD-LIST said MIT) | learn the idea only; `tz diffcheck` rules are rewritten, no text copied. Fix the BUILD-LIST licence claim | A3 |
| Superpowers (obra/superpowers) | MIT | learn workflow ideas; optional skill install by the user | none |
| Claude-Mem (thedotmack/claude-mem) | Apache-2.0 | learn; TZ keeps tzdb + handoffs as only stores | none |
| Beads (steveyegge/beads) | MIT | learn task-dependency model, reuse allowed with credit | A10 |
| Aider (Aider-AI/aider) | Apache-2.0 | integrate as optional CLI worker (`aider --yes --message`, flags unverified); learn repo map | A1, B5 |
| Serena (oraios/serena) | NOASSERTION (LICENSE file exists, not read) | read LICENSE before any reuse; default learn only | B5 |
| Tree-sitter | MIT | integrate optionally for symbol maps, with the regex fallback | B5 not started |
| Oh My ClaudeCode (Yeachan-Heo/oh-my-claudecode) | MIT | learn staged flow | A9 |
| OpenHands (All-Hands-AI/OpenHands) | MIT (core) | learn sandbox and event model; not integrated | none |
| mini-SWE-agent (SWE-agent/mini-swe-agent) | MIT | learn the minimal loop; possible worker | none |
| ccusage (ryoppippi/ccusage) | MIT | learn; TZ has its own `tzusage` | none |
| Harbor / Terminal-Bench (laude-institute) | Apache-2.0 | benchmark harness candidates for B7, needs live paid runs | not run |
| SWE-bench | MIT | benchmark dataset for B7 | not run |
| Ponytail, cc-safety-net, claude-squad | not re-checked today. cc-safety-net MIT read earlier; claude-squad AGPL excluded | | A5 |

## 5. ChatGPT responses pasted in this session: built or not
| Response | Built? |
|---|---|
| Competitor audit and 13-item build list (BUILD-LIST) | 3 of 13 built (diffcheck, impact, safe); rest open, see G |
| Claude Mods spec A-G, phases 1-6 | One mod built and validated; not live-tested; pause/approve/retry and agent spawning blocked by host |
| TZ 3.0 Product Factory vision (12 sections) | Phase 0 audit, phase 1 workers, phase 2 gate built. Phases 3-8 (spec, modules, factory, UI, deploy, acceptance product) NOT built |
| Open-core strategy | Written as OPEN-CORE-DECISION.md, now two products (Core, Studio), Enterprise removed. No Studio code and no second repo, by decision |
| Master Product Vision / Engineering Mandate (17 sections, 3 modes) | Audit done (FACTORY-AUDIT). Only the parts in A-D above are built; the product-builder modes are not |
| Two repos, one website, one brand structure | Decision recorded only. Repo 2 and website changes not started, by decision |
| Original EditSutra-style acceptance product | NOT built |

## 6. Doc fixes still owed
FACTORY-AUDIT "Suite status" and phase table (phases 1-2 now done); BUILD-LIST karpathy licence; LIMITATIONS "Adapters" line is still true; website command list (E8).

## 7. Order of work from here (Core only)
1. Quiet-machine rerun of the full suite and the four timing tests (F1-F4). 2. Resume for killed agent runs (A6). 3. Gate auto-detect lint/type/audit (A7). 4. Parallel worktree coordination (A9) and task deps (A10). 5. Tree-sitter symbol map with regex fallback (B5). 6. Benchmarks with Harbor/Terminal-Bench when credentials exist (B7). 7. spec/modules/factory (D3-D5). Studio, second repo and website redesign only after 1-4 are class 1.

## 8. Milestone 2 status (2026-11-24): reliability + gate hardening + resume
Full suite on this Mac after the changes: TOTAL pass 978, fail 0 (before them, quiet machine: 953/1; the 1 was a private-key literal in tzgate, fixed). test_gate2 24/0, test_agent 8/0, test_upgrade 27/0. Timing flakes fixed by readiness polling, thresholds unchanged.
VERIFIED (tests pass): killed-run resume (`tz agent --resume ID|last`, SIGKILL test); Python public-API drift detection (bin/tzapi.py; add(a,b)->add(*args) with passing tests is caught); tests-actually-ran check; syntax check; regression-link check.
IMPLEMENTED, only stub-tested: lint/type/audit detection (ruff/flake8, mypy/pyright, pip-audit, npm lint/tsc/audit). No real tools installed here; offline/missing = skipped, never passed.
LIMITS: regression check is a static link (test mentions module), not proof of exercise; resume reruns test/gate loops with a fresh budget; API check is Python only (JS/TS not covered).
UNTESTED: live Claude Code session validation; local models other than Qwen3-4B on llama-server; codex/gemini/others (deferred).
REMAINING: A9 parallel worktrees, A10 task deps in tz next, B5 tree-sitter map, benchmarks (need credentials), doc fixes, install/upgrade validation beyond this Mac, JS/TS API check.
18-capability audit (short): verified: 5,6,11,12,13,14,2,16; implemented-unverified: 1,3,4,7,9,10,17,18; partial: 8 (one local model), 15 (no parallel coordination); missing: none; blocked: benchmarks vs baseline (credentials). Claude-Code-in-live-session validation owed for 7.
