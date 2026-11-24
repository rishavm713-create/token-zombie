# TZ Core / TZ Studio: open-core decision (2026-11-24)
Status: DECISION PROPOSAL. Nothing here is built. Benchmark figures are third-party snapshots from web search on 2026-11-24, not re-run by us. UNKNOWN means not found.
Owner machine: Apple M3, 16 GB unified, 148 GB free, llama-server installed, Ollama not installed. Repo licence today: MIT (c) Rishav Mishra.

## 1. Recommendation (short)
1. **TZ Core stays MIT, fully offline-capable**: CLI, offline engine (scaffold, modules, gates), repo intelligence, token tracking, TZ Safe, worker adapters (claude, codex, gemini, opencode, aider, local), checkpoint/recovery, local MCP server, `tz hw` hardware advisor. Nothing already shipped gets paywalled.
2. **TZ Studio is a separate, closed-source product** in its own repo that depends on Core only through stable CLI/JSON/MCP contracts. Paid value = visual builder, workflow-automation designer, hosted execution, collaboration, managed connectors, governance.
3. **There are exactly two products: TZ Core (free, MIT) and TZ Studio (paid, proprietary).** No third product, tier or Enterprise offering. Hosting, teams and governance features, if built, are part of Studio.
4. **Claude/Codex/etc. are optional workers.** Core must pass its full test suite with no worker installed.
5. **No rewrite.** Only additions: worker registry, gate, spec, modules (see FACTORY-AUDIT.md phases 1-3). Studio waits until Core phases 1-5 are proven.

## 2. Licensing and redistribution
| Question | Finding / decision |
|---|---|
| Core licence | Keep MIT (already in place, maximum adoption). Risk: a cloud vendor can host it. Mitigation: the value is in Studio, not the CLI; Apache-2.0 is the alternative if patent grant/trademark clarity matters (switch costs little now, hard later). Decide before the first outside contributor. |
| Copyleft alternative | AGPL/BUSL/Elastic/FSL would protect against hosting clones but harm adoption and conflict with "genuinely open". Not recommended for Core. FSL/BUSL only worth considering for Studio source-available, UNKNOWN demand. |
| Contributions | Add a DCO (sign-off) now; a CLA only if Core and Studio licences may diverge. |
| Trademark | Register/claim "Token Zombie" and "TZ Studio" marks; the licence grants no trademark. |
| Bundled/redistributed code | Existing policy holds: MIT/Apache/BSD/ISC lead to reuse with credit; no licence leads to study only; copyleft needs a human check. Models: check each model licence (Qwen3-Coder is Apache-2.0 per its Hugging Face card; verify each model before bundling, never bundle weights, download on user action). |
| Reverse-engineering feature | Public pages, public docs, permissive repos only; no auth bypass, no private code. Original implementation. Legal review needed before marketing it. |
| Dependencies in Studio | Avoid AGPL libraries in the closed product; keep an SBOM; `tz reuse` already audits licences. |

## 3. Reusable OSS (verify licence per release before adopting)
- Local runtimes: llama.cpp (MIT, `llama-server` already on this machine, OpenAI-compatible HTTP), Ollama (MIT), MLX/mlx-lm (MIT, Apple-only), LM Studio (closed app, do not depend).
- Agents as workers: Aider (Apache-2.0), OpenCode (MIT), OpenHands (MIT core), mini-SWE-agent (MIT, already the model for tzagent), Codex CLI (Apache-2.0), Gemini CLI (Apache-2.0). Claude Code is proprietary: invoke it, never bundle it.
- Workflow engines to study/embed for the automation builder: n8n (fair-code "Sustainable Use" licence, NOT open source; do not embed or resell), Node-RED (Apache-2.0), Activepieces (MIT core, enterprise folder separate), Windmill (AGPL, avoid embedding). Safest path: own small JSON workflow engine plus Node-RED/Activepieces as optional exports.
- Visual UI: React Flow/xyflow (MIT) for the workflow canvas; Playwright (Apache-2.0) for browser tests.
All entries are from general knowledge, not re-verified today: run `tz reuse` on each before use.

