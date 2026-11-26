---
name: breaker-agent
description: Run an agent whose only job is to break the app on purpose (bad input, odd order, repeated clicks, huge values, missing permissions), on a copy of the data. Use before release or after a feature touching input, auth or money.
license: MIT
---
# breaker-agent
Idea source: interview with the Vercel CEO on working with AI agents (2026), as summarised in a pasted list of 7 tips. Own wording.
1. Make a copy of the data (test DB or fixtures); never point the agent at real data.
2. Brief the breaker: find inputs and sequences that crash, corrupt or leak. It reports; it does not fix.
3. Try per flow: empty, huge, wrong type, special characters, double submit, out-of-order steps, expired session, other user's ids.
4. Output: each break as steps to reproduce, expected vs actual, severity.
5. Fix the real ones, add a regression test per fix, rerun the breaker once.
