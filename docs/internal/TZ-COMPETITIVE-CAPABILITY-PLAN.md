# TOKEN ZOMBIE: competitive capability research and build plan

Research snapshot: 23 November 2026. This is a capability synthesis, not a claim that TZ should copy every product. Competitor descriptions are based on public documentation and the existing TZ research; reported vendor metrics have not been independently reproduced. Product status in this document follows the local audit and must be checked against code before implementation.

## Executive recommendation

TZ should be a single local-first Claude Code plugin that brings the useful capabilities of resource optimizers, monitors, memory/handoff tools, workflow plugins, and skill catalogs into one coherent product. Users should not need to install a pile of plugins or skills to get TZ's core experience. Specialist runtimes and remote observability services can remain optional adapters; core features should work locally through the TZ plugin and CLI.

The highest-value gaps are: (1) reliable real-host validation and quality-adjusted A/B evidence; (2) complete source attribution for costs and savings, including subagents and MCP tools; (3) task-aware retrieval over the existing vault; (4) safe, resumable workflow suggestions and cross-session conflict detection; and (5) a built-in skill finder that searches, explains, vets, and stages selected skills inside TZ. A broader skill/plugin catalog is now part of the owner's requested product direction, but should be a curated, source-aware finder rather than loading every skill into every session.

## Competitor and reference landscape

### Token and context optimisation

| Project | Publicly documented mechanism | TZ relevance | Recommended TZ treatment |
|---|---|---|---|
| RTK | Rewrites/filter shell output, has command discovery and savings reporting | Overlap: output reduction | Keep TZ's reversible trim and attribution; offer optional adapter, not a clone |
| Context Mode | Sandboxed execution, bounded output, local search and compaction resume | Strong context overlap | Add task-aware retrieval and output policies; preserve original output |
| Claude Token Optimizer | Audits, prunes and compresses startup instructions/configuration | Startup-context overlap | Make instruction audit actionable and show measured before/after size |
| Headroom | Proxy/library compression for JSON, code and prose; recovery and cache-aware behavior | Compression overlap, different integration layer | Add reversible formats only behind validation and opt-in; no mandatory proxy |
| LeanCTX | Multiple read modes, structured/code-aware reads, audit and dashboard | File-reading overlap | Add task/file read profiles and per-mode evidence, starting with safe common formats |
| Token Optimizer (alexgreensh) | Checkpoint/restore, quality score, skills/MCP audit, status bar and delta reads | Broad workflow overlap | Improve checkpoint restore, quality evidence, and skills/MCP inventory; do not import code |
| Magic Compact | Moves large outputs out of active context and retrieves them later | Direct overlap with spill/recall | Ensure spill/recall is lossless, searchable and surfaced as measured savings only when supported |
| PX Pipe | Experimental image representation of context | Research idea | Do not build absent rigorous task-quality and tokenization evidence |
| Local-Splitter | Evaluates local routing, compression, semantic cache, local drafting, structured intent, batching/cache | Methods research | Benchmark applicable tactics independently; avoid a bundled provider proxy initially |
| ACON | Learns compression guidelines from successful and failed trajectories | Research method | Consider only after TZ has consented, labelled task-quality datasets and reproducible evals |

### Usage and observability

| Project | Publicly documented mechanism | TZ relevance | Recommended TZ treatment |
|---|---|---|---|
| ccusage | Reads local logs for session/day/model usage and pricing | Direct usage reporting overlap | Keep local parser; compare totals and expose source/provenance |
| Claude Code Usage Monitor | Live burn rate, forecasts and quota display | Forecast/status overlap | Improve host quota support and reset-time provenance |
| ccstatusline | Status line with cost, context, cache and forecasts | UI overlap | Keep compact status surface; avoid duplicating every metric |
| Claude Code Router | Routes requests across models/providers with fallback and logs | Model selection overlap | TZ should advise first; only route through explicit, user-configured adapters |
| ai-observer | OTLP collection, database/dashboard and telemetry queries | Export/analytics overlap | Add optional OTLP export with local-only default and explicit opt-in |
| claude-code-otel | Exports telemetry to Prometheus/Grafana style systems | Team observability overlap | Interoperate via OpenTelemetry rather than build a full team backend |
| Langfuse integration | Traces model turns, tool spans and evaluations | Trace/eval overlap | Optional redacted export adapter; never silently transmit prompts |

### Memory, handoff and workflow

