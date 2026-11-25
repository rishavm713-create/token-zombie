# TOKEN ZOMBIE — Competitive Positioning & GitHub Discovery Notes

Research snapshot: 22 November 2026. Star velocity and trending rankings are time-sensitive; treat the figures below as snapshots, not permanent popularity claims.

## Position

**Category:** AI Agent Resource Intelligence & Workflow Control.

**One-sentence description:** TOKEN ZOMBIE is a local-first resource intelligence and workflow control layer for Claude Code that makes usage and agent activity visible, surfaces avoidable work, preserves recoverable output and helps continue work across sessions.

**Core distinction:** TOKEN ZOMBIE connects resource visibility, agent lifecycle signals, context optimisation and project continuity. It should not claim to replace every memory, workflow, or shell-compression tool.

## Competitive landscape

| Project | Primary positioning | What its public presentation teaches us | TOKEN ZOMBIE's relationship |
|---|---|---|---|
| [RTK](https://github.com/rtk-ai/rtk) | Terminal-output compression and token savings; now also pipelines and a broader agent control offering | A concrete pain, a named command (`rtk gain`), broad command coverage and a measurement story | Adjacent/overlapping on output reduction; TZ's broader proposition is resource and workflow intelligence |
| [Context Mode](https://github.com/mksglu/context-mode) | Keep tool output and context consumption under control | Clear headline promise, quick install per agent, before/after explanation, benchmarks and adoption evidence | Closest context-optimisation neighbour; TZ adds agent lifecycle signals, local ledger, recoverability and project continuity |
| [Claude-Mem](https://github.com/thedotmack/claude-mem) | Persistent memory and retrieval across sessions | Strong single-job story, clear quick start, architecture and detailed docs | Complementary on continuity/memory; TZ's core is resource observability and workflow control |
| [Superpowers](https://github.com/obra/superpowers) | Structured software-development skills and workflows | Memorable philosophy, clear workflow, broad host support and easy installation | Adjacent workflow framework; TZ observes and manages resource/workflow signals rather than replacing development methodology |
| [Ponytail](https://github.com/DietrichGebert/ponytail) | Coding-agent instruction and review skill pack | Distinctive identity, clear examples, before/after evidence and multi-agent installation instructions | Adjacent optimisation at the instruction/code-quality layer; TZ focuses on operational resource intelligence |
| [Claude Token Optimizer](https://github.com/nadimtuhin/claude-token-optimizer) | Reduce Claude Code startup context and configuration size | Excellent visual before/after, one clear number and step-by-step install | Narrower context-startup optimisation; TZ covers more of the session lifecycle |

These projects solve different problems and may be complementary. Do not market them as inferior or claim feature parity without a verified, current feature-by-feature test.

## What recent high-growth repositories have in common

A GitHub Trending aggregation snapshot dated 21 November 2026 listed these weekly gains among AI coding add-ons: [Superpowers](https://github.com/obra/superpowers) (+5,995), [Ponytail](https://github.com/DietrichGebert/ponytail) (+5,435), [Everything Claude Code](https://github.com/affaan-m/everything-claude-code) (+5,411), [Matt Pocock's skills](https://github.com/mattpocock/skills) (+5,269), and [Impeccable](https://github.com/pbakaus/impeccable) (+4,349). These are third-party trend snapshots and can differ from GitHub's live counters.

Other useful examples from recent trend reports:

- [morluto/rea](https://github.com/morluto/rea): +24,966 stars in GitTrend's week 45 report. Its pitch is a striking capability — reverse-engineer software with agents.
- [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill): +10,502 in the same report. Its pitch includes independently verified, machine-readable findings.
- [Jane Street agent_skills](https://github.com/janestreet/agent_skills): reported 2,124 stars shortly after its 3 November 2026 creation in a 22 November write-up. A narrow, recognisable skill can travel when the author/brand and use case are clear.
- [rea-video](https://github.com/morluto/rea-video): reported around 2.2k stars and 318 forks in a 2-week trend article. Its output is easy to demonstrate: shot-by-shot video analysis and an HTML report.

Sources:
- [GitHub Trend — last 30 days, snapshot 21 Nov 2026](https://trend.ondo.sh/github/r/en.html)
- [GitTrend — Week 45, 2026](https://gittrend.io/weekly/2026-W45)
- [ExplainX — Jane Street agent_skills, 22 Nov 2026](https://explainx.ai/blog/janestreet-agent-skills-socratic-tutor-github-2026)
- [ExplainX — rea-video, November 2026](https://explainx.ai/blog/rea-video-reverse-engineer-any-video-shot-by-shot-agent-skill-live-ai-code-apache-2026)

## Repeatable patterns worth adopting

1. **A one-line, concrete promise.** A visitor should know the pain and outcome before scrolling.
2. **An immediate first run.** Show one install command, one verification command and one useful action.
3. **Proof before percentages.** Show real before/after traces, raw data, task-quality checks and methodology. Avoid unsourced savings claims.
4. **A visual demo that explains itself.** A short GIF/video should show the problem, intervention and result, not just a dashboard.
5. **A memorable product identity.** Keep TOKEN ZOMBIE's visual system consistent, but pair the mascot with plain technical language.
6. **Composable ecosystem fit.** Document exact compatibility and limitations. Never imply native hooks where only a rules file exists.
7. **A contributor path.** Good first issues, contribution instructions, changelog and release cadence make adoption easier.
8. **Distribution outside GitHub.** A repository does not become viral by README edits alone. Share a short demo and a reproducible result where Claude Code users already gather.

## Recommended TOKEN ZOMBIE launch sequence

### Before launch
- Publish a real Claude Code toolbar capture; the current README notes that a verified live toolbar capture is not yet published.
- Run a reproducible A/B task set with the same task, model, settings and quality rubric, with and without TOKEN ZOMBIE.
- Report fresh input, cache reads, cache creation, output, tool calls, task quality and TOKEN ZOMBIE overhead separately.
- Publish raw logs or redacted reproducible fixtures, benchmark script, machine/runtime details and known limitations.
- Keep demo dashboard data visibly labelled as demo data.

### Launch assets
- 20–30 second screen recording: problem → detection → intervention → recoverable result.
- One animated README demo and one clean static screenshot.
- A "How it works" diagram: Observe → Understand → Detect → Protect → Continue.
- A concise release note with supported host/version, install/update/uninstall and verification steps.
- A technical post explaining why token totals alone are insufficient and how the ledger labels MEASURED / EST / UNAVAILABLE.

### Distribution
- Publish the GitHub release and changelog first.
- Post a short demo with a direct repository link on relevant developer channels.
- Submit to Hacker News only when the demo and benchmark are independently reproducible; explain the trade-offs candidly.
- Ask early users to report compatibility, false positives and overhead. Convert verified feedback into issues and releases.

## Claims discipline

Current repository documentation says real with/without A/B savings trials have not yet been completed and some host behaviours still require live verification. Therefore:

- Say **"surfaces resource signals"**, not "accurately attributes every token to every agent", until attribution is verified.
- Say **"helps identify avoidable work"**, not "eliminates waste".
- Say **"supports recoverable output trimming"**, not "lossless compression everywhere".
- Say **"Claude Code is the supported integration"**; other adapters remain experimental/rules-only as documented in [COMPAT.md](../COMPAT.md).
- Do not publish a percentage savings claim until a quality-adjusted benchmark includes TOKEN ZOMBIE's own overhead.

## Bottom line

The strongest defensible position is not "the biggest token saver". It is:

**TOKEN ZOMBIE gives developers a local control layer to understand AI-agent resource use, spot avoidable work and protect project continuity.**

The path to attention is a sharp promise plus a real demonstration and reproducible evidence — not copying competitor feature lists or chasing star-count claims.
