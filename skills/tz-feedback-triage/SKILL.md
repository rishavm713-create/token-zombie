---
name: tz-feedback-triage
description: Turn customer feedback and error reports (Gmail, Sentry via MCP) into fixes: clear bugs get fixed straight away, anything needing judgment goes to the owner. Use when feedback or error alerts pile up and the connectors are set up.
license: MIT
---
# feedback-triage
Idea source: interview with the Vercel CEO on working with AI agents (2026), as summarised in a pasted list of 7 tips. Own wording.
Needs Gmail and Sentry MCP servers; if absent say so and stop. Read-only until a fix is chosen.
1. Pull new feedback and unresolved errors; group duplicates.
2. Clear bug (reproducible, one obvious fix, low risk): fix on a branch, add a test, report.
3. Needs judgment (product choice, risky zone, unclear): list for the owner with a one-line recommendation.
4. Never reply to customers or close tickets without the owner's OK.
