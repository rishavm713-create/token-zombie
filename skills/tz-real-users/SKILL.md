---
name: tz-real-users
description: Checklist for software about to meet real customers: test before choosing, direction check vs PRD, careful zones with must-not-trade-off rules plus tests, breaker agent, first-time-user agent, feedback triage. Use before release or when agents wrote most of the code; skip for small fixes.
license: MIT
---
# tz-real-users
Idea source: interview with the Vercel CEO on working with AI agents (2026), as summarised in a pasted list of 7 tips. Own wording. Full versions live in TZ Studio.
1. Test before choose: small real trial, fresh agent checks from scratch; decide on results.
2. Direction check: list PRD requirements, mark Done/Partial/Missing/Drifted with proof, top 3 gaps.
3. Careful zones: "Must not trade off" lines in CLAUDE.md, each backed by a test; security scan after each feature.
4. Breaker: agent tries to break the app on a copy of the data; reports, does not fix.
5. First-time user: agent without code access walks each key flow; tally error-free sessions.
6. Feedback triage (Gmail/Sentry MCP): fix clear bugs, send judgment calls to the owner.
Run only the steps the release needs.
