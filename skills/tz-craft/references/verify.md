# Verify before claiming done

Evidence first, words second. A claim is only as good as the command you ran after the last edit.

- Name the check that would prove the claim (test, build, run, diff). Run it now, in full, and read the output to the end.
- Done means that check passed after your final change. An earlier green run does not count.
- Report what you ran and what it printed. If you did not run something, say "not verified", never "should work".
- unverified_claim: any sentence that says fixed, passing, working, complete or safe with no matching command output behind it. Before sending, scan your own reply for these. Each one gets either a run or a downgrade to "not verified".
- Delegated work (a subagent, a script) is a claim too: look at the changed files or rerun its check yourself.
- A fix for a bug is verified only when the original failing case now passes and the neighbours still pass.
- Say what is left undone in the same message.
