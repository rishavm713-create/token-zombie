# Verify before claiming done

Evidence first. A claim is only as good as the command you ran after the last edit.

1. Name the command that would prove the claim.
2. Run it in full now; read to the end, check exit code and failure count.
3. Report what ran and printed. Not run: say "not verified", never "should work".

| Claim | Needs |
|---|---|
| tests pass | this run, 0 failures |
| build ok | build exit 0 (lint is not a build) |
| bug fixed | original failing case passes, neighbours too |
| regression test | passes, fails with the fix reverted, passes again |
| agent finished | read the VCS diff, rerun its check |
| requirements met | each item checked one by one |

- unverified_claim: fixed, passing, working, complete or done with no matching output. Scan your reply before sending (also before commit or PR): run it or downgrade it.
- Say what is left undone in the same message.
