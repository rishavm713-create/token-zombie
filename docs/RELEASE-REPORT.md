# TOKEN ZOMBIE v0.3.0 release report (2026-11-21)

Status: **ready for GitHub publication, waiting on the owner's explicit yes.** Nothing is pushed.
Every check below ran in a throwaway HOME. The real `~/.claude/settings.json`, `~/.claude/skills/token-zombie` and live hooks were not touched.

## 1. The four bar metrics follow their real sources

| Metric | Source | Mod evidence (`claude plugin test`) | Dashboard evidence |
|---|---|---|---|
| AGENTS | `$.agent.list()` running count; the Mod writes `~/.claude/token-zombie/agents.json` for the dashboard | `panel.live.test.tsx`: 1 then 4 after the source changes; `agents.json` rewritten with `running` 1 then 4 | `tz dash --out`: 2 then 5 after `agents.json` changed; stale file shows UNKNOWN (`test_dash2`) |
| SKILLS | `~/.claude/skills/*/SKILL.md` (re-listed at most once a minute) | 1 then 3 after 61 s on the mock clock | 1 then 3 after two skill folders were added |
| TOKENS SAVED (EST) | `ledger.json`: measured, non-overhead entries minus overhead | 100 then 300 | 700 then 1.9K (700 + 1300 - 50) |
| OPTIMIZATIONS | `ledger.json`: count of measured, non-overhead entries | 1 then 3 | 1 then 2 |

The new test advances the Mod's 5 s `$.clock.every` poll with `mock.clock`, so the bar must redraw from the new values. No number is invented: a source that is missing shows `—` or UNKNOWN.

## 2. Interactions

- Chevron (`tz-expand`) opens the pane: `ui.open('token-zombie')` is called (`panel.test.tsx`, "chevron opens the pane").
- `/tz` opens the pane. When no surface places a pane, it falls back to a status line (`/tz opens the pane ...`).
- Pane buttons (`buttons run the expected argv ...`):
  - mode: `tz mode ultra`
  - review: `tz optimize`
  - audit: `tz audit`
  - board: `tz dash --out ~/.claude/token-zombie/board.html`
  - copy: clipboard summary
  - compact: `tz checkpoint`, then `/compact` with the keep-list
- When the host refuses compact, the pane shows the line to type.
- The same CLI commands also ran for real in a fake HOME:
  - `mode ultra` and `mode full` both exit 0, and `config.json` persisted the mode.
  - `optimize`, `audit` and `dash --out` all exit 0. The board was 24 KB.
  - `checkpoint` exits 1 ("no task state") in an empty HOME. The Compact button still goes on to request `/compact`.
- Dashboard `<details>`: tested in the browser with real clicks on `tz dash --serve`. It starts closed, and the summary click opens it and closes it (`open` true/false, content visibility true/false).
- Dashboard server security: no token gives HTTP 401. The page is served with CSP `default-src 'none'; style-src 'unsafe-inline'`.

## 3. Persistence and reload

- `$.state` atoms (`stats`, `files`, `acts`, `note`, `bar`) are kept by the host for the session. A hot reload re-runs `register` and `session.start` and keeps them.
  - Test: token totals survive a second `session.start`.
  - Test: a value stored under an older shape tag is declined, and the pane does not crash.
- Module variables (pane-placed flag, SVG cache, skills and agents throttles) reset on reload. Each is only a cache and is rebuilt on the next poll.
- Across sessions, the Mod does not use `$.store`. Everything that must last is already on disk:
  - the mode (`config.json`)
  - the ledger, `agents.json`, `status.json` and `host.json`
- The pane's token totals are per-session by design (docs/PANEL.md).

## 4. Docs and security

- README install was tested in a fake HOME. `claude plugin install token-zombie --marketplace ./` added the marketplace, and the install showed v0.3.0, enabled.
- The `owner/repo` form in the README cannot be tested until the repo exists.
- `claude plugin validate`: passed with 2 warnings, no marketplace `description` and no plugin icon. Both are cosmetic.
- `scan_secrets` (plugin-authoring): 136 files scanned, no known key or token format found.
- Hygiene grep over the 129 files git would publish:
  - No email addresses, home-folder paths, real keys, internal hosts or private IPs.
  - The only `sk-ant-` string is a fake fixture in `tests/test_status_read.sh`, used to test redaction.
  - The GitHub handle `rishavm713-create` appears in README, docs/INSTALL.md and `.github/ISSUE_TEMPLATE/config.yml`. This is intended.
  - **Finding:** `tests/test_tz.sh` line 58 runs `tz-start.py` against `$REAL/EditSutra` with the real HOME (read-only). Lines 152-188 use `editsutra` and `premiere-pro` as fixture names. These are the owner's private project names. The owner should decide whether to rename them before publishing (see manual steps).
- CHANGELOG: the v0.3.0 entry says "Tests: 377 -> 477". It has no line for the slim bar or the mascot changes (commits a8dcdd2, bc48121).
- COMPAT: accurate (Claude Code >= 2.1.318 tested; macOS tested; other agents rules-only and EXPERIMENTAL).
- Those doc files are owned by the docs session, so this report does not edit them.

## 5. Test suite

- `bash tests/run_all.sh`: see the result line below.
- `claude plugin test .`: 14/14. That is the 11 existing tests plus 3 new ones in `hooks/panel.live.test.tsx`.
- CI does not run the Mod tests (the runner has no `claude` CLI). `test_plugin.sh` skips `validate` there.

Result on 2026-11-21: `TOTAL pass 515 fail 0`. That is 20 scripts, each with fail 0, and it matches the baseline.

## Install (after publication)

In Claude Code:
```
/plugin install token-zombie --marketplace rishavm713-create/token-zombie
```
Shell: `claude plugin install token-zombie --marketplace rishavm713-create/token-zombie`.
Optional cost row: `bash <plugin dir>/install.sh --statusline-only`.
If the old hook install is present, run `bash install.sh --uninstall` first. Otherwise every hook fires twice.
Then type `/tz` in a session, or click the chevron on the bar above the prompt.

## Remaining manual steps (owner)

1. Decide on the `EditSutra` / `premiere-pro` names in `tests/test_tz.sh` (rename them to neutral names, or keep them). If you rename, keep the checks.
2. Let the docs session commit its README/LICENSE/CONTRIBUTING/SECURITY/.github/docs files, including the staged deletion of `docs/SECURITY.md`. Then update the CHANGELOG test count and add the slim-bar line.
3. Optional: add a marketplace `description` and an icon to clear the two validate warnings.
4. Set the git identity you want to publish under (`git config user.name/user.email`). Recent commits use the machine's default local address.
5. Give an explicit yes to create the public repo `rishavm713-create/token-zombie` and push. Then run `scan_secrets` again on the final tree.
6. After the push, install with the README one-liner in a clean Claude Code. Check that the bar shows, that `/tz` and the chevron open the pane, and take the panel capture for the README.
7. Known cosmetic issue: between about 600 and 780 px wide, the dashboard bar clips the AGENTS/SKILLS/OPTIMIZATIONS labels with an ellipsis. They are fine at 375, 800, 1100 and 1440 px.
8. The dashboard chip reads "mascot SLEEP · excited". It shows the status-bus mascot next to the bar's visual state, which can look contradictory.

No token-savings claim is made: there is still no A/B baseline.
