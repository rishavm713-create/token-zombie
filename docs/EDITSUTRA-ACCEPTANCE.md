# EditSutra acceptance (2026-11-24, TZ 2.0 + Windows patch, run on ~/EditSutra)
| Step | Result |
|---|---|
| `tz resume` | worked (<1 s): state CLEAN vs handoff, next action read from handoffs/2026-11-24.md; flagged "UNVERIFIED: no passing test at handoff" |
| `tz map` | 11,046 chars for 2,577 tracked files (~123M chars of tracked text) |
| `tz rank --n 15` | 735 chars; top defs in panel/js/platform.js, licence.js |
| `tz exists transcribe` | 163 chars; found 3 existing defs (engine.js transcribeMedia/transcribeMediaOnce, uxp.js transcribe) |
| `tz gate` | ran (4 s); no test command detected (EditSutra has no package.json test script) |
| Real task | offline test test/caption_looks_test.mjs was failing: it expected 9 caption looks, the code has 9 + 23 `g-*` looks since commit 4ba2f66 (intended). Test updated to check both; now passes. Other offline tests pass: judge 12, spelling 7, licence_trial 1, clamp_words, licence_device. test/panel/dl_test.mjs needs live Premiere (not run). |

What TZ saved here: MEASURED output sizes above. Exploration saved vs working without TZ: UNKNOWN (no side-by-side run). `tz exists` pointed at the 3 transcribe functions without opening files; `tz gate` did not find EditSutra's tests (no standard test runner), a real gap.
