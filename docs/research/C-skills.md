# Group C: engineering quality and skills (research, 2026-11-25)
Method: gh api (license, tree sizes, raw SKILL.md). Scratch only; no clones. Sizes = bytes (gh tree / wc -c). Frontmatter (fm) = bytes between the two `---` lines = the always-loaded listing cost per skill.
TZ today: bin/tzondemand.py (9.3K, caps on/off, backups, caps.jsonl; want(prompt) keyword match at ~line 151) + skills/ + catalog/skills-seed.json (7.9K); bin/tzstandards.py (2.2K, detects indent/quotes/test tools only, no rules text). No TDD/debug/verify/review/plan rules text anywhere. grep for `reset --hard` over bin/ and hooks/tz-guard.py/tzgate.py: no hit, so a git-destructive-command block appears missing (bin/tzops.py matched only a force flag; not read in full).

## Licence table (LICENSE files read, sha = main head)
| Repo | Licence | Evidence | Copy text? |
|---|---|---|---|
| obra/superpowers @22f0b463 | MIT | LICENSE 1070 B | yes with notice; we rewrite (smaller) |
| affaan-m/everything-claude-code @4adeee67 | MIT | LICENSE 1071 B | reject (328 skills); nothing needed |
| anthropics/skills @e4bb5d96 | NO root licence (API spdx empty). Apache-2.0 per skill (frontend-design/LICENSE.txt 10174 B, webapp-testing/LICENSE.txt 11345 B, Apache header read). docx/pdf/pptx/xlsx LICENSE.txt are 11357 B (different file; not read in full, treat as restricted) | tree + head of files | Apache skills only, with LICENSE+NOTICE; none needed |
| vercel-labs/agent-skills @5a37a632 | MIT per README/SKILL frontmatter; NO LICENSE file in tree | tree grep | rewrite; at most rule IDs with attribution |
| mattpocock/skills @d6539114 | MIT | LICENSE 1062 B | yes with notice |
| jokim1/karpathy-skills @55b9f0a9 | MIT, LICENSE present (1067 B, (c) 2026 Joseph Kim) | tree | yes with notice; "Karpathy" is only inspiration |
| EveryInc/compound-engineering-plugin @fcb5e3ad | MIT | LICENSE 1062 B | yes with notice |
| EL4CTEO/fast-anything @1fdf12ef | MIT | LICENSE 1064 B | yes with notice |

## Per-skill sizes, core rules (own words), class
Class: B selective port (NOTICE) / C rebuild / D reference / E reject.

1. TDD. superpowers skills/test-driven-development/SKILL.md 9578 B (fm 127). mattpocock skills/engineering/tdd/SKILL.md 3629 B (fm ~190) + mocking.md 1481 + tests.md 2214.
 Rules: no production code before a failing test; run it and watch it fail for the right reason; write the minimum to pass; run again; refactor only with tests green; one behaviour per test; assert real behaviour not mocks; a bug fix starts as a reproducing test; tests written after pass at once and prove nothing; code written before the test means restart. Class C (~1.0 KB; the 9.5 KB original is mostly rationalisation tables).
2. Systematic debugging. superpowers skills/systematic-debugging/SKILL.md 9530 B (fm 136); ce-debug 19327 B (reference only).
 Rules: no fix before root cause. Phase 1 read the whole error, reproduce, check recent changes, and in multi-component systems log what enters and leaves each boundary. Phase 2 find a working example and diff against it. Phase 3 one hypothesis, change one variable, state the expected result. Phase 4 failing test then a single fix. After 3 failed fixes stop and question the architecture instead of trying a fourth. Class C (~1.1 KB).
3. Verification before completion. superpowers skills/verification-before-completion/SKILL.md 3646 B (fm 280).
 Rules: no success claim without a command run in this turn; identify command, run it fully, read output and exit code, then claim with the evidence. Tests pass = 0 failures shown; build ok = exit 0 (lint is not build); bug fixed = original symptom retested; delegated agent said done = check the VCS diff; avoid "should", "probably", "Done!" before evidence. Class C (~0.7 KB). Overlaps tzgate verify (code exists; this adds the text rule).
