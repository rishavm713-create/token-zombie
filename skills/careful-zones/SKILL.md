---
name: careful-zones
description: Protect the parts of an app that matter most: list must-not-trade-off rules in CLAUDE.md, back each with a test, add quality gates and run a security scan after each feature. Use when agents write most of the code, before real customers arrive, or after a security/quality slip.
license: MIT
---
# careful-zones
Idea source: interview with the Vercel CEO on working with AI agents (2026), as summarised in a pasted list of 7 tips. Own wording.
1. Pick the zones where a mistake is costly (auth, payments, user data, deletes, migrations).
2. Add a "Must not trade off" section to CLAUDE.md: one line per rule, each naming the test that enforces it. A rule with no test is not done.
3. Quality gate per zone: tests pass, no new lint/type errors, a fresh reviewer agent reads the diff.
4. After every feature run a security scan (dependency audit, secret scan, a tool such as DeepSec if installed) and fix before moving on.
5. Never relax a rule to finish a task; ask the owner instead.