## 4. Local models: honest capability picture
Benchmarks found (third-party; harness and date matter):
| Model / system | Benchmark | Result | Source / conditions |
|---|---|---|---|
| Qwen3-Coder-30B-A3B-Instruct (30.5B total, 3.3B active) | SWE-bench Verified | 51.9% on a 484-instance subset | Nebius OpenHands run (16 instances had infra errors). Official HF card lists no score. Quantization/hardware: UNKNOWN (likely served at full precision). Not comparable to the full 500. |
| same | Terminal-Bench | UNKNOWN (no published figure found) | |
| Open-weight models, SWE-bench Pro | SWE-bench Pro | Original 2025 paper: best agent 23.3%. A 2026 blog reports ~62% for recent vendor-aggregated open models, not Scale-standardised | Epoch AI rates the benchmark "Flawed" (30%+ tasks possibly broken). Treat as indicative only. |
| Terminal-Bench 2.0 (89 tasks) | top entries | Codex on GPT-5.5 ~82% (aggregator), best open harness row ~52% (OpenHands) | Harness drives results; Claude Code score UNKNOWN from my search. Check tbench.ai directly. |
| WebDev Arena / Image-to-WebDev | UNKNOWN: not searched successfully | | |
Reading: model intelligence, agent harness and deterministic automation are three separate levers. The same model moves a lot with harness. Our lever is the third: TZ removes work that needs no model at all (scaffold, search, tests, lint, rollback), so the model only sees the residue. That claim is **EST until we run a with/without benchmark** on the same tasks (planned in section 9).

Hardware matrix (weights memory = params x bits/8; add KV cache and ~1.5-2 GB runtime/OS; Apple GPU can use roughly 65-75% of unified memory by default; figures are estimates, not measurements on this machine):
| Unified memory | Practical models (4-bit) | Role | Caveat |
|---|---|---|---|
| 8 GB | 1.5-4B dense (e.g. Qwen2.5-Coder 3B class) | classification, commit msgs, tiny edits | no real agent loop; context ~4k |
| **16 GB (this Mac)** | 7-14B dense (~5-9 GB weights) with 8-16k context | planning drafts, single-file edits, review | 30B-A3B Q4_K_M needs ~19 GB weights (+~4 GB KV at 16k per estimator sites): does NOT fit comfortably; one estimator reports ~6 tok/s when forced, UNKNOWN on M3 until `llama-bench` is run here |
| 24 GB | 30B-A3B at Q3-Q4 with short context | local agent worker, slow | estimator: ~9 tok/s at Q3 on M2 |
| 32 GB | 30B-A3B Q4 with 16-32k context; 14-24B dense | usable local worker | |
| 64 GB+ | 70B-class Q4, or 30B-A3B at high precision and long context | strong local worker | still below frontier on hard tasks |
| Discrete GPU 8 GB VRAM | 7B Q4 fully on GPU; MoE with expert offload to RAM | like 16 GB Mac | CUDA/ROCm via llama.cpp |
| GPU 24 GB | 30B-A3B Q4 / ~32B dense Q4 | good local worker | |
Plan: `tz hw` reads RAM/chip/free disk, picks a tier from this table, and prints which local worker fits. It must say "estimate" until we measure with `llama-bench` on the owner machine. Never promise frontier ability from small models.

## 5. Open-core boundary (exact)
| Capability | Core (MIT, free) | Studio (paid) |
|---|---|---|
| CLI, offline engine, scaffold, module library | yes | uses it |
| Worker adapters + registry + router, local model support | yes | |
| Gate (tests, lint, secrets, deps, diffcheck, safe), status ladder | yes | |
| Checkpoint, rollback, ledger, token tracking, reports | yes | |
| Agent-facing MCP/CLI contract | yes | |
| Single-user workflow engine (JSON, run from CLI) | yes (basic) | |
| Visual product builder, live preview, approvals UI | | yes |
| Visual workflow designer + NL-to-workflow editor, versioning, run history UI | | yes |
| Managed connectors (Gmail, Slack, CRM, billing) with maintained auth | | yes |
| Hosted execution, preview URLs, one-click deploy | | yes |
| Team workspaces, comments, shared checkpoints | | yes |
| Later Studio team features: SSO/SAML, RBAC, audit log export, private deploy | | yes (later) |
Test of the boundary: a solo developer with no money can build, test and ship real software with Core alone; Studio saves time and adds team/hosted conveniences. Core never gets crippled to push Studio.

## 6. Architecture
Core (extends existing files): `tzworkers` (registry/invoke: offline, llama-server/Ollama HTTP, CLI templates for claude/codex/gemini/opencode/aider), `tzgate`, `tzspec`, `tzmodules`, `tzfactory`, `tzdeploy`, plus a local MCP server exposing the nine questions an agent may ask (capabilities, repo contents, remaining work, AI-free tasks, reasoning tasks, safest strategy, what changed/failed, needs verification) backed by existing tzmap/tznext/tzdb.
Studio: a local web app (own repo) talking to Core over CLI/JSON and a localhost API; hosted variant adds auth, tenancy, job queue, sandboxed workers (containers). Contract: versioned JSON schemas for spec, task, result, status ladder; breaking changes need a version bump.
Automation engine: workflow = JSON graph (trigger, condition, action, branch, loop, delay, human-approval, retry policy, error edge). Actions that send email/money/delete default to "needs approval". Execution log + version per run; dry-run mode with fake connectors that are labelled as such.

