# GitHub capability research (2026-11-22)

**Method and limits.** Baseline = the owner's pasted external research (Codex/ChatGPT with GitHub connector, 22 Nov 2026: metadata, selected source files, docs).
I did not re-run GitHub discovery and did **not** audit any full repository. Source-level claims below are "documented/reported by the baseline", not checked by me.
My own checks: TZ source (read), installed Claude Code 2.1.318, real transcripts, TZ's test suite and timings.
Labels: **MEASURED** (here), **EST**, **REPORTED** (baseline, unverified by me).

Correction carried over: the 235K Karpathy star count does not belong to `skydr1ft/andrej-karpathy-skills` (1 star).

## 1. Licence and security gate (before any code reuse)
| Repo | Licence (GitHub) | Rule |
|---|---|---|
| mattpocock/skills, obra/superpowers, NousResearch/hermes-agent, DietrichGebert/ponytail, upstash/context7, wshobson/agents, nateherkai/token-dashboard, camtrik/agent-trail, tomstagl/cctop | MIT | ideas + small code OK with notice; none copied |
| JuliusBrussee/caveman, thedotmack/claude-mem, rtk-ai/rtk, headroomlabs-ai/headroom | Apache-2.0 | ideas OK; code needs notice; none copied |
| mksglu/context-mode | no SPDX returned; owner reports ELv2 | **copy no code**; ideas reimplemented independently |
| anthropics/skills | none returned | read only |

Security: nothing installed, no repo code executed, no tokens or paths of the owner sent anywhere. Any future reuse: read the licence file, pin a commit, read the code, no network at runtime.

## 2. What each project does, mechanism, overlap with TZ, decision
| Project | Mechanism (REPORTED) | TZ already has | Decision |
|---|---|---|---|
| Hermes Agent | modular context compressor (protect head+tail, summarise middle, tool-output pruning, deterministic fallback); subagent lifecycle states | `tz compact` note, PreCompact checkpoint, `tz live agents` | **Adapt later**: lifecycle states + summary-failure fallback; do not import runtime |
| Caveman | proxy with shadow/canary modes; savings only on completed requests; unknown price stays unknown; redundancy gate; recovery of originals | RTK trim, `tzout` spill + recall; EST/measured labels | **Adapt**: recovery + provenance (have); **reject** a second proxy (latency, failure modes) |
| cctop | per-call cache-aware cost (5m/1h writes), Ledger/Priced/Unpriced provenance, dedupe by message.id, agent ledger, next-call view | `calls()` dedupe by id, `ieq`, econ projections, labels | **Adopt**: 1 h write pricing (done), next-call line (done); agent ROI = open |
| Agent Trail | canonical JSONL parser: forks, subagents, compaction, streaming dedupe, unknown≠0 | `calls()` dedupe | **Adapt**: tests only; no new parser |
| Token Dashboard | incremental scan by byte offset, ignores unfinished last line, replace-not-sum snapshots | ledger + transcript reads | **Adapt later** if scans get slow (see overhead) |
| Context Mode | local output archive, FTS retrieval, benchmark groups per mechanism | `tzout` spill (+grep/lines) | **Reimplement independently**: FTS5 search (done). Reject its 99% claim as a token claim |
| Claude-Mem | 3-step retrieval (index, around, full), SQLite FTS5 + vectors, imports auto-memory md | handoffs, `tz recall`, memory dir | **Adapt**: progressive search over handoffs (open); reject vector DB and worker |
| Headroom | AST-aware code compression, fail-open on syntax error | RTK, no code compression | **Reject for now**; experimental only, never when editing |
| Ponytail / Matt Pocock / Superpowers | simplicity ladder, evidence-based review, TDD/debug skills, fresh-subagent flow | core rules block already carries the ladder | **Keep on demand**; subagent-per-task only when it beats inline |
| gstack | own eval: skills did not clearly improve fix rate (REPORTED) | `tz skills --effect` (EST) | **Adopt the lesson**: measure net quality, not only tokens |

## 3. Official hooks (checked)
Claude Code **2.1.318** installed (MEASURED). Docs list `PostToolUseFailure`, `InstructionsLoaded`, `SubagentStart/Stop`, `PostCompact`, others.
Decision: **not registered yet**. Adding `PostToolUseFailure` changes `hooks/hooks.json`, `install.sh` EVENTS and the 8-event test; it only takes effect when the owner re-runs `install.sh`. The circuit breaker already handles that payload shape and works from PostToolUse results today. Needs owner yes (LEFT 18).

## 4. Built this round (advice only, nothing blocks, all optional/OFF by config)
| Priority | Built | Where | Test |
|---|---|---|---|
| Next-call cost engine | `next_call()`: history x0.1 warm / x1.25 cold + one reply, per model, EST; line in `tz stats`/`tz route` | tzcont.py | test_cont |
| Cache-aware pricing | 1 h write part priced 2x (was 1.25x) | tzcont.py | test_cont |
| Subagent attribution | already `tz live agents`; real logs carry `attributionMcpServer/Tool`, not built into cost yet | - | open |
| Searchable output archive | `tz recall --search WORDS`: in-memory SQLite FTS5 bm25 over spill files, no new store, no daemon | tzout.py | test_out |
| Memory retrieval | not built (see 5) | - | open |
| Skill effectiveness | `tz skills --effect` (EST) | tzcont.py/tzcap.py | test_cont |
| File guard, breaker, replay | done earlier this session | tzcont.py | test_cont §12 |

## 5. Not built, with reason
- Memory retrieval: handoffs are small and read by newest-file rule; FTS over them adds little until they grow. Cheap next step: reuse `search()` over `handoffs/*.md`.
- Subagent ROI/lifecycle (Hermes, cctop): needs SubagentStart + transcript reconciliation; separate batch.
- Compaction verification (`PostCompact`): needs a new hook event, same owner gate as above.

## 6. Overhead (MEASURED, this Mac)
- guard hook, PreToolUse Edit payload: median 37 ms of 15 runs, 0 chars added to context when nothing to say.
- `tz recall --search` on a small store: 38 ms total process time. Index is built in memory per call (store capped at KEEP_FILES), nothing persists, no startup cost.
- Next-call line: +1 line (~100 chars) in `tz stats` only, not in any hook or startup context.
- Test results: see handoff (full suite run at the end).
