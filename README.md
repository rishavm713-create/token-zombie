<div align="center">

<img src="docs/img/brand-hero.svg" alt="TOKEN ZOMBIE — Make every single token count" width="760">

# MAKE EVERY SINGLE TOKEN COUNT.

### AI AGENT RESOURCE INTELLIGENCE & WORKFLOW CONTROL FOR CLAUDE CODE

**STOP THE WASTE. CONTROL THE SWARM. PROTECT THE WORKFLOW.**

[🌐 Product Website](https://rishavm713-create.github.io/token-zombie/) · [⚡ Install](#-get-started) · [🧭 Feature Map](#-the-control-layer) · [🎨 Design System](docs/DESIGN-SYSTEM.md) · [🗺 Roadmap](docs/ROADMAP.md) · [🛠 Engineering Audit](docs/AUDIT.md) · [⚖ Competitive Positioning](docs/COMPETITIVE-POSITIONING.md) · [🚀 Launch Kit](docs/LAUNCH-KIT.md)

![Claude Code](https://img.shields.io/badge/Claude%20Code-supported-7CFF9B?style=flat-square&labelColor=111812)
![Local first](https://img.shields.io/badge/LOCAL--FIRST-no%20telemetry-7CFF9B?style=flat-square&labelColor=111812)
![MIT](https://img.shields.io/badge/license-MIT-7CFF9B?style=flat-square&labelColor=111812)

</div>

> **Understand where your AI coding-agent context goes — and keep work recoverable.**
>
> TOKEN ZOMBIE is a **local-first Claude Code token-optimization and agent-workflow control layer**. It tracks resource signals, surfaces repeated or oversized work, supports recoverable tool-output trimming, and helps preserve project continuity between sessions.
>
> **Resource visibility · Context optimisation · Agent signals · Session continuity**
>
> Unlike tools focused only on shell-output compression or persistent memory, TOKEN ZOMBIE brings these operational signals together in one developer-controlled workflow.
>
### Try it in Claude Code

```text
/plugin install token-zombie --marketplace rishavm713-create/token-zombie
```

Restart Claude Code, then run:

```text
/token-zombie:tz
```

Shell form:

```bash
claude plugin install token-zombie --marketplace rishavm713-create/token-zombie
```

[Installation, verification and rollback →](docs/INSTALL.md)

<div align="center">
<img src="docs/img/dashboard.png" alt="TOKEN ZOMBIE dashboard preview — generated demo data" width="900">
<br><sub>PRODUCT INTERFACE · Dashboard preview with demo data — not a live session or benchmark.</sub>
</div>

---

## Why it exists

Long Claude Code sessions can accumulate repeated reads, oversized tool output, duplicated agent work and context that is hard to carry forward. TOKEN ZOMBIE makes these signals easier to inspect and act on.

TOKEN ZOMBIE is designed around that wider problem:

- **See resource signals:** token activity, cache activity, agent usage and cost signals, with explicit evidence labels.
- **Find avoidable work:** repeated reads, oversized outputs and agent patterns that may indicate duplication or low value.
- **Keep work recoverable:** supported output trims retain originals for recall; checkpoints and handoffs preserve project continuity.
- **Stay in control:** local-first operation, non-blocking advice and no model calls inside core hooks.

The goal is useful, quality-preserving optimisation—not a headline savings percentage.


> **Observed single-session result:** The project owner reports one real TOKEN ZOMBIE session with **5,000,000 tokens saved**. This is a single-session observation, not a controlled multi-trial benchmark or a guarantee of typical savings. The raw session evidence, token accounting breakdown, task-quality check and TOKEN ZOMBIE overhead are being prepared for publication. See [benchmark evidence status](docs/BENCHMARK-METHOD.md#observed-single-session-result).


## ☣ The control layer

Five connected systems for Claude Code resource visibility and workflow control.

<table>
<tr>
<td width="50%" valign="top">

### ◈ 01 — RESOURCE INTELLIGENCE

Understand where context, tokens, cache activity and resource signals come from.

- 5m / 1h cache accounting
- Incremental transcript scanning
- Local SQLite usage ledger
- Thinking-token estimates
- Ledger / Priced / Mixed / Unpriced labels
- Cost estimates and usage reports
- Hook overhead benchmarking

</td>
<td width="50%" valign="top">

### ◎ 02 — AGENT & WORKFLOW INTELLIGENCE

Understand the work your agents are doing.

- Agent start / stop / ID lifecycle
- ROI flags and duplicate-work signals
- Empty, small and failed-agent signals
- Estimated stalled-agent detection
- Retry and repeated-edit counts
- Skill and instruction-load signals
- Partial idle / overlap intelligence

</td>
</tr>
<tr>
<td width="50%" valign="top">

### ⌁ 03 — CONTEXT OPTIMISATION

Reduce avoidable context while keeping supported originals recoverable.

- Large-read nudges
- Repeated-read detection
- Supported output trimming
- Original output recall
- Python AST skeleton compression
- Shadow-mode optimisation
- FTS5 / keyword retrieval
- Context Vault index

</td>
<td width="50%" valign="top">

### ⬡ 04 — WORKFLOW SURVIVAL

Protect unfinished work and make the next session easier to resume.

- Project `STATE.md`
- Session handoffs
- Checkpoints
- Resume verification
- Compaction survival checks
- Safe-point warnings
- Supervisor status
- Next-session brief

</td>
</tr>
</table>

### ▣ 05 — DEVELOPER CONTROL SURFACE

| Surface | What it provides |
|---|---|
| **In-chat toolbar & pane** | Agent, skill, token and optimisation signals |
| **Mode controls** | OFF / LITE / FULL / ULTRA |
| **Dashboard** | Local resource and workflow overview |
| **Terminal statusline** | Compact session visibility |
| **Local companion** | Local companion interface |
| **Mascot states** | Alert, excited, working, sleep and idle |
| **CLI** | Status, optimize, audit, review, handoff, checkpoint, resume, report and more |
| **Native overlay** | Implemented; visual verification pending |

## 🔁 How it works

<div align="center">

| OBSERVE | UNDERSTAND | DETECT | PROTECT | CONTINUE |
|:---:|:---:|:---:|:---:|:---:|
| Capture signals | Build context | Surface patterns | Preserve work | Resume safely |
| Hooks & ledger | Agents & skills | Waste indicators | Recall & checkpoints | Handoffs & state |

</div>

Hooks and local tools feed a shared local state model. The system surfaces evidence and suggestions; the developer stays in control of actions.

## 🖥 Product interface

<div align="center">
<img src="docs/img/dashboard-mobile.png" alt="TOKEN ZOMBIE mobile dashboard preview — demo data" width="330">
<br><sub>RESPONSIVE DASHBOARD · Demo data</sub>
<br><br>
<img src="docs/img/mascot-states.png" alt="TOKEN ZOMBIE mascot states" width="620">
<br><sub>MASCOT STATES · Idle / Working / Excited / Alert / Sleep</sub>
</div>

The in-chat toolbar and pane are implemented in the repository, but a verified public capture of the live toolbar is not published yet. [Read the interface specification](docs/PANEL.md).

## 🚦 Implementation status

| <span>IN THE REPOSITORY</span> | <span>VALIDATION REQUIRED</span> | <span>PLANNED / NOT BUILT</span> |
|---|---|---|
| SQLite ledger, hook/event tracking, handoffs, checkpoints, supported output trimming + recall, Python AST skeleton, dashboard, toolbar/pane components and CLI | Real-host checks for some hook payloads and UI behaviour; model pricing and subagent/MCP attribution; real A/B savings trials | Semantic/vector retrieval, non-Python AST compression, task-level vault index, deeper task-aware resource selection |

**Important:** “In repository” does not mean every capability is fully verified on a live host. There are no real with/without A/B trials recorded, so end-to-end savings are not proven. Other adapters are experimental rules-file outputs; Claude Code is the supported integration.

[Full roadmap](docs/ROADMAP.md) · [Implementation matrix](docs/IMPLEMENTATION-MATRIX.md) · [Engineering audit](docs/AUDIT.md) · [Known limitations](docs/LIMITATIONS.md)

## ⚡ Install

Install from the Claude Code marketplace, restart Claude Code, then run `/token-zombie:tz`.

[Full installation, verification and rollback guide →](docs/INSTALL.md)

## 🔒 Local-first by design

- Local state under `~/.claude/token-zombie/`.
- No telemetry or network calls from core hooks.
- No model calls inside core hooks.
- Advice is non-blocking; the developer stays in control.
- Supported output trims retain originals for `tz recall`.
- Local recall may contain tool output; review it before sharing diagnostics.

[Security model](SECURITY.md) · [Metrics definitions](docs/METRICS.md) · [Compatibility](COMPAT.md)

## 📚 Documentation

| Guide | Purpose |
|---|---|
| [Design system](docs/DESIGN-SYSTEM.md) | Brand colours, layout, typography and GitHub visual rules |\n| [Installation](docs/INSTALL.md) | Setup, statusline and rollback |
| [CLI](docs/CLI.md) | Command reference |
| [Toolbar & panel](docs/PANEL.md) | In-chat control surface |
| [Modes](docs/MODES.md) | OFF / LITE / FULL / ULTRA |
| [Metrics](docs/METRICS.md) | Sources, labels and calculations |
| [Roadmap](docs/ROADMAP.md) | Built, validation, planned and deferred |
| [Implementation matrix](docs/IMPLEMENTATION-MATRIX.md) | Feature-by-feature status |
| [Audit](docs/AUDIT.md) | Evidence and remaining gaps |
| [Competitive positioning](docs/COMPETITIVE-POSITIONING.md) | Competitor landscape, recent GitHub growth patterns and launch strategy |
| [Limitations](docs/LIMITATIONS.md) | Known constraints |
| [Security](SECURITY.md) | Privacy and safety boundaries |

---

<div align="center">

**TOKEN ZOMBIE · MAKE EVERY SINGLE TOKEN COUNT.**

*Observe agents. Detect waste. Optimise context. Protect the workflow.*

[Product website](https://rishavm713-create.github.io/token-zombie/) · [GitHub repository](https://github.com/rishavm713-create/token-zombie) · MIT License

</div>