## 7. Security and governance
- Secrets only from env/secret store, never in specs or logs; secret scan in gate.
- Workers run with file allowlist, budget, no push/rm -rf/sudo (already in tzagent); TZ Safe guard on live hook.
- Hosted: container sandbox per job, network egress policy, per-tenant keys, audit log. Studio team features (SSO, RBAC, retention) are later scope. SOC2 etc.: UNKNOWN effort, not claimed.
- Financial or outbound-message actions always require explicit human approval.

## 8. Revenue models (evaluate, then pick two)
| Model | Fit | Risk |
|---|---|---|
| Studio individual/pro subscription | good for founders/devs | needs a visible quality gap vs free Core |
| Agency plan (seats, white-label, client workspaces) | best fit with an agency angle | support load |
| Studio team/business plan (private deploy, SSO, audit) | higher price, still Studio | long sales cycle |
| Managed cloud execution (usage-based) | optional, margin on compute | must stay optional; BYO model/infra always allowed |
| Services (build/automation setup) | fastest first revenue | does not scale; keep as bridge |
Price points: UNKNOWN until user interviews; do not publish numbers yet. Recommended start: services plus Studio beta for agencies, then subscriptions.

## 9. Benchmarks and acceptance
- Do not publish scores we did not run. Plan: (a) 20 fixed real tasks on a private repo set, run with agent alone vs agent + TZ, same model, harness and budget; record completion, build/test pass, regressions, tokens and cost per success, time, human interventions; (b) a small SWE-bench Verified subset run through each worker only if budget allows, recording date, model version, quantization, hardware and harness; (c) acceptance products: EditSutra-style SaaS (spec to TESTED) and one business automation (workflow generated, dry-run tested, executed with approval gate).
- Today's measured baseline is only: tz test suite results (see FACTORY-AUDIT.md) and EST token savings.

## 10. Phased roadmap (no big rewrite; each phase ends with tests)
| Phase | What | Gate to continue |
|---|---|---|
| 0 | Decide licence (MIT vs Apache-2.0), add DCO, trademark note, this document approved | owner decision |
| 1 | `tzworkers` + `tz hw` + local llama-server/Ollama adapter, `llama-bench` on this M3 to replace estimates | tests pass with no worker installed |
| 2 | `tzgate` + status ladder | seeded-bad-input tests caught |
| 3 | `tzspec` + task graph + MCP server for agents | an external agent can query the nine questions |
| 4-5 | modules library + `tzfactory` | EditSutra-style app reaches TESTED unattended (or honest report of what stalled) |
| 6 | with/without benchmark published as MEASURED | numbers exist |
| 7 | Studio prototype (separate repo): spec to preview, run log, approvals | 3 design-partner users |
| 8 | Workflow engine + designer, then hosted tier | paying pilot |
Effort for 0-5: roughly 1-2 weeks focused; Studio and hosting: months, UNKNOWN.

## 11. Risks and trade-offs
1. MIT lets a competitor host Core: accepted; defend through Studio, brand, speed.
2. Overclaiming ("builds anything"): status ladder and stubs report.
3. Local 16 GB models are weak at agent loops: Mode B is draft/review help; hard work goes to external workers.
4. Benchmark data is vendor/third-party and moving; re-check before any public claim.
5. Scope: Studio plus automation plus hosting is a company, not a feature; sequence strictly by phase gates.
6. Workflow-tool licences (n8n fair-code, AGPL engines) can poison a closed product.
7. Credential-handling and outbound actions in automations are the biggest liability: approvals by default.
8. Test timing flakes under machine load (documented, thresholds unchanged).

## Sources (search 2026-11-24)
- [Qwen3-Coder-30B-A3B card](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct), [Nebius OpenHands trajectories](https://nebius.com/blog/posts/openhands-trajectories-with-qwen3-coder-480b)
- [SWE-bench Pro paper](https://arxiv.org/html/2509.16941v2), [Scale leaderboard](https://scale.com/leaderboard/swe_bench_pro_public), [Epoch review](https://epoch.ai/benchmarks/swe-bench-pro/review)
- [Terminal-Bench 2.0 paper](https://arxiv.org/pdf/2601.11868), [tbench.ai](https://tbench.ai), [Codesota aggregate](https://www.codesota.com/benchmark/terminal-bench)
- [willitrunai estimator](https://willitrunai.com/can-run/qwen-3-coder-30b-a3b-on-m4-16gb), [modelfit](https://modelfit.io/models/qwen3-coder-30b-a3b/)
