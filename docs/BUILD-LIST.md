# Build list from the ChatGPT share (6b056444...), checked against the repo, 2026-11-24
Source: the shared chat is one ChatGPT answer plus the pasted "Claude Mods" spec (A-G, phases 1-6). Nothing else is in it. The earlier link (6b056307) holds only the question.

## Done (verified)
- One mod, no overlap: `hooks/panel.tsx` + `hooks/tools.ts`; `claude plugin validate` passes.
- Tools: tz_recall, tz_map, tz_plan, tz_delegate, tz_checkpoint, tz_recover, tz_verify, tz_ship, tz_status (all call the existing `bin/tz`).
- Panel buttons: checkpoint, verify, ship?; hook-proof log (`tz hooks proof`).
- Tool-output optimization, recall of originals, redaction: existing hooks (`tzout`).
- Context recovery: handoff / resume / checkpoint (existing).
- Coding agent: `tz agent` run for real once (fixed a bug, 54.5k tokens measured).
- Honest report: docs/MODS-REPORT.md.

## To build (not done)
1. Live check of mod tools and buttons in a fresh chat with the plugin enabled (loads only on session start).
2. A/B benchmark with/without TZ (needs ~/tzab/control and ~/tzab/treatment logged in; control login in progress).
3. tz_verify that runs the project's tests (today: handoff vs git only).
4. Panel: pause / approve / retry (need a host pause API; check types first).
5. Agent coordination: duplicate-work detection and report collection from agent events (tracking exists; orchestration does not).
6. Status registry; stop tests rewriting docs/; multi-task detector misfire on pasted text; sonnet-only review phase.
7. Installer/upgrade check that the mod's tools.ts ships and loads after `install.sh`.

## Host-limited (document, do not fake)
- Spawning and coordinating agents from a mod: no safe API in this build.
- Hook `tool.run` event: does not exist; tools are served via `tool.call`.
- Zero context loss: not promised; measured via resume-readiness score.
