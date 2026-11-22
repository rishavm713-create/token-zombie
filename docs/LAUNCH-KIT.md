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


## Research-backed distribution patterns (22 Nov 2026)

Recent high-growth agent repositories show a few repeatable presentation patterns. These are observations, not a promise of viral growth:

- **A sharp capability hook:** repos such as [morluto/rea](https://github.com/morluto/rea) lead with a surprising, demonstrable job rather than a broad platform claim.
- **An immediately legible workflow:** [Superpowers](https://github.com/obra/superpowers) packages a recognisable development method; [Ponytail](https://github.com/DietrichGebert/ponytail) makes its code-quality promise easy to understand.
- **A concrete before/after:** [Context Mode](https://github.com/mksglu/context-mode) and [Claude Token Optimizer](https://github.com/nadimtuhin/claude-token-optimizer) show the context problem visually and explain what changes.
- **Proof and transparent measurement:** [RTK](https://github.com/rtk-ai/rtk) makes its savings command and measurement approach discoverable. TOKEN ZOMBIE should publish its own methodology and results, not borrow another project's percentages.
- **Distribution beyond the README:** the [Breakscale launch case study](https://launchmaxxing.co/guides/first-1000-github-stars) reports that a short third-party screen recording with a direct repository link drove more discovery than the author's first launch post linking to the website. This is one case study, not a universal conversion rate.

MostStarred's November 2026 research reported that a small number of agent projects reached 100K stars extremely quickly. Those are exceptional outliers with unusual distribution and should not be used as a forecast for TOKEN ZOMBIE. See [fastest repositories to 100K](https://moststarred.com/news/fastest-github-repos-to-100k-stars) and [2026 star growth](https://moststarred.com/trending/year).

## Updated 25-second demo structure

1. **0–4s — pain:** show an actual repeated read or oversized tool result in Claude Code.
2. **4–9s — visibility:** invoke TOKEN ZOMBIE and show the real signal and its MEASURED / EST / UNAVAILABLE label.
3. **9–15s — intervention:** show a supported trim or warning. Do not simulate an action that did not occur.
4. **15–20s — recovery:** use the actual recall mechanism to retrieve the original output.
5. **20–25s — continuity + CTA:** show a real handoff/checkpoint, then the GitHub URL and install command.

Use a direct GitHub repository link in the post or its immediate reply. Do not route the primary CTA only to the product website. Ask viewers to try it and report what failed; do not ask for artificial stars.

## Launch readiness gates

- [ ] Confirm latest tests pass on the commit being released.
- [ ] Complete supported-host install and uninstall verification.
- [ ] Capture a real live toolbar/panel only if verified; otherwise show the CLI and mark dashboard data as demo.
- [ ] Run and publish the A/B benchmark before making net-savings claims.
- [ ] Create a tagged release only after the release contents and changelog are checked.
- [ ] Post once in each relevant community only where self-promotion is allowed; tailor the explanation to that community.


## Public tester call

Use GitHub's [Call for testers issue](https://github.com/rishavm713-create/token-zombie/issues/undefined) as the single feedback destination. Invite developers to test one real workflow and report failures; do not buy stars, use fake accounts, mass-DM strangers or post repetitive promotion.

