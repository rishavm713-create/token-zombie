#!/usr/bin/env bash
# tz split / lock / hsize: plan shape, lock exclusion + stale takeover, handoff size flags
cd "$(dirname "$0")/.." || exit 1
T=$(mktemp -d); export TZ_LOCK_DIR="$T/locks"; P=0; F=0
ok(){ if eval "$1"; then echo "ok $2"; P=$((P+1)); else echo "FAIL $2"; F=$((F+1)); fi; }
O=$(python3 bin/tz split "run live test on simulator" "fix typo in docs" "live test premiere" --json)
ok "echo '$O' | python3 -c \"import json,sys;r=json.load(sys.stdin);sys.exit(0 if len(r['sessions'])==3 and 'worktree add' in r['sessions'][0]['worktree'] and 'build' in r['rule'] else 1)\"" plan
python3 bin/tz lock acquire live >/dev/null; ok "! python3 bin/tz lock acquire live >/dev/null" lock-busy
python3 bin/tz lock release live >/dev/null; ok "python3 bin/tz lock acquire live >/dev/null" lock-after-release
sleep 1; ok "python3 bin/tz lock acquire live --ttl 0 >/dev/null" lock-stale-takeover
mkdir -p "$T/p/handoffs"; seq 40 > "$T/p/handoffs/2026-11-20.md"
ok "! python3 bin/tz hsize $T/p >/dev/null" hsize-over
seq 5 > "$T/p/handoffs/2026-11-20.md"; ok "python3 bin/tz hsize $T/p >/dev/null" hsize-ok
ok "python3 -c \"import sys;sys.path.insert(0,'bin');import tzsplit as t;assert len(t.detect('1. fix login bug now\n2. add export feature too'))==2 and t.detect('fix the typo')==[]\"" detect-multi
ok "echo '{\"hook_event_name\":\"SubagentStart\",\"session_id\":\"s\",\"cwd\":\"/tmp\"}' | python3 bin/tz-guard.py | grep -q '300 words'" subagent-cap
seq 40 > "$T/p/handoffs/2026-11-21.md"
ok "echo '{\"hook_event_name\":\"SessionStart\",\"session_id\":\"s\",\"cwd\":\"$T/p\"}' | python3 bin/tz-start.py | grep -q 'oversized'" start-hsize
ok "python3 -c \"import sys;sys.path.insert(0,'bin');import tzpolicy as t;e=lambda **k:[a['id'] for a in t.evaluate(k,{'spawns':6},t.DEFAULT)];assert 'fake_green' in e(tool_name='Edit',tool_input={'file_path':'a/test_x.py','new_string':'@pytest.mark.skip'});assert 'fake_green' not in e(tool_name='Edit',tool_input={'file_path':'a/x.py','new_string':'@pytest.mark.skip'});assert 'spawn_cap' in e(tool_name='Agent',tool_input={});assert 'prefix_edit' in e(tool_name='Edit',tool_input={'file_path':'/p/CLAUDE.md','new_string':'x'})\"" policy-fakegreen-spawn
ok "python3 bin/tz code fix the login bug --json | python3 -c \"import json,sys;r=json.load(sys.stdin);sys.exit(0 if [x['phase'] for x in r][:3]==['plan','build','debug'] and len(r)==7 else 1)\"" code-pipeline
echo "pass $P fail $F"; [ $F = 0 ]
