# Group A: context and token efficiency (researched 2026-11-25)

TZ = MIT, Python stdlib. Repo reads via `gh api` only. Ledger rows exist for all 8 repos; this deepens, does not repeat.
Main cost is cache reads of the re-sent chat, so value ranks by "tokens removed from every later turn".

## 1. microsoft/TokenEconomizer (priority 1)
- URL: https://github.com/microsoft/TokenEconomizer | MIT (LICENSE at repo root) | main@9c0888c42dd3
- Inspected: tokeneconomizer/toolprune/{stage.py:86-111,190-194; tools.py:14-104; README.md}; plugin/{fold.py:40-50,143-283,428-460; config.py:194-199; adapter.py; denylist.py; toolcheck.py:199}; trace/{claude.py:31-71,366-380; calls.py:109; claude_tool_catalog.json}; microskills/{envfacts.py,lifecycle.py:17-23}; tests/{test_live_hooks.py ~525,687,708; test_toolcheck_measure.py; test_tool_roles.py}; plugin/slash-commands/{toolprune,untool}.md.
- Capabilities: (a) toolprune: remove never-used tools from the next session's request via bare-name `permissions.deny` (schema leaves the prompt; verified by them on CC 2.1.286/2.1.307). (b) micro-skills / experience memory: candidate->active lifecycle, recency-weighted score, firing gate, injection cap MAX_FACTS=4 / MAX_TOKENS=150.
- TZ overlap: none for toolprune (V2.1-PLAN.md:11 lists it as planned). Micro-skills: partial with TZ memory files, no scoring.
- Decision: toolprune = B (selective port, NOTICE). Micro-skills = C (rebuild small, reuse constants). Pure Python stdlib already.
- TZ target: new bin/tztoolprune.py (+ `tz toolprune show|apply|restore`), hook-free; reads transcripts under ~/.claude/projects.
- Spec (toolprune):
  - Input: transcript JSONL files of the repo (tool_use.name per assistant message; deferred_tools_delta for the catalog), static catalog snapshot (name -> description) for tool-token estimate, config `toolprune_protect` (fnmatch list).
  - Algorithm: per tool, unused streak = consecutive sessions AND prompts with zero calls. Candidate only if streak >= N sessions and >= M prompts (TE defaults at config.py:194-199; take them, then calibrate). High-risk tools (NotebookEdit) need 3x streak. Never prune PROTECTED set (Read, Edit, Write, Bash, Grep, Glob, Task/Agent, TodoWrite, plus interactive ones; tools.py:41-48, adapter INTERACTIVE_PROTECTED) or anything matching toolprune_protect. Skip tools that never appear in catalog.
  - Apply: write bare names to `.claude/settings.local.json` permissions.deny; record exactly what WE added in `untool_applied.json` (restore removes only recorded entries, never user ones); add both to .git/info/exclude. Apply is delayed until repo idle (>=60 min, pending cap 24h), since tool-list change invalidates cached prefix on resume.
  - Output: table `tool | streak | est tokens saved/turn | verdict`; `restore` is exact inverse.
  - Edge cases: settings.local.json missing/invalid JSON (abort, no write); concurrent edit (re-read before write); tool used after apply (auto-restore suggestion); MCP tools `mcp__srv__tool` pruned per-tool, server-wide only if all unused.
- Parity examples (from test_live_hooks.py behaviour): (1) 3 sessions, 6 prompts, none call CronCreate/ShareOnboardingGuide/Workflow -> proposes exactly those 3. (2) Read used once -> never proposed. (3) NotebookEdit unused at 1x streak -> not proposed, at 3x -> proposed. (4) apply then restore -> settings.local.json byte-identical to start, user's own deny entry kept. (5) apply requested while repo active <60 min -> status `apply-pending`, no write. (6) toolprune_protect=["Cron*"] -> CronCreate excluded.
- Conflicts: none (we only write settings.local.json). Must not touch tz-guard allow/deny arrays. Status: SELECTED (top of build list).

