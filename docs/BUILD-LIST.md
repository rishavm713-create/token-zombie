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

## Competitor-derived items (ChatGPT audit, 2026-11-24)
Rule: reuse code only from MIT/Apache repos (credit + keep licence); CHECK/STUDY repos are read for public behaviour and rebuilt clean-room; no decompiling. Licences checked with `tz reuse`.

| # | Item | Source (licence) | Approach | Est. |
|---|------|------------------|----------|------|
| 1 | `tz diff-review`: did the diff stay inside the task | karpathy-skills (MIT) | reuse idea + prompts, credit | 30 min |
| 2 | `tz impact FILE`: callers, imports, what may break | aider (Apache), codebase-index (MIT) | reuse approach; ast for py, regex for js/ts | 60 min |
| 3 | Task dependencies in `tz next` | beads (MIT) | reuse model | 30 min |
| 4 | Staged team flow plan>prd>exec>verify>fix in `tz agent` | oh-my-claudecode (MIT), mini-swe-agent (MIT) | reuse flow | 45 min |
| 5 | Instruction-file organizer (core vs archive) | claude-token-optimizer (MIT) | reuse approach | 25 min |
| 6 | Destructive-command guard hook | cc-safety-net (MIT) | reuse rules, credit | 30 min |
| 7 | Skill install/update registry | vercel-labs/skills (MIT) | reuse | 30 min |
| 8 | Reversible compression + cache-aware notes | headroom (Apache) | reuse ideas | 40 min |
| 9 | RTK filter coverage gap audit | rtk (Apache CLI; proxy BUSL: excluded) | compare, add missing filters | 40 min |
| 10 | Bounded output + retrieval | context-mode (Elastic 2.0) | CLEAN-ROOM only, no code copied | 30 min |
| 11 | Symbol navigation | serena (custom licence) | CHECK licence first; else clean-room | 45 min |
| 12 | Tokens per PASSED task | code-compression-bench, harbor | needs owner login for the live run | 30 min |
| 13 | Spec-to-tasks | OpenSpec (MIT) | reuse format | 30 min |
Not copied: claude-squad (AGPL), 100-agent swarms, vector DB, cloud proxy.
Total ~7 h of build; items 1-9 ~5 h.

## Built 2026-11-24 (tz 2.0 front door): `tz safe` (destructive-command rules, cc-safety-net approach, MIT, rewritten), `tz impact`, `tz diffcheck` (karpathy-skills scope idea, MIT, rewritten), `tz run` (10 stages, dry by default; `--go` runs tz agent with budget and worktree). Not wired: safe into the tz-guard hook (opt-in later), task deps (tz next already has deps).
Built 2026-11-24: `tz scaffold "<idea>"` (0 tokens, templates, stdlib): signup/login, one CRUD resource, sqlite, passing tests. Next: HTML UI template, payments stub, deploy files, more templates (Node, Next.js) as reusable repos under licence.
