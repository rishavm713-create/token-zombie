---
name: token-zombie
description: Token-saving rules for Claude Code. Use when a chat is big, a task ends or starts, a handoff is due, plan usage is high, token use/savings is asked, or a task needs a skill not on.
---

# Token Zombie

An optimization layer, not a cage. Defaults below are advice: override any of them when the task needs it, and say why in one line. Never trade correctness, verified progress or needed context for tokens. Thresholds live in `~/.claude/token-zombie/config.json` (keys: limit, hard, read_warn, plan_warn, plan_stop, mode). CLI: `python3 "${CLAUDE_PLUGIN_ROOT}/bin/tz" help`.

## 1. Task limit, not number limit
- One task per chat. A task = one thing the owner can check as done.
- Task continuity first: a task may span sessions. Never abandon or mark done unfinished work because a threshold was hit. Big chat + unfinished task: at a safe point (not mid-edit, mid-test, mid-file-op) write handoff, then move the REST to a fresh session (`mcp__ccd_session__hand_off_to_session`; no desktop app: tell the owner "new chat, say: read <handoff path> and continue").
- Big chat + NEW task: write handoff, start the new task fresh (`mcp__ccd_session__start_session`, context "fresh", 5-line brief + handoff path).
- Plan limits: use only real provider data (`mcp__ccd_session_mgmt__get_usage`, statusline `rate_limits`); never guess % or reset times. Check at task start and on big steps. >= plan_warn (90): keep the active task first, get handoffs ready, avoid optional work. >= plan_stop (97): reach a safe point, write handoffs, then stop only if the next step would be cut off; tell the owner the real reset time.

## 2. Handoffs that stay small
- Master `<project>/HANDOFF.md`: only its TOP BLOCK loads at start (max 15 lines, ended by a `---` line). Newest facts on top; old detail below the line (never loaded).
- Task/daily `<project>/handoffs/YYYY-MM-DD[-task].md`, max 30 lines: `Status (unfinished|done) / Done (verified how) / Left / Next step (one exact action) / Changed files / Tests (cmd -> result)`. Keep every technical detail the next session needs (paths, exact errors, decisions).
- Update daily handoff when a task ends and before any session move or limit stop. Paths, never pasted content. Weekly: merge dailies into the master top block.
- New chat reads nothing else unless the step needs it (start hook injects top block + newest daily). Details: references/checkpoints.md, references/continuity.md.

## 3. Cheapest capable model, short-lived agents
- Cheapest model that meets the quality bar; escalate one step after a failed check, never to save tokens at the cost of correctness. `tz route <task>` gives advice.
- Main chat Sonnet; Opus only for hard builds/design (say in one line if the owner should switch). Do not switch the main model mid-chat: it drops the prompt cache. A step that needs another model goes to a subagent (`model`).
- Agent only when parallel work or a large read pays for its own start (~20-80k context each). One clear task, compact brief, its model chosen per step. Search/bulk reading: `haiku`.
- Take back the result (verdict + evidence paths), not its history. Stop it when done (`TaskStop`); no duplicate or idle background agents.
- No web search unless the task needs outside or current facts. Never repeat a search. Details: references/routing.md, references/orchestration.md.

- Several independent tasks: `tz split "A" "B"` = one session per task, cheapest fitting model, own worktree; shared resources (live test, device, port) behind `tz lock acquire|release NAME`. Build the whole batch first (syntax checks only), then one live test at the end. `tz code` gives the coding pipeline with a model and skill per phase. `tz similar QUERY` finds comparable GitHub tools (ideas only, vet first). `tz hsize` flags daily notes over 30 lines / weekly merge due.

## 4. Skills and plugins: off until needed
- Guard suggests packs from prompt words: a hint, not an order. Turn a pack on (`~/.claude/skillpack on <pack>`) only if the task needs it and installed skills do not cover it; `off` when done; one line saying which. Owner can turn any pack on/off by hand.
- Pick by task type (coding, research, security, docs, testing): installed skills first (`tz skills <task words>`), then `find-skills` (`npx skills find <need>`), then GitHub (section 6). Vet before use, ask before install, never "just in case"; skip any that overlaps an installed one.
- After the task: pack off, stop invoking its skills. Honest limit: an invoked skill's text stays in the chat until compaction or a new chat; only metadata loads in later chats.
- Rare skills: `disable-model-invocation: true` (manual `/name`, 0 startup). Plugins with MCP servers cost every chat: keep off unless used weekly.

