# Competitor learnings (viral GitHub tools, read 2026-11-25)

Scope: what went viral, why, what TZ lacks, what to copy. Extends `COMPETITIVE-GAP-ANALYSIS.md` and `OPEN-SOURCE-INTEGRATION-LEDGER.md` (does not replace them).
Labels: MEASURED = read from the GitHub API or the repo README by this session on 2026-11-25. EST = my inference. UNKNOWN = not checked.
Star counts are a snapshot; some are very large and I did not audit them for inflation (UNKNOWN). TZ itself: 1 star (MEASURED).

## Table

| # | Repo | Stars (MEASURED) | Licence (MEASURED) | What it does | Why it spread (README evidence, MEASURED unless marked) | What TZ lacks |
|---|---|---|---|---|---|---|
| 1 | JuliusBrussee/caveman | 122,743 | Apache-2.0 | Terse-output skill plus proxy, now an agent app | Joke title; side-by-side "63 → 20 tokens" box; 4 headline numbers each linked to a dated test; HN #1 and Trending claimed by README; third-party cites (Adobe paper, JetBrains blog) | Before/after demo of terse output; benchmark with interval; third-party validation |
| 2 | thedotmack/claude-mem | 119,668 | Apache-2.0 | Persistent cross-session memory (SQLite + vectors) | Demo GIF, star-history chart, "every agent" pitch (EST: memory is a pain every user feels) | Vector recall (owner rejected early vector memory) |
| 3 | rtk-ai/rtk | 87,778 | Apache-2.0 | Rust CLI proxy compressing command output; "60-90%" | One line `brew install rtk` + `rtk init -g`; "install and forget"; `rtk gain` shows savings; README states "90% less output is not 90% less cost" | A `gain`-named savings command; brew/winget/curl install; per-agent `init` with `--dry-run` |
| 4 | ruvnet/ruflo | 82,397 | MIT | Agent swarm harness | `npx ruflo@latest init` then a sample task; "check the result" step | `npx` zero-install entry; sample-task walkthrough (swarms: owner REJECTED) |
| 5 | headroomlabs-ai/headroom | 80,825 | Apache-2.0 | Compression layer (library, proxy, MCP, `headroom wrap <agent>`) | `pip install` + `headroom wrap claude`; undo with `unwrap`; honest ranges "21-57% on 4 scenarios, little on prose" | Wrap/unwrap for 15+ agents; proxy layer |
| 6 | mksglu/context-mode | 34,469 | Elastic License 2.0 (NOT open source; LICENSE file read) | Sandbox + SQLite FTS5 keeps tool output out of context | "Free and local" plus 11 agents; npm download count in README (929K claimed) | Sandboxed execution; FTS index (TZ has `tz recall`, no index) |
| 7 | ccusage/ccusage | 19,585 | MIT | Local usage/cost reports from agent logs | `npx ccusage@latest`: no install, instant report | `npx`-style zero-install; many agent sources (TZ: Claude + Codex) |
| 8 | sirmalloc/ccstatusline | 13,690 | MIT | Customisable statusline, themes, powerline | ASCII banner, screenshots, TUI configurator (EST) | TZ has a toolbar; no theme configurator |
| 9 | smtg-ai/claude-squad | 8,866 | AGPL-3.0 | tmux manager for many agents, git worktree each | Demo video, `brew install`, one command `cs` | Multi-agent session manager (REJECTED: auto-spawning). Learn only |
| 10 | Maciek-roboblog/Claude-Code-Usage-Monitor | 8,819 | MIT | Live usage monitor with burn prediction | Live terminal view + predictions | TZ has pace/5h-7d view already (DONE) |
| + | DietrichGebert/ponytail | 198,446 | MIT | "Laziest senior dev" prompt/plugin; smallest change | Persona story, before/after (335 lines vs 1 file), numbers section, "never cut security" rule | Already close in spirit (TZ core rules); lacks story + before/after |
| + | obra/superpowers | 326,243 | MIT | Skills methodology | Methodology brand, not token-saving | Not a direct competitor |

Others seen via search (statusline tools: CCometixLine 3,574 licence NONE; claude-statusline 1,404 MIT) are not token-savers; skipped.

## What TZ already has (so not a gap)
`tz stats` (measured vs EST, minus own overhead), `tz recall` (lossless trim recall), `tz doctor`, `tz learn`, `tz ab`, 5h/7d view, handoffs, MIT, no telemetry. Source: `bin/tz` help, `COMPETITIVE-GAP-ANALYSIS.md`.

## Top 5 to copy or learn (ranked by value / effort)

1. **Make `npm i -g token-zombie` true, then add a zero-install `npx` entry.** ccusage, ruflo and rtk all convert on one command. MEASURED: `npm view token-zombie` returns 404 on 2026-11-25, yet README line 20 tells users to `npm i -g token-zombie`. This is the highest-value fix because the documented path may fail. Effort: S (owner must publish; needs npm account, not me). Licence: n/a (own code). Verify the npm name first.
2. **`tz gain` / `tz discover` names for existing stats + a "what the number means" line.** rtk's `gain` is its viral hook; TZ's `tz stats` already has the data (MEASURED output above). Copy the naming and the honesty line ("cut in output is not cut in bill"); TZ's NET-minus-overhead is already stricter. Effort: S (alias + 2 doc lines). Licence: rtk Apache-2.0, name and idea only, no code copied, so no NOTICE needed; log a ledger row.
3. **Per-agent `init` / `wrap` / `unwrap` with `--dry-run` and undo.** headroom wraps 15+ agents in one command; rtk has `init -g`. TZ has `install.sh` and Codex adapters. Add `tz init --dry-run` printing what would change and `tz init --undo`. Never run on live `~/.claude` in tests. Effort: M. Licence: headroom Apache-2.0, rtk Apache-2.0; UX learned only, own implementation.
4. **Benchmark with intervals and honest ranges, then seek third-party reproduction.** caveman links each headline to a dated test with a 95% interval; headroom states "little on prose". TZ's real number is small (MEASURED 0.58% net input from replay of 1,025 chats, per gap analysis), so lead with the honest range and the quality A/B instead. Paid `tz ab` needs owner OK. Effort: M (free replay) to L (paid quality A/B). Licence: n/a.
5. **Terse-output before/after panel and README hook.** caveman's two-column "63 vs 20 tokens" is the single most copied visual; ponytail's "335 lines vs 1" too. TZ has `docs/img/demo.gif` from real output; add a measured before/after of one real trimmed tool output (use `tz recall` pair). Effort: S. Licence: caveman Apache-2.0 / ponytail MIT: copy layout idea only; copying prompt text needs NOTICE entry and ledger row. No invented numbers: use TZ's own recorded event.

## Learn only, do not copy
- context-mode: Elastic License 2.0 (source-available, restricts hosted use). Learn the FTS5 index idea; write own code. Not MIT/Apache/BSD, so no copying.
- claude-squad: AGPL-3.0. Learn UX only; owner rejected auto agent spawning anyway.

## Rules applied
Copy only MIT/Apache/BSD with a NOTICE entry; GPL/AGPL/ELv2/NONE-licence is learn-only; one ledger row per repo before any code is reused (see `OPEN-SOURCE-INTEGRATION-LEDGER.md`). Not covered: Windows (deferred), repos with licence NONE, star-growth rates (UNKNOWN: only totals were read).
