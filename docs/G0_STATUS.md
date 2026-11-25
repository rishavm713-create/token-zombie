# G0 status (feat/v2.1-g00)
All 12 group-00 repos are integrated; per-repo status and evidence are in docs/OPEN-SOURCE-INTEGRATION-LEDGER.md (rows noted g00).
Added after the first pass: bin/tzplanfiles.py (planning-with-files), bin/tzswebench.py (SWE-bench log grading), tests for tz fast.
Fixed: third_party licences for ai-maestro and fast-anything held the wrong copyright; NOTICE completed.
Opt-in, off by default: crash_restart, learn_loop (its nudge hook is not wired into tz-guard).
Wiring into bin/tz is done on integration/v2.1; planfiles and swebench still need it after re-merge.
Studio deferrals: none (docs/STUDIO-DEFERRED.md).
Not done: no Windows run, no push, merge or tag. No speed or token benefit measured.