## 5. Every-turn habits
- Every model call re-sends the whole chat (measured ~80-120k per call here): batch independent tool calls in one message; fewer round trips beat any trimming. `tz optimize` shows the per-call cost.
- Prefer grep / `sed -n a,bp` ranges. Read whole files when the task needs them (the guard nudges once on files > read_warn; repeat the Read to proceed). Do not re-read unchanged files or re-summarise what is already in the chat.
- Text before images; images <= 800 px, once. Search only the files the task needs.
- Terse replies, smallest complete change, command output through rtk.
- `/compact <what to keep>` inside one task only; between tasks fresh chat. `/token-zombie:compact` writes the note and prints the line to paste.

## 5b. Engineering rules (from karpathy-guidelines, MIT)
Read the code before changing it; state assumptions. Simplest code that works, no speculative abstraction. Surgical edits in the codebase's style. Define a check (test/run), loop until it passes; verify before saying done. Docs change with the code. Details: references/engineering.md.

## 6. GitHub-first discovery, vetted, local only
1. Name the need in 3-5 words. 2. Haiku agent: `gh search repos "<need> claude skill" --sort stars --limit 10`.
3. Shallow clone top 2-3 into the scratchpad; run `bash "${CLAUDE_PLUGIN_ROOT}/bin/tz-vet.sh" <dir>`. HIGH (pipe-to-shell, secret reads, upload, deletes outside own dir, decode-then-exec, persistence, permission bypass, prompt injection, hidden unicode): do not install until each line is read and explained to the owner. REVIEW: check whether the doc describes or instructs. INFO: judge by purpose. GREEN is not proof of safety.
4. Overlap with installed = skip. Smallest set wins. Copy only SKILL.md (+ needed local scripts); never run its install.sh/curl.
5. Ask the owner before installing. Log one line in `~/.claude/token-zombie/registry.md`. Details: references/security-audit.md.

## 7. Show the numbers
Owner asks what is used/saved: `/token-zombie:tz` (or `tz status`, `tz stats`) plus `get_usage` plan % if available. Label every figure MEASURED, EST or UNKNOWN. NET = gross savings - tz overhead (hooks, advice, handoffs, agents, discovery); a rule that costs more than it saves gets turned off. Claim savings only with a valid baseline comparison (references/benchmarks.md, references/metrics.md).

## What runs by itself
Plugin hooks (guard on prompt/tool/stop/session-end/precompact, lean start, compaction note) and the supervisor run silently unless a threshold is hit. Statusline is not set by a plugin: `bash "${CLAUDE_PLUGIN_ROOT}/install.sh" --statusline-only`. Off switches: `tz mode off`, env `TZ_SUP=0`; safety controls stay on in every mode (references/recovery.md).

## References (load only when needed)
- [overview](references/overview.md): what it is, optimizer
- [commands](references/commands.md): slash commands and tz CLI
- [metrics](references/metrics.md): cost, tokens, context, agent time; MEASURED/EST/UNKNOWN
- [checkpoints](references/checkpoints.md): checkpoints, compact notes, handoffs
- [continuity](references/continuity.md): resume across sessions
- [routing](references/routing.md): model routing
- [orchestration](references/orchestration.md): multi-agent work
- [engineering](references/engineering.md): Karpathy-derived coding rules, attribution
- [security-audit](references/security-audit.md): skill/plugin/MCP audit, tz-vet.sh
- [supervisor](references/supervisor.md): usage levels, status bus
- [dashboard](references/dashboard.md): dashboard, companion, in-chat panel
- [benchmarks](references/benchmarks.md): bench, A/B, no-claim rule
- [recovery](references/recovery.md): disable, uninstall, restore
