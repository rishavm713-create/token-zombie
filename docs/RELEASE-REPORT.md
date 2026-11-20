# TOKEN ZOMBIE v0.3.0 release report (2026-11-21)

Status: **release-ready locally. Not pushed, not published.** The owner's explicit yes is needed before anything leaves this machine.
- Every check ran in a throwaway HOME.
- These were not touched: `~/.claude/settings.json`, the installed skill and the live hooks.

## Hardening done in this round
1. **Privacy**
   - `tests/test_tz.sh` no longer reads the owner's real project folder. The real-project size check is now a generated oversized project, and it is stricter: it must hit the 4000-char cap.
   - Private fixture names were replaced with `demo-skill` / `demo-mcp`.
   - `tz-start.py` test calls now run under the fake HOME.
   - `tests/test_bench.sh` runs under its own temp HOME. It still checks that its state dir is left untouched.
   - `bin/tzstartup.py` no longer hard-codes two machine-specific plugin names.
2. **Dashboard responsiveness**
   - The bar now wraps its metrics to a second row at <= 820 px (it was 640 px).
   - A 4 px gap stops the mascot's feet touching the metric row.
   - The compact one-row bar is unchanged above 820 px.
3. **Mascot consistency**
   - The dashboard chip shows only the animated state (it used to show "SLEEP · excited").
   - Priority is fixed and identical in Python and in the Mod: alert, excited, working, sleep, idle.
4. **Metric honesty**
   - The skills metric counts enabled skills on disk, not invocations. It is now labelled **SKILLS ON** on the bar and **SKILLS ENABLED** on the card.
   - [docs/METRICS.md](METRICS.md) documents each formula, source, label and limit, and separates measured, estimated and verified-baseline savings.
5. **Docs**
   - CHANGELOG v0.3.0 is complete, with the test count corrected.
   - README has a Toolbar section.
   - PANEL.md has a toolbar section.
   - SECURITY.md keeps all of the old `docs/SECURITY.md` content and adds a line on the Mod.
   - `docs/RELEASE-NOTES-0.3.0.md` is new.
   - The marketplace now has a `description`.
   - The dashboard captures were regenerated from demo data.

## A. Automated tests (no live host)
| Check | Result |
|---|---|
| `bash tests/run_all.sh`, 20 scripts | `TOTAL pass 517 fail 0` (was 515; +2 new dash2 checks) |
| `claude plugin test .` | 14 pass, 0 fail (11 existing + 3 in `panel.live.test.tsx`) |
| `claude plugin validate .` | passed; 1 warning: no plugin icon |
| `scan_secrets` | 140 files, no key or token format found |
| Hygiene grep over the 132 files git would publish | no emails, home paths, private project names, hostnames, private IPs or real keys; the only `sk-ant-` string is a fake redaction fixture |
| Suite run with an empty outer HOME | 517/517 with HOME set to an empty dir. 0 files were written to it. In the real `~/.claude/token-zombie`, only `activity.json`, `status.json` and `guard-<id>` changed, all written by the live hooks of the session that ran the checks. |

New tests this round:
- `test_dash2`: the mascot chip equals the animated state, both with data (EXCITED) and with no data (SLEEP).
- Labels updated in `test_dash2` and the Mod tests: SKILLS ON / SKILLS ENABLED.
- `test_tz`: the oversized-project start cap.

## B. Simulated integration (real code, fake host or fake HOME)
- **Mod metrics:** `mock.clock` advances the 5 s poll.
  - AGENTS 1→4, with `agents.json` rewritten.
  - SKILLS ON 1→3.
  - TOKENS SAVED 100→300.
  - OPTIMIZATIONS 1→3.
- **Mod interactions:** the chevron opens the pane; `/tz` opens the pane, or falls back to the status line; the mode, Review, Audit, Board, Copy and Compact buttons run the expected argv; a refused compact shows the line to type.
- **Reload:** `$.state` totals survive a second `session.start`. A value stored under an old shape is declined.
- **Real `tz` CLI** in a fake HOME:
  - `mode ultra` / `mode full` exit 0, and `config.json` persists the mode.
  - `optimize`, `audit` and `dash --out` exit 0.
  - `checkpoint` exits 1 with no task state. Compact still asks for `/compact`.
- **Dashboard** from real files:
  - agents 2→5, skills 1→3, saved 700→1.9K.
  - The `tz dash --serve` server returns 401 without the token, and sends a CSP.
- **Responsive**, in the built-in browser with the worst-case data (ULTRA, 1.2M saved):
  - Widths 375, 600, 674, 780, 860, 1100 and 1440 px, collapsed and expanded.
  - Every width: 0 clipped labels, 0 overlapping bar items, 0 overlapping cards, no horizontal scroll.
  - The `<details>` body is visible when open and hidden when closed (real clicks, earlier round).
- **Clean install** in a fake HOME:
  - `claude plugin install token-zombie --marketplace ./` gives v0.3.0, enabled, read from the repo folder.

## C. Actual live host verification
- The owner saw the toolbar live in Claude Code on 2026-11-20 and 2026-11-21: the bar, and the mascot's hands on its border.
- The Mod was loaded from the dev-mods copy and wrote a real `agents.json`.
- `hooks/panel.tsx` is synced to the dev-mods copy with this round's label change.
- **Not verified live** in this round:
  - the new SKILLS ON label in the app
  - pane buttons pressed by hand
  - `/tz` typed by hand
  - a hot reload in a real session
  - an install from GitHub (the repo does not exist yet)

## D. Remaining limitations
- TOKENS SAVED is an estimate (chars / 4) of `tz filter` cuts only. There is **no A/B baseline**, so it is not a proven saving.
- AGENTS needs the Mod loaded (otherwise UNKNOWN). Several sessions share one `agents.json`.
- SKILLS ON counts enabled user skills. It does not count plugin or project skills, and it does not count usage.
- The Mod's token totals are per session. They survive a hot reload but not a new session.
- The Mod tests need the `claude` CLI, so CI runs only the shell suite.
- The terminal bar draws an emoji, not the SVG mascot.
- Windows is untested. Non-Claude adapters are rules-only.
- There is no plugin icon.

## Install (after publication)
```
/plugin install token-zombie --marketplace rishavm713-create/token-zombie
```
- **Shell:** `claude plugin install token-zombie --marketplace rishavm713-create/token-zombie`.
- **Optional cost row:** `bash <plugin dir>/install.sh --statusline-only`.
- **Legacy install:** if the old hook install is present, run `bash install.sh --uninstall` first.

## Manual steps for the owner, in order
1. Set the git identity to publish under: `git config user.name` / `git config user.email`.
2. Give an explicit yes to create the public repo `rishavm713-create/token-zombie` and push `main`.
3. After the push, install from GitHub in a clean Claude Code session. Check the bar, the chevron, `/tz` and each pane button by hand. Then take the toolbar capture for the README.
4. Optional: add a plugin icon.
