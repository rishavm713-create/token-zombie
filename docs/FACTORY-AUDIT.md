# TZ 3.0 Product Factory: audit, gaps, architecture, roadmap (2026-11-24)
Status words used here: GENERATED < IMPLEMENTED < TESTED < VERIFIED < PRODUCTION-READY < DEPLOYED. Nothing below is claimed past TESTED unless a command proves it.

## 1. Current-state audit (measured from the repo, main @ 6ad92e0 + scaffold)
Size: ~10k lines Python in bin/ (63 files), 44 test scripts, hooks (tsx/ts), skills, docs. 132 commits.
| Area | What exists | State |
|---|---|---|
| Orchestrator core | `tz` dispatcher, `tzagent` (plan/build/test/debug loop, budget, worktree, file ownership), `tznext` (task deps, gates, 2k-token task pack), `tzsplit`, `tzroute` (model advice), `tzdb` ledger | works, tested |
| Token layer | tzout/tzcrush/tzcompress (filter, trim), tzopt, tztokens, tzusage, tzcost, tzreplay, tzbench, tzab | works; savings labelled MEASURED/EST |
| Memory/continuity | tzhandoff, tzintegrity, tzcont, handoffs/, docs/HANDOFF etc | works (continuity tests 32/32) |
| Repo intelligence | tzmap (repo map), tzfinder, tzstandards, tzsimilar (GitHub search), tzbuild: reuse (licence audit), gaps, missing, contract, api, dbschema | works |
| Guard | tz-guard hook (read advice, circuit breaker, file claims), **tz safe** (destructive Bash deny, TZ_SAFE=0 off) | wired; test_upgrade 20/20 |
| Product generation | `tz scaffold` (one stdlib CRUD+auth skeleton, tests pass), `tz run` (10-stage front door, dry by default) | thin: ONE template, no UI |
| Workers | tzadapters (claude, codex, gemini, cursor, cline, roo, windsurf, antigravity: rules/capability tables only), `tzagent` calls `claude -p` (CLAUDE_BIN override) | rules generation only; no worker abstraction, **no Ollama/local model code** |
| Deploy | none | missing |
| UI/visual | none for generated apps (overlay/panel are TZ's own UI) | missing |
| Research | tzsimilar + reuse licence audit; no web/doc reader, no feature-matrix | partial |

Suite status (2026-11-24, run still in progress when written): test_upgrade 20/20 incl. TZ Safe guard (block `git reset --hard`, allow `ls`). Failures seen so far, all in test_e2e/test_hard under load average ~25: tick 634 ms (limit 400), statusline 469 ms (250), tool-event hook 328 ms (200), and "SIGKILLed runner leaves partial count" (not a timing check, NOT yet investigated or rerun alone). Thresholds unchanged. Earlier quiet-machine run: 938 pass, 3 timing failures.

## 2. Duplicates / debt (do not rewrite, just note)
- Routing exists twice in spirit: tzroute (advice) and tzsplit (model per task). Keep both; workers.json becomes the one registry later.
- Docs overlap (ROADMAP, VISION, LEFT, NEXT-SESSION, BUILD-LIST). Factory work is tracked only in this file + BUILD-LIST.
- tz-guard is 394 lines doing many jobs; add logic there only as tiny calls (as done for safe).

## 3. Gap analysis vs the 12 sections
| Vision item | Gap | Zero-token? |
|---|---|---|
| Offline engine (scaffold, CRUD, auth, schema, API, config, format, lint, deps, git) | one template; no module library, no frontend, no lint/format/dep-audit runner | yes (templates + tools) |
| Local intelligence | nothing | local compute only |
| External intelligence | claude only in tzagent; adapters are docs | paid |
| Prompt-to-product (12 artifacts) | none; scaffold only picks an entity name | spec skeleton + assumptions list is rule-based; real understanding needs a model |
| Product modules | only auth+CRUD | yes once written and tested |
| Reverse engineering | licence audit only | reading public pages/APIs = zero model tokens; synthesis needs a model |
| Execution engine | tzagent exists, single worker | partly |
| Workers + routing by capability/cost | missing registry | yes |
| Token/cost tracking | exists | yes |
| Quality gate + status ladder | pieces exist (tests, diffcheck, safe); no secret scanner or dependency audit; no unified `tz verify` for generated products | mostly yes |
| Visual builder | missing | templates yes; "looks like a real product" needs design input/model |
| Deploy prep | missing | yes (files only); actual deploy needs user authorization |

## 4. Architecture (additions only; everything existing stays)
```
idea ──> tz spec ──> spec.json (assumptions listed) ──> tz plan graph (tznext tasks with deps, gates)
                                                             │
        tz modules (tested template library) ◄── offline engine ── tz scaffold/compose
                                                             │
        worker registry (workers.json): offline | ollama | claude | codex | aider | opencode | gemini
                    task router: capability, cost, reliability, budget  (extends tzroute/tzsplit)
                                                             │
   each task: worktree + file allowlist (tzagent/claim) ─> worker ─> GATE ─> pass: checkpoint commit
                                                                   └> fail: diagnose → retry cheaper→stronger (max 2) → report
GATE = tz safe + tz diffcheck + tests + lint/type + secrets + dep audit  (all zero-token)
ledger (tzdb) records tokens, time, worker, status ladder per task.  Delivery report = tz report.
```
New files only: `tzworkers.py` (registry+invoke), `tzspec.py`, `tzmodules/` (templates), `tzfactory.py` (graph executor), `tzgate.py` (verify + status ladder), `tzdeploy.py` (prep files). No second memory DB: tzdb + handoffs stay the only stores.

## 5. Integration map
tzspec → tznext (tasks) → tzfactory → tzworkers → tzagent/ollama/CLI adapters; tzfactory → tzgate (tzops.safe/diffcheck, tzbuild.gaps/contract/dbschema, tzstandards) → tzdb ledger → tokens/progress; research: tzsimilar+reuse (licence) → tzspec feature matrix.
External (all optional): ollama, claude, codex, aider, opencode, gemini CLIs, git, gh, node/npm, ruff/eslint/pip-audit/npm audit, playwright for browser checks.

## 6. Phased roadmap (each phase ends with passing tests and a status line; stop-points are real)
| Phase | Deliverable | Est. | Needs model? |
|---|---|---|---|
| 0 | This audit + full-suite baseline | done | no |
| 1 | `tzworkers`: registry, `tz worker add/list/test`, invoke adapters (offline, ollama HTTP localhost, any CLI template string), per-task budgets; tzagent uses it | 2-3 h | no (workers optional) |
| 2 | `tzgate`: `tz verify` runs tests, lint, secrets, dep audit, diffcheck, safe; writes status ladder per task | 2-3 h | no |
| 3 | `tzspec`: prompt → spec.json + assumptions + task graph into tznext; rule-based baseline, model-enhanced when a worker is set | 3-4 h | baseline no; quality yes |
| 4 | `tzmodules`: auth, orgs/roles, uploads, jobs, billing STUB (provider test mode), admin; each with tests; compose into a Flask/FastAPI+SQLite or Node app | 1-2 days | no |
| 5 | `tzfactory`: executes the task graph, routes workers, checkpoints, rollback on failed gate, max 2 repairs, final report | 4-6 h | when a task is not templatable |
| 6 | UI templates (design system, responsive pages, states) + Playwright smoke + screenshot diff | 1-2 days | design taste needs model/reference |
| 7 | `tzdeploy`: Dockerfile, CI, env template, host configs; deploy only on explicit user OK | 3-4 h | no |
| 8 | Acceptance: EditSutra-style app end to end (see below) | 1-2 days | yes for the video-AI core |
Total to a first honest end-to-end run: roughly 1 to 2 weeks of focused work, not 2 hours. Phases 1-2 are the next safe step.

## 7. Testing and acceptance
- Per phase: unit tests in tests/, added to run_all.sh; a phase is DONE only when its tests pass and the full suite is run (timing tests may flake under load: re-run alone, never loosen thresholds).
- Module library: every module has its own generated-app test; composing modules must pass them in a clean temp dir.
- Gate tests: seeded bad inputs (leaked key, failing test, destructive command, out-of-scope file) must be caught.
- Acceptance product (EditSutra-style): prompt "video editing SaaS: upload, auto-cut silences, captions, export, accounts, subscriptions (test mode), dashboard". Pass = unattended run reaches TESTED with: accounts/uploads/projects/dashboard working, silence-cut and caption jobs run via ffmpeg+whisper locally, UI smoke test passes, gate green, delivery report lists what is stubbed. DEPLOYED and PRODUCTION-READY stay out of scope until a human approves.

## 8. Risks
1. Over-claiming: "builds anything" is false; template coverage bounds the zero-token part. Mitigation: status ladder + report of what was stubbed.
2. Cheap/local workers produce bugs; repair loops can burn tokens. Mitigation: gate first, max 2 repairs, budgets, stop and report.
3. Scope explosion (100 features). Mitigation: only phases above; one acceptance product.
4. Security: generated auth/billing code. Mitigation: established libraries, secret scan, no real keys, test mode only, no deploy without OK.
5. Licensing/IP in reverse engineering: public info and permissive code only; reuse licence audit stays mandatory; no auth bypass, no proprietary copying.
6. Test flake under load; mitigation: no threshold changes, rerun alone.
7. Host limits: tz cannot drive other Claude sessions or the panel; workers are subprocesses.

## 9. Zero-token vs model-dependent
Zero-token: scaffolding/templates/modules, schema and API generation from a spec, config/env, dependency install, format/lint/type/static checks, test execution, secret and dependency scans, repo map/search, git checkpoints/rollback, deployment file generation, reports, ledger, licence audit, public-page fetching.
Local model (no cloud tokens, local compute): planning drafts, standard feature code, classification, first-pass review/debug.
External model (metered): novel algorithms, hard architecture trade-offs, difficult debugging, UI design taste, synthesizing research into a spec.