| Project | Publicly documented mechanism | TZ relevance | Recommended TZ treatment |
|---|---|---|---|
| Claude-Mem | Persistent observations, indexed retrieval and progressive disclosure | Memory overlap | Keep TZ's local recoverable vault; add task-scoped retrieval, not a replacement observer LLM |
| Hermes Agent | Context compression, output pruning and agent lifecycle/fallback patterns | Context/agent overlap | Improve deterministic fallback and lifecycle states |
| Caveman | Proxy-based context trimming, shadow/canary and recovery concepts | Trim/rollout overlap | Keep shadow mode; promote only with human-controlled evidence gates |
| Agent Trail | Agent/transcript event parsing and attribution patterns | Ledger overlap | Strengthen transcript reconciliation and unknown-vs-zero handling |
| Token Dashboard | Incremental transcript scanning | Accounting overlap | Maintain offset-based incremental scan; expose provenance and recover from rotations |
| REMvisual/claude-handoff | Handoff chain and compact/swap workflow | Continuity overlap | Add linked handoff IDs and verify continuation completion |
| vasilispapg/claude-handoff | Offline JSONL-to-handoff conversion and redaction | Continuity/privacy overlap | Add import/export with redaction preview |
| marcj/handover | Living work status and handover workflow | Continuity overlap | Keep lightweight STATE/handoff format; avoid a token-spending daemon |
| Superpowers | Brainstorm, plan, implement/test, review skill workflow | Workflow reference | Offer optional workflow templates and evidence gates; don't force a methodology |
| Ponytail | Minimal implementation and review guidance, cost visibility | Coding quality and cost overlap | Add measured task-level quality/cost reporting; keep prompts modular and opt-in |
| gstack | Role-oriented workflows and skill effectiveness lessons | Workflow/evaluation overlap | Measure whether optional workflows improve pass rate per resource |
| Karpathy Guidelines / Andrej Karpathy Skills | Concise coding-agent behavioral rules (simplicity, think first, focused edits) | Instruction quality reference | Offer a small optional skill/rule pack; not a product feature or competitor parity target |

### Agent platforms and orchestration

| Project | Publicly documented mechanism | TZ relevance | Recommended TZ treatment |
|---|---|---|---|
| Ruflo / claude-flow | Plugin/MCP surface for agents, swarms, workflows, memory and monitoring | Broad orchestration overlap | Learn from resumable workflows and audit; do not reproduce its large runtime/tool surface |
| Oh My ClaudeCode | Claude Code plugin with specialist agents and multi-agent workflows | Workflow/agent overlap | Add safe task decomposition and recommendations; keep execution native to host |
| T3 Code | Cross-agent control plane with clients, remote access, worktrees and review | Adjacent control-plane product | Integrate/export status; do not turn TZ into a remote agent desktop |
| OpenAI Agents SDK | Handoffs, tracing and guardrails for custom agent apps | Adapter/reference | Use concepts for traceability and guardrails; no need to embed the SDK in TZ |
| Claude Agent SDK | Build Claude-powered agents and custom applications | Host/integration reference | Track supported host signals and expose an adapter only where supported |
| smolagents | Lightweight code-first agent framework | Adjacent runtime | Treat as a future adapter target if multi-runtime demand appears |
| Microsoft Agent Framework | Build and coordinate agents and workflows | Adjacent runtime | Prefer standard telemetry/skill interfaces over bespoke framework support |
| Semantic Kernel | Connect models, tools and workflow orchestration | Adjacent runtime | Same: standards-based adapter only if demand warrants |
| DeepAgents | Hierarchical, stateful agent workflows | Orchestration reference | Adopt resumability and bounded state concepts, not framework dependency |
| OpenClaw | Multi-agent runtime and integrations | Adjacent runtime | Consider only through a narrow adapter and security review |

### Skill and plugin ecosystems

