# Group 2 status (branch feat/v2.1-repos-g2)
Tests: every tests/v21/test_g02_*.py run as a script; results below.
| repo | licence | result |
|---|---|---|
| harbor | Apache-2.0 | ported: `bin/tzscrub.py` secret scrub that keeps JSON valid (adapted, NOTICE); test_g02_harbor.py |
| terminal-bench | Apache-2.0 | already ported as `bin/tztbench.py`; added test_g02_terminalbench.py (load, parse, resolve, pass@k) |
| rea (morluto) | MIT | read: RE tool, nothing to port as code; idea `mark_untrusted()` (tag tool output as data) in tzscrub.py |
| Continuous-Claude-v3 | MIT | ported idea: `bin/tzdiag.py` post-edit syntax check (own code); test_g02_continuous_claude.py |
| token-zombie (self) | MIT | published repo HEAD 7e2ee6a is an ancestor of this branch; nothing to port; test_g02_token_zombie.py |
Earlier g2 repos (rtk, serena, langfuse, context-mode, superpowers, mattpocock, tokeneconomizer): see their tests.
Fixed: test_g02_langfuse.py leaked a `sess/subagents` fixture into the recorded-only check (test bug, not tztrace).
Not done: Windows run, real harbor/terminal-bench runs, hooks wired later (test_g02_wiring.py). See the ledger for current status.