4. Git safety. mattpocock skills/misc/git-guardrails-claude-code/SKILL.md 2313 B (fm ~330) + scripts/block-dangerous-git.sh 507 B. Behaviour: PreToolUse Bash hook reads tool_input.command, exits 2 with a stderr message when it matches: git push (any variant), reset --hard, clean -f/-fd, branch -D, checkout ., restore . . superpowers using-git-worktrees 6813 B + finishing-a-development-branch 7781 B: one worktree per task, run tests before merge, offer merge/PR/keep/discard, discard needs typed confirmation. Class B for the 9-pattern list (MIT, copy with NOTICE), implemented in tz-guard.py as Python, ask-first rather than hard block; ~0.4 KB text + ~25 lines code. NOTE: this very session's TZ safe hook blocked a heredoc containing the text of such a flag, so TZ may already have a partial pattern block in a hook outside bin/ (check ~/.claude/hooks before building).
5. Evidence-gated refactor. karpathy-refactor SKILL.md 25196 B (fm 1017, lines 40-135 doctrine/lanes). Doctrine: each candidate needs a structural observation plus repo-history evidence (churn, co-change from `git log --no-merges`, fix-commit clusters); record the verification baseline BEFORE the first edit (red or missing baseline blocks any behaviour-preserved claim; downgrade to test-first or report-only); small slices, snapshot before, verify after, auto-revert on failure (marker example "[refactor] Reverted R2: npm test 210/212 - pre-slice state restored"); two lanes: auto-apply (risk low/medium, blast radius local/subsystem, payoff named, baseline green) vs report-only (sensitive areas, hot path without a runnable benchmark, red baseline). Class C (~1.0 KB); revert maps to existing bin/tzrollback.py.
6. Perf. fast-anything skills/fast-anything/SKILL.md 2257 B (fm 360) + commands/fast.md 427 B (fm 157). Loop: scan with the real workload (not the test suite), take the top function; skip anything under 2% of the run; record up to 500 real calls; port; verify by replaying every recorded call; never edit the recordings; enable only after verify passes; report end-to-end and per-call speedup plus the undo path. The Rust port and its CLI: E (external dependency). Language-neutral rules (measure first, 2% floor, replay equivalence, show undo) class C ~0.6 KB; pairs with karpathy rule "hot path needs a runnable benchmark".
7. React/frontend. vercel react-best-practices SKILL.md 7251 B (fm 440) + 72 rule files 110590 B (never load); composition-patterns 2886 B (fm 431); web-design-guidelines 2077 B. Useful core = priority order: 1 waterfalls (parallelise independent awaits, await late, Suspense) CRITICAL; 2 bundle size (no barrel imports, dynamic import heavy parts, defer third party) CRITICAL; 3 server (authenticate server actions, per-request cache) HIGH; 4 client fetching; 5 re-render; 6 rendering; 7 JS micro; 8 advanced. anthropics frontend-design 9390 B (Apache; aesthetics, not needed). Class C ~0.9 KB: the priority list + about 12 rule names.
8. Code review. superpowers requesting-code-review 2974 B (fm 154), receiving-code-review 6203 B (fm 280); karpathy-diff 7206 B (fm 767; flags edits beyond what was asked); ce-code-review 7800 B. Rules: review a BASE..HEAD range with a fresh-context reviewer given requirement + diff only; severity Critical/Important/Minor; fix Critical now, Important before moving on; push back with reasoning when wrong; when receiving review verify each point against the code before agreeing. Class C ~0.8 KB.
9. Planning. superpowers writing-plans 10335 B (fm 122), brainstorming 15190, executing-plans 18364. Rules: map files first; tasks sized to one verifiable unit with exact paths, commands and expected output; no placeholders ("TBD", "handle edge cases"); self-review the plan against the spec (coverage, naming consistency, a task per failure mode); global-constraints block; execution handoff. Class C ~0.8 KB.

## Always-loaded description cost (measured, fm bytes)
Superpowers 8 relevant skills 127+136+280+154+122+240+156+280 = 1495 B (plus using-superpowers ~3.2 KB injected at every SessionStart, 3192 B file). Vercel react+composition 871 B. karpathy 5 skills ~3.3 KB (audit 910, diff 767, refactor 1017, +2). fast-anything 360 B + command 157 B. mattpocock tdd ~190 B. ce-compound ~300 B. ECC: 328 skills. Merged TZ set: ONE skill, fm <= 260 B.

## karpathy audit + token-cost ranking (karpathy-audit SKILL.md 26529 B, lines 150-160, 280-295)
Input: CLAUDE.md / AGENTS.md / .cursor/rules / memory file. Two checks: coverage (does the file tell the agent to follow the four principles: think before coding, simplicity, surgical changes, goal-driven verification; "partial" shown but not scored) and quality axes CE1-CE11: Lean, Unambiguous (verification commands named, every step fail-able), Current, Contradiction (worst defect), Rules-to-judgment (KEEP safety/destructive/security/merge rules), Disclosure (monolith -> core + on-demand), Interfaces, Duplication (name one owner), Memory routing, References (link not prose), Reader tier (cut safe-for-all vs claude-only).
Ranking: impact = token size x replay tier, NOT raw bytes. Tiers high to low: every-turn base file > per-session digest > per-task read > rarely loaded. Upstream example: a 1 KB file replayed every turn outweighs a 12 KB file read once per session.
TZ spec (class B/C; target bin/tzopt.py or `tz audit-instructions`): inputs = CLAUDE.md, AGENTS.md, RTK.md, memory index, skill frontmatters; tokens = ceil(bytes/4); replay weight 1.0 always-loaded, 0.2 per-session, 0.05 per-task (our numbers, not upstream); score = tokens x weight x expected_turns; output top-N with offending CE axis. Parity examples: (a) 1000 B every-turn file vs 12000 B per-task file at 15 turns: 250*1*15=3750 vs 3000*0.05*15=2250, 1 KB file ranks first. (b) two rules that cannot both hold -> CE4 first regardless of size. (c) a safety rule (never run destructive git) is never proposed for cut (CE5). (d) same rule in global and project file -> CE8, name one owner. Live finding: ~/.claude/CLAUDE.md and ~/AGENTS.md carry the same ~5 KB block; both replay when both load. TZ overlap: tzopt/tzcost measure cost but do not rank instruction files by replay tier.