| Project/catalog | What it contributes | Recommended TZ treatment |
|---|---|---|
| Anthropic Skills and official plugin marketplace | Skill folders and plugins containing commands, agents, hooks, skills and MCP configuration | Inventory installed components, detect overlap/risk, and respect native plugin installation |
| Everything Claude Code | Broad pack of skills, agents, hooks, commands, rules, memory and optimization workflows | Make TZ able to audit/profile it; do not absorb its whole pack |
| Matt Pocock's Skills | Composable engineering skills | Inventory/measure use and support skill effectiveness reporting |
| Karpathy Skills | Focused coding guidance | Optional rule profile with explicit user choice |
| Vercel Agent Skills and `skills` CLI | Skill format, discovery/install/update and broad agent-path support | Build a TZ skill finder with search, compatibility, provenance, permission review, preview, and user-approved install/update |
| Google, OpenAI, Hugging Face, GitHub Copilot skill collections | Provider/community-specific domain and workflow skills | Inventory compatible formats and report provenance; load on demand |
| Addy Osmani Agent Skills, UI UX Pro Max, Impeccable, Claude SEO, Humanizer, Planning with Files | Specialized software, design, writing, SEO and planning skills | Treat as examples of a long tail; support detection, scope, usage and outcome measurement, not feature-by-feature cloning |
| Antigravity Awesome Skills, Agentic Awesome Skills, n-skills, Skills Manager | Large skill libraries or cross-agent skill/plugin management | Index their public catalogs in the TZ finder; show source, date, compatibility and risk, then preview before user-approved install |
| Claude Plugin Radar, Awesome Claude Skills, Awesome Coding Agent Skills, Awesome Agent Orchestrators | Discovery catalogs, not execution products | Use as candidate sources for the TZ skill/plugin finder; deduplicate and track source/date/provenance |

## Cross-cutting methods worth evaluating

These are techniques, not necessarily products to copy:

1. **Progressive disclosure:** keep only short skill metadata visible until a task selects a skill; load references/scripts on demand.
2. **Bounded tool output:** cap noisy output, persist the original, return a concise searchable summary and recovery handle.
3. **Incremental parsing:** scan only appended transcript bytes, ignore incomplete final records, deduplicate by stable event/message ID.
4. **Cache-aware accounting:** report input, output, cache-read and cache-write separately, use model-specific prices and label unknown plan-equivalent spend.
5. **Task-aware routing:** recommend model, workflow, read limits and agent count from task class; show estimated tradeoffs and leave final choice with user.
6. **Safe parallel work:** isolate worktrees, define file ownership, prevent duplicate assignments, and require review before applying cross-agent changes.
7. **Checkpoint/restore:** keep a compact continuation state with done/left/next, link it to the source session and verify the next session consumed it.
8. **Quality-adjusted evaluation:** same task, model, settings and acceptance checks; measure tokens, cost, latency, retries, pass rate and TZ overhead over multiple trials.
9. **Optional telemetry export:** local-first by default; opt-in redacted OTLP/trace export with preview and no prompt content unless explicitly enabled.
10. **Skills lifecycle:** search across curated catalogs, inspect provenance/license/permissions, preview content, check compatibility and context footprint, stage an install, then install/update only with user approval; track activation, version and outcome.
11. **Policy gates:** preflight validation before risky tool use, clear reason, reversible behavior, and never silently mutate provider/model routing.
12. **Security boundary:** skill/plugin scripts execute with agent permissions; inspect source, permissions, network use and licensing before reuse or automatic execution.

## TZ implementation status and additions

The audit and handoffs already record output trim with recall, shadow mode, FTS search, usage/cost accounting, cache split, hook/agent tracking, ROI advice, compaction checks, handoff/resume, dashboard, CLI, SQLite ledger and Python AST compression. Existing features must be re-verified before claims are updated; old audit files have conflicting test counts and some status tables are stale.

### P0 — evidence and accounting (do first)

- Verify a current full suite and plugin suite; reconcile docs to actual code and latest run.
- Run host verification for registered hooks and payloads, including compaction summary support.
- Wire each optimization event into ledger and dashboard with source, method, confidence and recoverability.
- Complete subagent and MCP attribution where host records allow; show `UNAVAILABLE` instead of zero when they do not.
- Define and run approved controlled A/B trials; report quality/pass rate, cost, tokens, time, overhead and variance. No savings marketing claim without this.

### P1 — context and continuity

- Add task/project/file/tool indexing to the existing vault; support progressive search → excerpt → full original.
- Add handoff chain IDs and continuation-consumed/completed signals.
- Add supported language readers/compressors incrementally, each fail-open and reversible; start with languages demanded by real TZ users.
- Improve churn signals and instruction-conflict reporting with explainable evidence and low false-positive rate.

### P2 — workflow/coordination

