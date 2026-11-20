# TOKEN ZOMBIE v0.3.0

TOKEN ZOMBIE is a local-first token saver for Claude Code. It makes no network calls and sends no telemetry.

## Install
```
/plugin install token-zombie --marketplace rishavm713-create/token-zombie
```
- **Shell:** `claude plugin install token-zombie --marketplace rishavm713-create/token-zombie`
- **Desktop app:** **+** next to the prompt box > **Plugins** > **Add marketplace** `rishavm713-create/token-zombie` > **Add plugin**.
- **Optional cost row:** `bash <plugin dir>/install.sh --statusline-only`.
- **Legacy install:** if you used the old `install.sh` hook install, run `bash install.sh --uninstall` first. Otherwise every hook fires twice.

## What is new
- **Plugin and marketplace:** 8 commands, `/token-zombie:tz|optimize|audit|review|compact|board|supervisor|benchmark`.
- **Toolbar Mod:** one slim bar above the prompt.
  - It shows the mascot, the mode, AGENTS, SKILLS ON, TOKENS SAVED · EST and OPTIMIZATIONS.
  - The chevron, or `/tz`, opens a detail pane. Its buttons are mode, Copy, Review, Audit, Board and Compact.
- **Modes:** off, lite, full and ultra (`tz mode`).
- **HTML dashboard** (`tz dash --out FILE`, or `--serve` on 127.0.0.1 with a token): the same bar as a collapsible summary, plus metric cards.
- **Zombie mascot:** five states with a fixed priority: alert, excited, working, sleep, idle.

## Honest numbers
- Every metric is labelled MEASURED, EST or UNKNOWN.
- TOKENS SAVED counts only output that tz actually cut, net of its own overhead. It is an estimate (characters / 4).
- There is no with/without A/B baseline yet, so it is **not** a proven end-to-end saving.
- SKILLS ON counts enabled skills, not skills that were used.
- Full rules: [docs/METRICS.md](METRICS.md).

## Compatibility
- Claude Code >= 2.1.318 is tested.
- macOS is tested. Linux runs in CI. Windows is untested.
- Other agents are rules-only and EXPERIMENTAL ([COMPAT.md](../COMPAT.md)).

## Tests
- `bash tests/run_all.sh`: 517 shell checks.
- `claude plugin test .`: 14 Mod tests.
- Both run in a throwaway HOME.
