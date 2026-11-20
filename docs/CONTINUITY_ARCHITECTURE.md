# Continuity architecture
bin/tznext.py (new): tasks, ready(), pack(), checkpoint(), on_tool(), measure(). Reuses tzhandoff (run_test, checkpoint, git snapshot), tzusage (find_transcript), tzlive (overhead).
Hooks: tz-start.py -> tznext.pack; tz-guard.py -> tznext.on_tool + tznext.checkpoint (all output via emit(); tznext emits none).
CLI: `tz next` in `mods` of bin/tz. tzhandoff.newest_task ignores `T-*.json` (tznext files) so old handoff/resume is unchanged.
Flow: add tasks -> start (deps/gate checked) -> work -> test pass auto-checkpoints -> done (test must pass) -> next eligible.