## 2. alexgreensh/token-optimizer (priority 2)
- License: PolyForm Noncommercial -> ideas only, no code. Evidence: repo LICENSE (verified earlier). Files read: README + hooks docs (scratch to-readme.md, to-hooks.md).
- Behaviour: PreToolUse on Read of an already-read, unchanged file -> deny with skeleton (structure map) as the reason; if changed, show delta diff only. Modes shadow (log only) / soft_block / block. MCP deny: duplicate identical MCP call with same args in session -> deny and say "result already above / recall". Invalidate on Edit/Write.
- TZ overlap: bin/tzopt.py read_decision 191-232 (deny-once, DENY_MIN=2000), bin/tzout.py _reread 161-177, bin/tzcompress.py skeleton/outline, tz-guard.py:199,234 deny path. Duplicate-Read deny + skeleton already exist (tzlib.py:39,41 `dup_skeleton`).
- Gaps: (i) no delta diff on changed re-read, (ii) no MCP duplicate-call deny (tz-guard.py:274 only handles mcp__ names), (iii) no shadow mode metric.
- Decision: C (independent rebuild of gaps i-ii). TZ target: tzopt.py (delta), tz-guard.py (MCP dedup).
- Spec MCP dedup: key = tool name + JSON args (sort_keys, drop nulls); ledger per session id in tzopt ledger (line 26); second identical call within same session with no intervening Write/Edit/Bash-mutating -> deny, reason "identical call already answered above". Exempt non-idempotent names (send, create, post, delete, update, write, run). Delta: difflib.unified_diff(old,new,n=2) when file hash changed; fall back to full read if diff > 1500 chars or > 2000 lines.
- Parity: same Read twice unchanged -> deny+skeleton; changed by 3 lines -> diff of ~3 hunks; changed by rewrite -> allow full; mcp__x__get(a=1) twice -> second denied; mcp__x__get(a=1) then (a=2) -> allowed; after Edit of file F, Read F allowed.
- Status: REVIEWED (idea only), gaps SELECTED.

## 3. Tarquinen/opencode-dynamic-context-pruning (priority 3)
- License AGPL -> behaviour only. Files: lib/strategies/deduplication.ts, purge-errors.ts, config.ts:88-101, README.
- Behaviour: dedup = same tool + normalized args (sorted-key JSON, nulls dropped) -> keep newest, replace older outputs with a placeholder; purge-errors = errored tool call inputs older than N turns replaced. Both mutate the history array before each LLM call. HEAD has no supersede-writes. Pruning is computed only when compression runs, to preserve cache.
- TZ: Claude Code hooks cannot rewrite old tool results, so the strategy does not port. What ports: (a) normalized signature (used in item 2 above), (b) cache-aware rule: only shrink at a /compact boundary or PreCompact (tz PreCompact hook), never mid-session.
- Decision: D reference only (+ signature idea absorbed in C above). Status: REVIEWED.