- Expand current mode advice into explainable task profiles for model, read limits, skill packs, and agent count.
- Add duplicate-work and overlapping-file warnings across sessions; optionally use user-controlled worktree isolation.
- Add workflow templates for plan/build/test/review with explicit checkpoints; keep skill choice and agent spawning opt-in.
- Track skill activation, input footprint, task outcome and quality; do not load entire large skill catalogs into every prompt.

### P3 — built-in skill finder and interoperability

- Ship `tz skills find <query>` over a curated, refreshable catalog assembled from the listed public skill/plugin sources.
- Rank by task fit, host compatibility, maintenance signal, license/provenance and declared permissions; never rank on star count alone.
- Show skill instructions and scripts in a safe preview; flag network, shell, filesystem and secret access before install.
- Support staged, reversible installation into TZ's plugin-managed skill directory, with explicit user confirmation and uninstall/restore.
- Load selected skill details on demand, not the entire catalog; record which skill was used, token footprint estimate and task outcome.
- Keep authored TZ-native workflows for planning, execution, testing, review, security, memory and context optimization so common work needs no third-party skill.

- Add opt-in OTLP export and trace adapters with field-level redaction preview.
- Add adapters for other agent hosts only after defining a stable event schema and confirming user demand.
- Consider semantic/vector memory only if FTS/task-index evaluation demonstrates a retrieval gap; measure extra storage, latency and token cost.
- Consider model routing only as user-approved advice or through a separately configured adapter; never proxy prompts by default.

## Boundaries for the one-TZ product

- Loading every public skill into context or claiming to replace every specialist skill's domain expertise.
- Copying source code without checking its license and required notices. Use permissively licensed code only after source review, security review and attribution; otherwise learn from documented behavior and implement independently.
- A 100+ agent swarm runtime or automatic agent spawning.
- Silent cloud telemetry, prompt export, or provider/model switching.
- Lossy code compression without syntax/semantic validation and recovery.
- Vector DB, remote server, or always-on LLM memory worker before local retrieval is proven insufficient.
- Claiming competitor parity from README descriptions or copying self-reported star/savings figures.

## Suggested architecture

1. **Core local event schema:** session, model, usage, cache, hook, tool, agent, skill, optimization, checkpoint, retrieval and outcome records; versioned and privacy-safe.
2. **Adapters:** Claude Code first; normalize host events into the schema. Later adapters consume the same contract.
3. **Policy engine:** deterministic rules for caps, safe trim, churn alerts, task profiles and gates. No model call required for baseline operation.
4. **Recoverable context store:** content-addressed originals plus indexes and provenance. Search results identify what was omitted and how to restore it.
5. **Surfaces:** CLI, compact companion dashboard, native statusline integration, and optional telemetry exporters.
6. **Evaluation harness:** fixed task suite, clean worktrees, frozen model/settings, task acceptance tests, per-trial raw artifacts and quality-adjusted summary.

## Source references

- [TZ competitive intelligence](COMPETITIVE-INTELLIGENCE.md) and [TZ audit report](COMPETITIVE-AUDIT-REPORT.md).
- [T3 Code repository](https://github.com/pingdotgg/t3code) and [FAQ](https://github.com/pingdotgg/t3code/blob/main/docs/user/faq.md).
- [Ruflo workflow plugin](https://github.com/ruvnet/ruflo/blob/main/plugins/ruflo-workflows/README.md) and [status guide](https://github.com/ruvnet/ruflo/blob/main/docs/STATUS.md).
- [Oh My ClaudeCode](https://github.com/Yeachan-Heo/oh-my-claudecode).
- [OpenAI Agents SDK handoffs](https://openai.github.io/openai-agents-python/handoffs/) and [guardrails](https://openai.github.io/openai-agents-python/guardrails/).
- [Anthropic official plugin structure](https://github.com/anthropics/claude-code/blob/main/plugins/README.md) and [official marketplace](https://github.com/anthropics/claude-plugins-official).
- [Vercel agent skills](https://github.com/vercel-labs/agent-skills), [skills CLI](https://github.com/vercel-labs/skills), and [supported agent paths](https://github.com/vercel-labs/skills/blob/main/docs/agents.md).
- [Everything Claude Code](https://github.com/affaan-m/everything-claude-code).
- [Agent skills specification dataset paper](https://arxiv.org/abs/2608.10906), [ACON paper](https://arxiv.org/abs/2510.00615), and [Local-Splitter paper](https://arxiv.org/abs/2604.12301).

