# TZ Studio: vision (single source of truth)

**Status: UN-PARKED 2026-11-25 by the owner (engine v0 only).** Engine skeleton built in ~/tz-studio (separate folder, own git repo, zero dependencies, not in this repo): project memory, plan generation, task graph, Claude Code streaming, approval gates, verify, checkpoints, budget cap, playbooks, learned-rule loop, local web UI. Tested with a fake Claude (suite passes) and one tiny live Claude Code run. Not built: browser inspection, deploy/launch, SaaS end-to-end, any reliability claim. EditSutra and revenue still come first; use real products as Studio's tests, and promote learned rules only after a test.
The Core prerequisites in section 9 remain open; Studio uses Core read-only via its CLI.
Written 2026-11-25 from two owner conversations. Every estimate, market claim, price and reliability claim here is **UNVERIFIED** unless marked otherwise. Licensing and boundary decisions live in [OPEN-CORE-DECISION.md](OPEN-CORE-DECISION.md).

## 1. Decisions (fixed)
1. Studio is a paid, closed-source product in its own repo. Core stays MIT, local-first, and must never depend on Studio. Studio may use Core through stable CLI/JSON/MCP contracts.
2. Studio is not a competitor or replacement for Claude Code. Claude Code is its execution engine. No own coding model, no chatbot, no agent framework for its own sake.
3. Two products only: TZ Core (free) and TZ Studio (paid). No other tiers.
4. Studio is not a dashboard of token counts. Its value is managing a whole project from idea to verified delivery.

## 2. Vision
Someone describes an outcome in plain language and Studio guides it to a deliverable. They need not choose languages, frameworks, databases or hosting. Aims: (a) make creation reachable for non-programmers (later, needs a mature experience); (b) make developers spend time on decisions, not avoidable fixes, context management and manual coordination; (c) let a small team or agency run several projects, repos and workflows in one controlled place.
Slogan candidate: "You bring the idea. Studio manages the journey from research to finished product." It is about removing the need to know how to vibe-code, not about generating more code.

## 3. Pipeline
idea → research → planning → design → development → testing → security → deployment → launch → maintenance.
| Stage | Studio does |
|---|---|
| Idea | Takes the prompt and project type |
| Research | Finds existing open-source projects, libraries, APIs, models, engines; compares licences and maintenance; reuses before rebuilding |
| Planning | Requirements, features, milestones, architecture, data structures, task graph |
| Design | Design system, layouts, prototypes, preview and inspect, iterate without the user fixing UI by hand |
| Development | Specialised tasks (frontend, backend, data, integrations, game systems, creative tooling) executed through Claude Code |
| Testing | Runs tests, checks the UI, reproduces failures before fixing, verifies fixes |
| Security | Reviews credentials, permissions, dependencies, data handling, deploy risk |
| Deployment | Build, deploy config, docs, install and release assets |
| Launch | Positioning, landing page, docs, pricing, launch material |
| Maintenance | Issue tracking, dependency updates, continued improvement |

## 4. What it should eventually support
SaaS and internal tools; business automation and AI agents; games (e.g. Unreal Engine 5); creative apps such as EditSutra; books and publishing; websites and launch; enterprise software. These are playbooks on one engine, not separate products.

## 5. Core ideas
- **Rules and playbooks engine.** Each project gets a structured execution contract, not a vague prompt. Rule groups: research, architecture, design, development, testing, security, delivery. Playbooks differ by type: SaaS (auth, database, deploy), games (engine, assets, performance, builds), creative tools (media processing, export), books (source checks, editing, publishing), enterprise (access control, audit, compliance).
- **Open-source discovery and reuse.** Check licences (`tz reuse` already audits), prefer reuse, justify any rebuild.
- **Specialised agent orchestration.** Research, design, development, QA, security and launch agents, all executing through Claude Code. Independently verifiable tasks; working code preserved.
- **Visual workflows.** Tasks, dependencies, agents, progress, run history, rollback via Core checkpoints. Workflow = JSON graph (trigger, condition, action, branch, loop, delay, approval, retry, error edge); own small engine, React Flow (MIT) for the canvas.
- **Quality assurance.** Tests after each milestone, browser and visual checks, nothing reported complete unless verified.
- **Human approval gates.** Destructive, sensitive or irreversible actions (credentials, deletes, deploys, outbound messages, money) always need explicit approval. Secrets never in specs or logs.
- **Core reuse.** Context optimisation, usage ledger, session state, handoffs, hooks, checkpoints. Studio adds project intelligence, orchestration, research, design and browser inspection, QA/release workflows, deploy and launch management.