## 4. rtk-ai/rtk (priority 4)
- License: root = split. src/cmds/** Apache-2.0 (portable with NOTICE); engine/ and proxy/ BUSL (idea only). Evidence: LICENSE files per dir, tree rtk-tree.txt. Files: src/cmds/README.md + per-ecosystem READMEs, python/pytest_cmd.rs tests 494-536, git/git_cmd.rs tests from 5343 (names only read).
- Behaviour: per-command filters. pytest: keep failures + short summary, drop passing dots/progress; git status: compact counts per section; git diff: stat + hunks trimmed with `... N more lines`; git log: one line per commit, cap count.
- TZ overlap: tzout.py generic head/tail trim (READ_MAX 20000, OTHER_MAX 12000), `rtk` already installed as separate tool by the owner (RTK.md), so output is already condensed when rtk runs.
- Decision: E for porting (Rust->Python cost high, and rtk already runs on owner machine); D reference. Only revisit if rtk is absent: small pytest/git-status filter in tzout (C). Status: REVIEWED.

## 5. headroomlabs-ai/headroom (priority 5)
- URL https://github.com/headroomlabs-ai/headroom | Apache-2.0 (LICENSE, NOTICE) | main@3292b0e4 | Rust core + Python.
- Files: crates/headroom-core/src/ccr/mod.rs:1-40 (+ backends/sqlite.rs), transforms/log_compressor.rs:1-50,166-238, smart_crusher/*, diff_compressor.rs, search_compressor.rs.
- Capabilities: CCR (compress-cache-retrieve): lossy text on the wire, original stored by hash, retrievable by a tool call; SQLite store, TTL idle + absolute max lifetime. Log compressor: format detect (pytest/npm/cargo/jest/make), level scoring, stack-trace state machine, conservative dedupe preserving the message prefix before first `:`/`=`, adaptive budget, CCR only when ratio < 0.5 and >= 50 lines. SmartCrusher: JSON array row drop with anchors/constraints.
- TZ overlap: bin/tzcrush.py (crusher), tzmcpfake.py, tzout.py trim with `[trimmed]` marker (_mark_trimmed 179-190) but no retrievable original.
- Decision: log compressor = B/C (Apache; port logic to Python stdlib, ~200 lines: level regexes, trace blocks, prefix-preserving dedupe). CCR = C: store dropped original in `.tz/ccr/<sha8>.txt` (stdlib sqlite3 or flat files), marker `[tz: N lines omitted, full: tz recall <sha8>]`, TTL 24h. Worth it because dropped tails currently cannot be re-fetched, so the agent re-runs commands (cost).
- Parity: 10,000-line pytest output with 5 failures -> keeps FAIL lines + traceback + summary line, < 5% size; two errors `segfault at 0x1`, `segfault at 0x2` stay distinct; 100 identical warnings -> 1 + "x100"; input < 50 lines -> unchanged, no store; ratio >= 0.5 -> no store.
- Conflicts: marker text must stay consistent with tzout `[trimmed]`. Status: SELECTED (log filter + recall).

## 6. yvgude/lean-ctx
- License: Apache-2.0 root LICENSE (e7a78554); LICENSE.md + LICENSE_MATRIX.toml say commercial/free_runtime/private_service paths are NOT in the public tree; per-path authority is the matrix. Files inspected: tree listing (core/archive*, core/cache/*), LICENSE_MATRIX.toml.
- Capabilities: read modes (full/map/delta), session cache with validation + warming, archive with FTS recovery, MCP gateway.
- Overlap: tzopt read cache, tzcompress modes. Decision: D (ideas: archive recovery = same as headroom CCR). Not read in depth (Rust, large). Status: REVIEWED, shallow.

## 7. mksglu/context-mode
- License ELv2 (LICENSE; package.json "Elastic-2.0") -> ideas only; also restricts providing as managed service. main@f41c429a. Tree seen: src/core/compaction/{candidates,recall,render,score}.ts, hooks/decision.ts.
- Idea: run noisy commands in a sandbox, index output into per-project SQLite FTS5, return only a query hit. Same shape as CCR above, with search instead of hash.
- Decision: D. Take idea: `tz recall` may support keyword search via sqlite3 FTS5 (stdlib) in a later step. Status: REVIEWED, shallow.

## 8. DietrichGebert/ponytail
- MIT (LICENSE) | main@ebd8654c. Files: skills/ponytail-debt/SKILL.md, skills/ponytail/, hooks/band/.
- Shortcut-debt detection: grep `(#|//|/*) ?(shortcut|ponytail):` comment markers; row `<file>:<line> what. ceiling: X. upgrade: Y.`; marker with no trigger gets `no-trigger`; end `N markers, M with no trigger.`; nothing found -> `No shortcut debt. Clean ledger.`
- Decision: B tiny (MIT; copy the regex+output format with NOTICE) as `tz debt` or tzgate check. ~30 lines. No token effect unless it replaces repeated rediscovery; low value.
- Parity: `# shortcut: 100 rows max, move to db at 1k` -> row with ceiling and upgrade; `// shortcut: temp` -> no-trigger; prose "keyboard shortcut:" without comment prefix -> skipped. Status: SELECTED (low).

## Ranked build list (value per re-sent token first)
1. tz toolprune (TE, B): removes whole tool schemas from every request for all later turns; per-turn saving repeats 100%.
2. Log/test output filter + `tz recall` (headroom, B/C): shrinks the biggest single tool results that live in the chat forever; recall removes the re-run cost.
3. MCP duplicate-call deny (token-optimizer idea, C): stops big repeat MCP results entering the chat.
4. Delta-diff on changed re-read (C): replaces full re-read with a small diff.
5. Cache-aware prune at PreCompact only (DCP idea, D): keep as rule, no code.
6. Micro-skills / experience memory (TE, C): small, injection capped 150 tokens; measure before shipping.
7. FTS5 search over recall store (context-mode idea, D->C later).
8. ponytail shortcut-debt scan (B, tiny).
9. RTK filters (E; rtk already installed).
Not checked: lean-ctx and context-mode source in depth; RTK git diff/status test bodies; TE default streak numbers (take from config.py:194-199 at build time).
