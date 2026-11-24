# Everything the owner asked for, one by one (from this session's transcript), with status, 2026-11-24
Done = in repo and tested. Limited = built, but the host or a missing piece caps it. Open = not built.

| # | Ask | Status |
|---|---|---|
| 1 | Save tokens everywhere, keep chats short, compact + handoff (main offline, daily, per task) | Done (`tz handoff`, daily notes, `tz hsize`, continuation note) |
| 2 | Skills off by default, on when needed | Done (`tz ondemand`, skillpack) |
| 3 | Split tasks into one session each, build first, test later | Limited: prompt hint + `tz split`; a hook cannot start sessions; detector misfires on pasted text |
| 4 | find-skills inside tz | Done (`tz skills find`) |
| 5 | Search similar GitHub repos, learn, improve | Done (`tz similar`, handoffs/2026-11-24-research.md); ideas taken: repo map (Aider), xcheck (ccusage) |
| 6 | Coding skills + workflow in tz | Done (`tz code`); `tz agent` ran for real once (bug fixed, 54.5k tokens) |
| 7 | Model, agents, skills chosen automatically per task | Limited: advice (`tz classify`, route) + per-phase models in `tz agent`; cannot switch the live chat's model |
| 8 | Cost control items; "why not opus" | Done (cost caps, pricing known/unknown labels) |
| 9 | Build items 2-6 | Done earlier |
| 10 | Subagent report cap; hsize warning | Done |
| 11 | Cache-aware reads | Open (needs cache tracking tz lacks) |
| 12 | Hub research: ccusage, Aider, harbor/terminal-bench, codebase-memory-mcp, OpenHands, claude-squad | ccusage + Aider done; harbor A/B runner Open; codebase-memory-mcp not adopted; OpenHands/agent patterns partial (`tz agent`) |
| 13 | Feature freeze, fix incomplete, verify, honest docs, keep identity | Followed; docs/MODS-REPORT.md and BUILD-LIST.md |
| 14 | Claude Mods integration: tools, panel, hooks | Done (9 tools, 3 buttons, hook proof); not live-tested; pause/approve/retry and agent orchestration Open |
| 15 | Prove with/without TZ on real tasks | Open: needs ~/tzab/control and ~/tzab/treatment logged in |
| 16 | "Update website" | Open: no website found in the repo; which one? |
| 17 | Small handoff instead of full chat | Done |
