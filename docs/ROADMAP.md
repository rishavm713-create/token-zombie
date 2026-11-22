# TOKEN ZOMBIE Roadmap

This roadmap separates shipped capabilities from validation work and future plans. Status is based on the repository's implementation and audit documents, not marketing intent.

Last reviewed: 2026-11-22.

## Available in the repository

These capabilities have implementation and test coverage in the current codebase. Some still need real-host verification.

- Hook ledger across 18 registered Claude Code events.
- Local SQLite ledger, alerts, outcomes and Context Vault index.
- Agent lifecycle signals, ROI flags and estimated stalled-agent detection.
- Incremental transcript scanning and cache-window accounting.
- Token/resource labels that distinguish measured, estimated, mixed and unavailable data.
- Handoffs, checkpoints, project state and resume verification.
- Output trimming in supported paths, with recoverable originals through `tz recall`.
- Python AST skeleton compression with validation and fail-open behaviour.
- Shadow-mode output optimisation advice.
- Dashboard, toolbar components and CLI modes.
- Install, check, dry-run, restore and uninstall workflows.

See [Implementation Matrix](IMPLEMENTATION-MATRIX.md) and [Audit](AUDIT.md) for evidence and test references.

## In development / validation priorities

These are areas where code exists but the complete real-world behaviour or measurement is not yet established.

1. **Real-host verification:** verify hook payloads and toolbar behaviour against the supported Claude Code host.
2. **Real A/B measurement:** run controlled with/without trials, recording resource use, TOKEN ZOMBIE overhead and task-quality checks. No real trials are currently recorded.
3. **Resource attribution:** improve model pricing coverage and subagent/MCP cost attribution.
4. **Agent intelligence:** improve idle, overlap, interruption and outcome signals where the host exposes reliable evidence.
5. **Measurement quality:** make reported savings distinguish verified avoided consumption from estimates and overhead.
6. **Onboarding and documentation:** make install, first-run verification and recovery straightforward.

These are priorities, not claims that every item is already implemented.

## Planned capabilities

The following are future directions, not shipped features:

- Semantic/vector retrieval if keyword retrieval proves insufficient.
- AST-aware compression for languages beyond Python.
- A task-level Context Vault index.
- Deeper task-aware resource and context selection.
- More complete orchestration and intervention, subject to host capabilities and explicit user control.

## Experimental compatibility

Claude Code is the supported integration. Other adapters (Codex, Cursor, Windsurf, Gemini, Cline, Roo and Antigravity) are experimental rules-file outputs only; they do not currently provide equivalent hooks or statusline integration.

See [Compatibility](../COMPAT.md).

## Deliberately out of scope

- A nine-tab UI.
- A clone of RTK or a full replacement for Claude-Mem.
- Automatic agent spawning.
- Vector memory before keyword retrieval demonstrates a real limitation.
- Lossy source-code compression.
- Blocking developer tools merely to reduce token usage.


## Feature-by-feature status at a glance

| Area | Available in repository | Validation / gap |
|---|---|---|
| Resource accounting | SQLite ledger, incremental scan, cache split, labelled usage states | Pricing and agent/MCP attribution remain partial |
| Agent intelligence | Lifecycle signals, ROI flags and heuristic stall/duplicate signals | Idle, overlap, interruption and outcome confidence need more validation |
| Context optimisation | Supported output trim + recall, Python AST skeleton, shadow advice, keyword index | Other languages and task-level indexing not built |
| Workflow continuity | Project state, handoffs, checkpoints and resume verification | Host-specific compaction and resume paths need real-session checks |
| Developer control | CLI, dashboard and toolbar/pane components | Public live-toolbar capture and some host UI checks pending |
| Measurement | Ledger, overhead accounting and A/B harness code | No real end-to-end A/B trials recorded |


## How priorities change

A capability moves from planned to in-development only when implementation work starts. It moves to available only when the code and relevant tests support the claim. Host-dependent features remain marked unverified until tested on the actual host. Savings claims require real A/B evidence and quality checks.

For known gaps, consult [Limitations](LIMITATIONS.md) and [Host Verification](HOST-VERIFY.md).

## Competitive-audit priorities (added 2026-11-23)
Order from `COMPETITIVE-GAP-ANALYSIS.md`: P0 real A/B trial and live-host verification (owner-run); P1 MCP/tool-schema cost signal, real-toolbar demo GIF, handoff chain id; P2 official usage view, JS/TS skeletons, rework scoring, CI-failing startup audit; P3 non-Claude adapters. Rejected: nine-tab UI, RTK clone, Claude-Mem replacement, auto agent spawning, early vector memory, lossy compression, blocking tools.
