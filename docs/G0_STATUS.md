# G0 status (feat/v2.1-g00)
Tests: every tests/v21/test_g00_*.py run as a script; all pass (7 files, 0 fail) after the final re-run.
Six repos read this round (cloned shallow, read only the needed files; REA is binary-oriented, so not used):
- fast-anything: already ported as bin/tzfast.py (MIT, LICENSE in third_party/fast-anything). Nothing more.
- repomap (MIT): `impact` was missing. Added bin/tzimpact.py (`tz impact NAME`: callers by depth, files, tests to run, risk). Idea-only.
- OpenHands (MIT): condenser (keep first K / last L, forget the middle) was missing. Added bin/tzcondense.py (no LLM).
- mini-swe-agent (MIT): head+tail output cut with elided count added as `cut` in tzcondense. Limits already in tzagent.
- planning-with-files (MIT): 2-action rule is a prompt rule; plan re-injection already in v2.1. Nothing to port.
- SWE-bench (MIT): needs Docker and a benchmark harness; no token saver. Reference only (not cloned).
New test: tests/v21/test_g00_impact_condense.py (19 checks). NOTICE and third_party LICENSE files updated.
Studio deferrals: none (docs/STUDIO-DEFERRED.md).
Not done: no Windows run, no push, merge or tag.