## compound-engineering learnings loop (skills/ce-compound/SKILL.md 7890 B, fm ~300; ce-compound-refresh 1665 B)
Loop: after a problem is solved AND verified, capture ONE learning per run. Durable bar: write only if the lesson is project reasoning not recoverable from code/tests/lint/docs and losing it would plausibly cause recurrence; otherwise write nothing and say why. Pick the CHEAPEST durable form in order: a test, a lint rule, a CODING_STANDARDS.md condition, then a doc at `<root>/solutions/<category>/<slug>.md` (root = docs_root in .compound-engineering/config.yaml, default `docs`; must be repo-relative, inside the repo, not .git). If an existing learning is now wrong, update it, never duplicate. Only the orchestrator writes product files. Refresh mode audits learnings against the current tree and may delete stale ones. Non-interactive mode never asks. Class C. TZ target: bin/tzlearn.py (3.7K) + tzhandoff. Spec: trigger = tzgate pass after a prior fail; output = at most 1 file `docs/solutions/<slug>.md` <= 1.5 KB (symptom, cause, fix, how to detect) or a test; skip when diff is under 3 lines or no fail-to-pass transition. Examples: failing test then green with a found root cause -> capture; typo fix -> write nothing "not durable"; learning contradicting an existing file -> update that file.

## Recommended minimal merged set (all rewritten in our words; credit ideas in NOTICE)
Layout: skills/tz-craft/SKILL.md (router) + skills/tz-craft/refs/<name>.md; one ref loaded per task via tzondemand.want() keywords.
| File | Target bytes | Source ideas |
|---|---|---|
| SKILL.md router (fm <= 260 B + 10-line which-ref table) | 700 | n/a |
| refs/tdd.md | 1000 | superpowers, mattpocock tdd |
| refs/debug.md | 1100 | superpowers |
| refs/verify.md | 700 | superpowers |
| refs/git-safety.md (+ ~25-line guard in tz-guard.py, ask-first) | 400 | mattpocock, superpowers finishing |
| refs/refactor.md | 1000 | karpathy-refactor |
| refs/perf.md | 600 | fast-anything |
| refs/react.md | 900 | vercel priorities |
| refs/review.md | 800 | superpowers, karpathy-diff |
| refs/plan.md | 800 | superpowers writing-plans |
| refs/learn.md | 600 | compound-engineering |
Total ~8.6 KB on disk; per task load = router 0.7 KB + one ref ~0.9 KB (~400 tokens). Always-loaded ~260 B vs 1495 B (superpowers subset) or 3.2 KB per-session injection (superpowers hook).

## Conflicts / notes
- superpowers SessionStart injection: rejected (against off-by-default).
- superpowers mandates subagents for review/execution (more cost): TZ ref says subagent only for diffs over ~150 lines.
- karpathy-refactor auto-apply without mid-run questions vs TZ ask-first for destructive ops: keep auto-revert, require one go-ahead.
- tzstandards.py: extend only to report the test command for verify/tdd refs; do not carry rules.

## Status
superpowers SELECTED (rewrite); mattpocock SELECTED (git guard); karpathy SELECTED (audit ranking, refactor gate); compound SELECTED (learn loop); fast-anything SELECTED (rules only, Rust CLI REJECTED); vercel SELECTED (rewrite; no licence file); anthropics/skills REVIEWED (nothing needed; no root licence); everything-claude-code REJECTED.

## Ranked build list (value per re-sent token)
1. refs/verify.md + refs/debug.md (stop re-work loops, 1.8 KB)
2. git-safety guard (check existing hooks first; ~25 lines)
3. tz-craft router + tzondemand keyword mapping (260 B always-loaded)
4. instruction-file audit ranking (token x replay tier)
5. refs tdd, refactor, review, plan, perf, react
6. refs/learn.md capture loop (tzlearn.py)
Gaps: did not read karpathy-wiki/update, ce-debug, ce-code-review, vercel rule files, anthropics docx/pdf licence text in full; no runtime efficacy tests.
