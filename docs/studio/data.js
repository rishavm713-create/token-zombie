'use strict';
// Rule: "working" needs evidence that does not depend on the fake Claude used by the test suite.
(function (root) {
  const STATUS = {
    working: { label: 'Working', meaning: 'Implemented and verified by real execution, within the stated limits.' },
    partial: { label: 'Partial', meaning: 'Code exists, but it is limited or not fully verified (for example tested only with a stand-in for Claude).' },
    planned: { label: 'Planned', meaning: 'Part of the product blueprint. Not implemented yet.' },
    demo: { label: 'Demonstration', meaning: 'Illustrative, simulated content on this website. Nothing runs on a backend.' }
  };

  const DOMAINS = ['Discover', 'Define', 'Design', 'Build', 'Assure', 'Ship and maintain', 'Control', 'Specialist packs'];

  // [id, name, domain, status, what Studio is designed to do, what exists today, what is missing, [files]]
  const CAPABILITIES = [
    ['intake', 'Idea intake', 'Discover', 'partial', 'Turn a plain-language idea into a short brief, asking at most five essential questions.', 'Brief and PRD files are written; tested with a stand-in for Claude, with a rule-based fallback.', 'Prompt quality with real Claude is unmeasured.', []],
    ['research', 'Product and market research', 'Discover', 'partial', 'Research competitors and markets, link every claim to a source and a date.', 'One real Claude research run succeeded. No fact in it was marked confirmed; vendor pages were not opened.', 'Source verification, repeat runs, tighter tool scope.', []],
    ['discover', 'Repository discovery', 'Discover', 'partial', 'Find existing repositories, libraries and tools, check licence and source, and score them.', 'Discovery and scoring code, tested with injected network and clone responses.', 'Live search path is not covered by tests.', []],
    ['skills', 'Skills discovery and licence gate', 'Discover', 'partial', 'Find Claude Code skills, review their licence, and enable them with approval.', 'Skills manager and licence gate exist with tests.', 'Not connected to the command line; nothing enforces the enabled list yet.', []],
    ['registry', 'Capability registry and licence metadata', 'Discover', 'working', 'Keep a catalogue of capabilities, tools and their licences that each phase can query.', 'Catalogue loads, validates and answers queries. This is local logic with automated tests.', 'Entries are metadata. A catalogue row is not an implemented capability.', []],
    ['rea', 'Reverse-engineering investigation (external REA tool)', 'Discover', 'partial', 'Inspect an artifact or release you own, behind a named approval, and keep the results as evidence.', 'Adapter and content-bound approval gate, tested with a stand-in tool.', 'No successful real run yet.', []],

    ['prd', 'Requirements and PRD', 'Define', 'partial', 'Produce requirements and a product spec that later phases are checked against.', 'Requirements phase and PRD output, tested with a stand-in for Claude.', 'Template library and real-run quality.', []],
    ['architecture', 'Architecture and database design', 'Define', 'partial', 'Design the system, record decisions, and validate the database schema.', 'Real Claude run: first attempt failed validation, second passed after a prompt fix.', 'One passing run is not a reliability measurement.', []],
    ['plan', 'Task planning and dependencies', 'Define', 'partial', 'Break the plan into ordered tasks and run each only when its dependencies pass.', 'Dependency-aware runner with crash recovery, tested with a stand-in for Claude.', 'No real end-to-end run; no visual graph.', []],

    ['design-system', 'UI/UX and design systems', 'Design', 'partial', 'Generate design tokens and component guidance with accessibility contrast checks.', 'One real Claude run produced tokens with no contrast failures.', 'Component registry adapters and screen-level design review.', []],

    ['claude', 'Claude Code execution', 'Build', 'partial', 'Use Claude Code as the only coding engine for every build task.', 'Execution layer exists. Single research, architecture and design calls have run for real.', 'A full real build has not been run through the pipeline.', []],
    ['website', 'Website factory', 'Build', 'partial', 'Take an idea to a tested static website with deployment notes.', 'Template factory with headless-browser checks at three widths. A skipped browser check is reported as skipped.', 'Browser sandbox hardening is not yet verified.', []],
    ['saas', 'SaaS starter factory', 'Build', 'working', 'Generate a small application with sign-up, login and data screens, then check it.', 'Generated app was exercised in a browser on localhost: sign-up, add, edit, delete, logout, user isolation, mobile layout.', 'One template and one browser. Real entities are not yet derived from your idea. Run only code you have reviewed.', []],
    ['repowork', 'Changes to existing repositories', 'Build', 'partial', 'Work on an isolated branch and worktree, show the diff, test after approval, and leave merging to you.', 'Isolated-worktree flow with named approvals, tested offline.', 'Not yet run against a real product repository; approved tests are not fully isolated.', []],
    ['understand', 'Codebase understanding and audit', 'Build', 'planned', 'Map architecture and behaviour of an imported product, find gaps and recommend improvements.', 'Today only file, licence, branch and test-file counts.', 'Architecture analysis, gap audit and a recommendation report.', []],
    ['parallel', 'Parallel Claude Code sessions', 'Build', 'planned', 'Split work across several isolated Claude Code sessions with file ownership and merge gates.', 'Tasks run one at a time. (Studio itself was built with manually coordinated sessions, which is not a product feature.)', 'Worker pool, task contracts, merge gates.', []],

    ['testing', 'Test execution and verification', 'Assure', 'partial', 'Run each project’s tests and checks and refuse to call unverified work done.', 'Task-level checks and project test detection, tested offline.', 'Repair loop and reviewer pass.', []],
    ['browserqa', 'Browser QA', 'Assure', 'partial', 'Open the product in real browsers and test layouts and flows.', 'Headless layout checks for generated static sites only.', 'Application flows, end-to-end tests, multiple browsers.', []],
    ['debug', 'Debugging and code quality loop', 'Assure', 'planned', 'Diagnose failures, fix them, re-verify and review the result automatically.', 'Failed checks stop the run and can be retried by hand.', 'Verifier and reviewer repair loop.', []],
    ['security', 'Security controls', 'Assure', 'partial', 'Approval gates, isolation, secret handling and safe execution of generated code.', 'An internal review on 26 Nov 2026 found serious open issues. Fixes are in progress and not fully verified.', 'Verified fixes and an independent re-review before any release claim.', []],
    ['scanners', 'Secret and dependency scanning', 'Assure', 'planned', 'Run dedicated secret and vulnerability scanners and attach results as evidence.', 'Only a simple secret pattern check inside the website factory.', 'Scanner adapters and disclosure of any data they send.', []],

    ['docs', 'Documentation and delivery report', 'Ship and maintain', 'partial', 'Write documentation and a report of what passed, failed and was never verified.', 'Evidence-backed report and factory documentation, tested offline.', 'Documentation for imported products.', []],
    ['release', 'Release preparation', 'Ship and maintain', 'partial', 'Plan versions and prepare release assets. Publishing is always your action.', 'Plan and prepare steps; publish never publishes. Tested offline.', 'Releases for external repositories.', []],
    ['deploy', 'Deployment preparation', 'Ship and maintain', 'partial', 'Prepare deployment for a chosen target and require approval for anything live.', 'Dry run that writes deployment notes. Nothing is executed.', 'Provider adapters, each tested before it is offered.', []],
    ['adapters', 'Live deployment adapters', 'Ship and maintain', 'planned', 'Deploy to hosting providers after explicit approval.', 'None.', 'First tested provider adapter.', []],
    ['monitor', 'Monitoring and maintenance', 'Ship and maintain', 'partial', 'Check health, re-run regressions and propose maintenance after launch.', 'Health check, regression run and schedule record, tested offline.', 'A running scheduler, alerts and maintenance proposals.', []],

    ['approvals', 'Approvals', 'Control', 'partial', 'Pause before consequential actions and record who decided, bound to exactly what was approved.', 'Approval queue and gates work in offline tests.', 'The 26 Nov review showed gates could be bypassed. Hardening is in progress.', []],
    ['evidence', 'Evidence log', 'Control', 'partial', 'Record hashed evidence for every result.', 'Append-only log with file hashes, tested offline.', 'Evidence must be protected from the work it describes.', []],
    ['budget', 'Budget and token control', 'Control', 'partial', 'Cap spend per project, show tokens and cost per phase, and show external costs before you commit.', 'Per-project cap and per-phase metrics. Costs of four real calls were recorded.', 'No cost screen; no measurement over a full real project.', []],
    ['dashboard', 'Local dashboard', 'Control', 'partial', 'One local workspace to start projects, watch progress, read evidence and decide approvals.', 'Local web page with project overview, approve and reject, and artifact view. Data model tested.', 'Browser interface not verified end to end; accessibility not checked.', []],
    ['memory', 'Memory and session continuity', 'Control', 'partial', 'Resume any project from its files, with memory and handoffs.', 'Resume-from-files tested across separate processes.', 'Search and handoff writing.', []],
    ['core', 'Token Zombie Core integration', 'Control', 'partial', 'Use the independent Core tool for context facts, read-only. Core never depends on Studio.', 'Read-only calls observed once against real Core.', 'Feeding optimised context into builds; version contract tests.', []],
    ['portfolio', 'Product portfolio', 'Control', 'partial', 'Give every product its own memory, spec, budget, evidence and approvals under one control plane.', 'Portfolio sync, inspection and capability map, tested offline.', 'Real validation on existing products; owner budgets.', []],
    ['playbooks', 'Project-type playbooks', 'Control', 'partial', 'Adapt the lifecycle to the product type and learn rules you promote.', 'Rule files and manual rule promotion. Only website and SaaS have factories.', 'Factories for other product types.', []],
    ['licensing', 'Product licensing and activation', 'Control', 'planned', 'Local licence verification for the paid product. Terms and price are not final.', 'None.', 'Pricing decision, licence and activation.', []],

    ['automation', 'Business automation', 'Specialist packs', 'planned', 'Plain-language automations with safe test runs, approvals and run history.', 'Playbook rules only.', 'Triggers, actions, logs.', []],
    ['media', 'Video and audio processing', 'Specialist packs', 'planned', 'Editing automation for video and audio products.', 'No code in Studio.', 'Media pack.', []],
    ['motion', 'Captions, motion and effects', 'Specialist packs', 'planned', 'Captions, motion graphics and effects workflows.', 'No code in Studio.', 'Motion pack.', []],
    ['image', 'Image and creative design', 'Specialist packs', 'planned', 'Thumbnails, creative direction and image generation.', 'No code in Studio.', 'Image design pack.', []],
    ['writing', 'Scripts and story', 'Specialist packs', 'planned', 'Hooks, structure, pacing and scripts.', 'No code in Studio.', 'Writing pack.', []],
    ['social', 'Social publishing operations', 'Specialist packs', 'planned', 'Publishing workflows with approval before anything is posted.', 'No code in Studio.', 'Social pack.', []],
    ['outreach', 'Client research and proposals', 'Specialist packs', 'planned', 'Prospect research, positioning, pitches and proposals.', 'No code in Studio.', 'Outreach pack.', []],
    ['ads', 'Advertising creative', 'Specialist packs', 'planned', 'Ad concepts, presenters and voiceovers.', 'No code in Studio.', 'Ad creative pack.', []],
    ['publishing', 'Manuscript publishing', 'Specialist packs', 'planned', 'Manuscript, screenplay and book publishing workflows.', 'No code in Studio.', 'Publishing pack.', []],
    ['game', 'Game design and Unreal workflows', 'Specialist packs', 'planned', 'Game design, prototyping, asset pipelines, testing and packaging.', 'No code in Studio.', 'Game engine adapter.', []]
  ].map(([id, name, domain, status, goal, today, gap, files]) => ({ id, name, domain, status, goal, today, gap, files }));

  // Lifecycle stage: [name, what happens, you get, gate, [capability ids]]
  const stage = ([name, what, output, gate, caps]) => ({ name, what, output, gate, caps });
  const WORKFLOWS = {
    new: { title: 'Build a new product', lead: 'Describe an idea. Studio carries it to a maintained product.', stages: [
      ['Idea', 'You describe the product in plain language. Studio asks only essential questions.', 'Product brief', 'You confirm the brief', ['intake']],
      ['Research', 'Markets, competitors, existing repositories, skills and tools.', 'Sourced research notes', 'None', ['research', 'discover', 'skills']],
      ['Requirements', 'Scope, users, features and acceptance criteria.', 'PRD', 'You accept the scope', ['prd']],
      ['Architecture', 'System design, database, decisions and task graph.', 'Architecture and schema', 'You accept the design', ['architecture', 'plan']],
      ['Design', 'Design tokens, components and screens.', 'Design system', 'You accept the look', ['design-system']],
      ['Development', 'Claude Code builds task by task; later in parallel isolated sessions.', 'Working code with checkpoints', 'Approval for risky actions', ['claude', 'website', 'saas', 'parallel']],
      ['Testing', 'Tests, browser QA and fixes.', 'Test evidence', 'Failures stay failures', ['testing', 'browserqa', 'debug']],
      ['Security', 'Secrets, dependencies, permissions and review.', 'Security report', 'Open serious findings block release', ['security', 'scanners']],
      ['Deployment', 'Build and deployment preparation.', 'Deployment plan', 'Named approval for anything live', ['deploy', 'adapters']],
      ['Launch', 'Documentation, release assets and launch material.', 'Release package', 'You publish', ['docs', 'release']],
      ['Maintenance', 'Health checks, regressions, updates.', 'Maintenance log', 'Approval per change', ['monitor']]
    ].map(stage) },
    existing: { title: 'Improve an existing product', lead: 'Import a repository. Understand it first, then change it safely.', stages: [
      ['Import repository', 'Point Studio at a repository. Your checkout and current branch are not written.', 'Project record', 'None', ['portfolio', 'repowork']],
      ['Understand codebase', 'Structure, licence, tests, architecture and behaviour.', 'Codebase map', 'None', ['understand', 'core']],
      ['Audit', 'Quality, security, dependencies and user experience.', 'Audit report', 'None', ['understand', 'security', 'scanners']],
      ['Identify gaps', 'Compare what exists with what the product should do.', 'Gap list', 'None', ['understand']],
      ['Recommend improvements', 'Ranked options with effort, risk and cost.', 'Recommendations', 'You choose', ['understand', 'research']],
      ['Approve', 'Nothing changes until a named person approves.', 'Recorded decision', 'Named approval', ['approvals']],
      ['Implement', 'Claude Code works on an isolated branch.', 'Diff for review', 'You read the diff', ['repowork', 'claude']],
      ['Regression test', 'The project’s own tests run after approval.', 'Test evidence', 'Named approval to run tests', ['testing', 'repowork']],
      ['Release', 'Merge command and release preparation.', 'Release plan', 'You merge and publish', ['release']],
      ['Maintain', 'Monitoring, regressions and the next change.', 'Maintenance log', 'Approval per change', ['monitor']]
    ].map(stage) }
  };

  // Mirrors portfolio/products.json (names, packs). Use cases are illustrative.
  const PORTFOLIO = [
    ['editsutra', 'EditSutra', 'Creative software', 'Existing product', 'AI-assisted Premiere Pro editing product.', 'Import the repository, audit caption and cutting features, approve one improvement, regression-test on an isolated branch. Premiere Pro only; existing behaviour is preserved.', ['repowork', 'understand', 'media', 'motion', 'release']],
    ['token-zombie-core', 'Token Zombie Core', 'Developer tool', 'Existing product', 'Independent, MIT-licensed productivity and context tool.', 'Studio treats Core as its own product: separate repository, read-only integration, never a dependency on Studio.', ['repowork', 'core', 'testing', 'release']],
    ['token-zombie-studio', 'Token Zombie Studio', 'Platform', 'In development', 'This product-development platform.', 'Requirements, security review, tests and releases tracked as one project. Proprietary and separate from Core.', ['plan', 'approvals', 'evidence', 'budget', 'security']],
    ['websutra', 'WebSutra', 'Websites', 'Concept', 'Distinctive, professional websites.', 'Brief, research, design system, website factory, layout checks, deployment notes.', ['intake', 'research', 'design-system', 'website', 'deploy']],
    ['clientsutra', 'ClientSutra', 'Business', 'Concept', 'Help beginners and freelancers win clients.', 'Prospect research and proposal drafts, with approval before anything is sent.', ['research', 'outreach', 'writing']],
    ['designsutra', 'DesignSutra', 'Creative software', 'Concept', 'Design and improve creative assets.', 'Visual concepts, titles and thumbnail iterations against a design system.', ['design-system', 'image', 'writing']],
    ['scriptsutra', 'ScriptSutra', 'Writing', 'Concept', 'Better video and content scripts.', 'Hooks, structure and retention passes, grounded in research.', ['research', 'writing']],
    ['automationsutra', 'AutomationSutra', 'Automation', 'Concept', 'Automate social publishing work.', 'Triggers and publishing steps with test data first and approval before posting.', ['automation', 'social', 'approvals']],
    ['adsutra', 'AdSutra', 'Creative software', 'Concept', 'UGC ads and marketing creatives.', 'Ad concepts, scripts, presenter and voice workflows, reviewed before use.', ['ads', 'writing', 'image', 'media']],
    ['ai-filmmaking', 'AI filmmaking and post-production', 'Film', 'Held for later', 'Conventional shooting combined with AI-assisted production.', 'Shot planning, post-production and effects pipeline. Adds to filming, does not replace it.', ['media', 'motion', 'image', 'writing']],
    ['games', 'Unreal Engine and game development', 'Games', 'Held for later', 'Games and interactive experiences.', 'Game design document, prototype, asset pipeline, playtests and packaging through game adapters, not the SaaS flow.', ['game', 'design-system', 'testing']],
    ['rudra', 'RUDRA', 'Story IP', 'Held for later', 'Mythology-based thriller: novel, screenplay and potential game adaptation.', 'World bible, manuscript, screenplay and game-adaptation tracks kept as one separate creative IP.', ['research', 'writing', 'publishing', 'game']]
  ].map(([id, name, category, stageName, purpose, useCase, caps]) => ({ id, name, category, stage: stageName, purpose, useCase, caps }));

  // Public pages that exist today. Products without an entry have no public site; do not invent one.
  const LINKS = { editsutra: 'https://editsutra.github.io/', 'token-zombie-core': 'https://rishavm713-create.github.io/token-zombie/' };
  const CREATOR_URL = 'https://rishavm713-create.github.io/';

  const ROADMAP = [
    ['1. Trust the base', 'Verify the security fixes, re-review, protect approvals and evidence.', ['security', 'approvals', 'evidence']],
    ['2. Prove real execution', 'One full real Claude pipeline under a small budget, with measured cost.', ['claude', 'plan', 'prd', 'budget']],
    ['3. Existing-product path', 'Codebase understanding, audit and recommendations on a real repository.', ['understand', 'repowork', 'portfolio']],
    ['4. Quality layer', 'Repair loop, application browser tests, scanners, verified dashboard.', ['debug', 'browserqa', 'scanners', 'dashboard']],
    ['5. Scale out', 'Parallel sessions, skills in daily use, first live deployment adapter.', ['parallel', 'skills', 'adapters', 'monitor']],
    ['6. Specialist packs and product', 'Media, writing, game and other packs in the agreed order; licensing.', ['media', 'writing', 'game', 'licensing']]
  ].map(([name, what, caps]) => ({ name, what, caps }));

  const data = { STATUS, DOMAINS, CAPABILITIES, WORKFLOWS, PORTFOLIO, LINKS, CREATOR_URL, ROADMAP, AS_OF: '26 November 2026' };
  if (typeof module !== 'undefined') module.exports = data; else root.STUDIO = data;
})(typeof window !== 'undefined' ? window : globalThis);
