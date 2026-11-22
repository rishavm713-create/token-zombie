# Launch kit (drafts; post only after real A/B evidence and host verification exist)
Rule: no fake stars, no spam, follow each community's self-promotion rules. Claims must match docs/AUDIT.md.

## 10-second pitch
TOKEN ZOMBIE watches your Claude Code agents, flags wasted work (repeat reads, retry loops, stalled agents), keeps originals recoverable, and reports MEASURED vs EST savings. Local only.

## Hacker News (Show HN)
Title: Show HN: TOKEN ZOMBIE, a local watcher that measures how much your coding agents waste
Body: what it is (3 lines); what is measured vs estimated; what is NOT done (A/B proof status, exact numbers once run); install; link to docs/AUDIT.md. Ask for failure reports, not praise.

## Reddit (r/ClaudeAI and similar; check each sub's rules first)
Same body, shorter, lead with the demo GIF and the honest "what is not proven yet" line.

## X thread
1 hook: "I built a watcher for my AI agents. It measures how much they waste." 2 demo GIF. 3 what is measured. 4 what is estimated. 5 what is not proven. 6 repo link.

## LinkedIn
Problem (agent spend is invisible) -> what I built -> the honesty rule (MEASURED/EST/UNAVAILABLE) -> link.

## FAQ
- Does it save tokens? It reports measured duplicate-read denials and trims; whole-session net savings need the A/B runs in docs/BENCHMARK-METHOD.md.
- Does it send data anywhere? No network, all state in ~/.claude/token-zombie.
- Can it break my setup? Install is idempotent with --dry-run/--check/--uninstall/--restore; hooks fail open.
- Other hosts? Adapters are experimental.
- Vs RTK / Claude-Mem / Superpowers? Different jobs: TZ measures and advises across the whole session; use them alongside.

## Demo outline (30 s, owner records)
0-5 s repeated read; 5-12 s TZ warning with evidence; 12-20 s `tz recall` restores original; 20-27 s `tz live agents` + `tz hooks live`; 27-30 s honest label screen.
