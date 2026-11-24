# Claude Mods integration: capability report (2026-11-24)
Rule: one mod (`hooks/panel.tsx` + `hooks/tools.ts`), no second engine. Every tool shells to the existing `bin/tz`.
Verified against this build's plugin-authoring types and `claude plugin validate` (passes). NOT yet exercised in a live chat.

| Capability | Status | Powered by |
|---|---|---|
| Callable tools: tz_recall, tz_map, tz_plan, tz_delegate, tz_checkpoint, tz_recover, tz_verify, tz_ship, tz_status | built, validates, not live-tested | `tz recall/map/code/split/checkpoint/resume/handoff verify/handoff status/status` |
| tz_plan / tz_delegate | print a plan only; they do not spawn agents | `tzsplit` |
| tz_verify | checks handoff vs git (integrity score); does not run the project tests (use `tz resume --run-test`) | `tzhandoff` |
| tz_ship | read-only readiness report; no push or deploy | `tz handoff status` |
| Context retrieval | on demand via tz_recall / session-start hook | `tzout recall`, `tz-start.py` |
| Tool-output optimization + original recovery | existing PostToolUse hooks; originals via `tz recall` | `tzout`, `tzcompress` |
| Agent tracking | panel writes per-session `agents-<sid>.json`; counts and tasks, no orchestration | `panel.tsx`, `tzlib` |
| Agent orchestration | NOT implemented: the mods API here has no safe way to spawn and coordinate; `tz agent` runs the pipeline via `claude -p` (tested only against a fake host) | `tzagent` |
| Panel controls | checkpoint, verify, ship? buttons built (run the tz command, show output); pause/approve/retry NOT implemented | `panel.tsx` |
| Hook proof | `tz hooks proof` lists which events fired | `tzhooks` |
Measured savings: replay net 0.58% (offline). No end-to-end or quality claim: the A/B benchmark has not run (needs two logged-in config dirs).
Remaining: live-session verification, panel controls, A/B benchmark, status registry.