## 6. Layers of work (build order when resumed)
| Layer | Scope |
|---|---|
| A. Technical foundation | Launch and stream Claude Code, project record, task list, approvals UI, Core data feed |
| B. Complete SaaS production workflow | Research, spec, design, build, test, security, deploy, website, launch for one product type, proven end to end |
| C. Later specialised workflows | Automation, games, creative tools (EditSutra as second demo), books, enterprise governance and teams |
Demo target after B: a non-technical person describes a SaaS idea and gets a researched, designed, built, tested, launchable product. Then repeat for a creative app. Do not start all categories at once.

## 7. Estimates (UNVERIFIED engineering guesses, not commitments)
| Item | Estimate | Note |
|---|---|---|
| Layer A, thin foundation | 3-7 days (owner chat) / 2-4 weeks (this session) | Differs by what "foundation" includes; assumes Core's JSON output is usable, not checked |
| Useful production MVP (6 items in section 8) | 2-3 weeks | Same assumption |
| First specialised workflows | 3-5 weeks | |
| Layer B, full SaaS demo | about 3-5 months | |
| Layer C and hosted/team features | months, open-ended | |
| Pay test (section 10) | 1-2 weeks | Before any large build |

## 8. First release scope (when resumed)
Project creation; research and planning; visual task view with approvals; Claude Code execution and session management; design preview, test run and fix loop; delivery (docs, build, website and launch assets). No large workflow canvas first, no six parallel products.

## 9. Prerequisites and dependencies
- Core roadmap items 1-4 must be class 1 first: quiet-machine rerun of the suite and timing tests (F1-F4); resume for killed agent runs (A6); gate auto-detect lint/type/audit (A7); parallel worktree coordination and task deps (A9, A10). See MASTER-BUILD-ROADMAP.md.
- Open-core phases 0-5 proven (OPEN-CORE-DECISION.md section 10); Studio prototype is phase 7, gate "3 design-partner users".
- Core's interfaces actually usable by Studio: unchecked.
- Owner decisions pending: Core licence MIT vs Apache-2.0, DCO, trademark claim.
- Avoid AGPL libraries in Studio; keep an SBOM.

## 10. Risks and unresolved questions (all open, none established)
1. **Market demand.** Unproven. A reported survey share of Claude Code users (a 65.5% figure was quoted, not verified) does not show willingness to pay. Competitors exist (Lovable, Replit, Cursor, others). Validate: 10 Claude Code developers or founders, 5 use it on real projects, test paid early access, not compliments.
2. **Pricing.** Hypothesis only ($19-29 individual, $49-99 professional per month). Unknown until interviews; publish nothing.
3. **Anthropic terms.** Unchecked whether a paid product may drive customers' Claude Code, and whether customers must bring their own login or API key. Resolve before any pricing or build.
4. **Unattended reliability.** End-to-end hands-off building is unproven even for Core (needs an EditSutra-style app reaching TESTED, or an honest stall report). Never promise one-click production-ready software.
5. **Cost per project.** A full pipeline run is token-heavy; needs per-stage budgets and caps.
6. **Claude Code interface drift.** Depends on its CLI, stream output and hooks; needs a thin adapter and version check.
7. **Scope.** "A company, not a feature." Strict phase gates.
8. **Core hosting.** MIT lets others host Core; defence is Studio, brand and speed.
Initial audience if resumed: developers, technical founders, agencies. Non-technical users are a later ambition.

## 11. Non-goals
No Claude Code clone, no general chatbot, no agent framework for its own sake, no rebuilding of open-source tools that work, no dependence on a proprietary model where open source suffices, no unverified one-click claims, no simultaneous start of all product categories.

## Update 2026-11-26: quality loop built (tz-studio, branch studio-foundation)
`studio quality` runs SkillEvaluator tier 1 as a gate, triages findings (safe-fix / false-positive / risky), and fixes the safe ones with cheaper Claude workers in folder copies; the router re-runs the gate against each ticket's eval.md, a deterministic watchdog flags stuck workers, and risky or false-positive items wait for a named human. Bounded by retries, 5 rounds, early stop and budget. Tested with fakes; real-run results are in the tz-studio handoff. Stageshow `--gate` is wired but not run (needs `npm install`, owner's OK).
