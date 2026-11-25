#!/bin/bash
# tz next: tasks, deps, gates, dup prevention, pack cap, test-pass checkpoint, limit checkpoint, measure, failure handling. Fake HOME, offline.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; P="$T/p"; pass=0; fail=0; mkdir -p "$H/.claude" "$P"
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
n() { HOME="$H" python3 "$Z/bin/tznext.py" --cwd "$P" "$@"; }
n add a --title "Build A" --goal "goal A" --file bin/a.py --next "write a" >/dev/null
n add b --title "Build B" --dep a >/dev/null
n add c --title "Publish" --dep b --gate publish >/dev/null
ok "persisted as handoffs/tasks/T-*.json" '[ -f "$P/handoffs/tasks/T-a.json" ]'
o=$(n add a --title x); r=$?; ok "duplicate id refused, file kept" '[[ $o == *duplicate* && $r = 1 ]] && grep -q "Build A" "$P/handoffs/tasks/T-a.json"'
o=$(n add z --title "build a"); ok "duplicate title refused" '[[ $o == *duplicate* ]]'
o=$(n add q --title Q --dep nope); ok "unknown dep refused" '[[ $o == *"bad deps"* ]]'
o=$(n add q --title Q --gate wat); ok "bad gate refused" '[[ $o == *"bad deps"* ]]'
o=$(n); ok "list: NEXT is a (b,c blocked by deps)" '[[ $o == *"NEXT: a"* ]]'
o=$(n start b); r=$?; ok "start with deps undone refused" '[[ $o == *dependencies* && $r = 3 ]]'
n start a >/dev/null; o=$(n pack); ok "pack has goal/files/next, no test yet" '[[ $o == *"goal A"* && $o == *bin/a.py* && $o == *"write a"* && $o == *"none yet"* ]]'
o=$(n start b); ok "second active refused" '[[ $o == *dependencies* || $o == *active* ]]'
o=$(n done a --test "true"); ok "done without --yes does not run" '[[ $o == *"--yes"* ]] && grep -q pending "$P/handoffs/tasks/T-b.json"'
o=$(n done a --test "echo boom && exit 1" --yes); r=$?; ok "failed test: task stays active, failure recorded" '[[ $o == *"test failed"* && $r = 3 ]] && grep -q "\"ok\": false" "$P/handoffs/tasks/T-a.json" && grep -q "\"status\": \"active\"" "$P/handoffs/tasks/T-a.json"'
o=$(n done a --test "echo 7 passed" --yes); ok "passing test: done + verified" '[[ $o == *"done, verified"* ]]'
o=$(n start a); ok "done task not restarted/overwritten" '[[ $o == *"already done"* ]]'
n start b >/dev/null; n done b --test "echo ok" --yes >/dev/null
o=$(n); ok "gated task is NEXT but flagged stop-and-ask" '[[ $o == *"NEXT: c"* && $o == *"stop and ask"* ]]'
o=$(n start c); r=$?; ok "gated start refused without approval" '[[ $o == *"GATE publish"* && $r = 3 ]]'
o=$(n start c --approved); ok "gated start only with explicit --approved" '[[ $o == active ]]'
n add d --title D --dep c >/dev/null
# pack cap + <=2k tok
python3 - "$P" <<'PY'
import json,sys,glob
p=sys.argv[1]+'/handoffs/tasks/T-c.json'; t=json.load(open(p)); t['goal']='x'*50000; json.dump(t,open(p,'w'))
PY
o=$(n pack); ok "pack capped at 2k tokens (8000 chars)" '[ ${#o} -le 8000 ]'
# tz-start injects pack for active task only
s=$(echo "{\"cwd\":\"$P\",\"source\":\"startup\"}" | HOME="$H" python3 "$Z/bin/tz-start.py")
ok "tz-start injects active task pack" '[[ $s == *"task pack [c]"* ]]'
# hook: verified test pass -> record + checkpoint; failure -> nothing
g() { echo "$1" | HOME="$H" TZ_SUP=0 python3 "$Z/bin/tz-guard.py"; }
FAILJ="{\"session_id\":\"s1\",\"cwd\":\"$P\",\"hook_event_name\":\"PostToolUse\",\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"bash tests/run_all.sh\"},\"tool_response\":{\"stdout\":\"TOTAL pass 5 fail 2\"}}"
g "$FAILJ"; ok "failing test output does not record a pass" '! grep -q "\"src\": \"hook\"" "$P/handoffs/tasks/T-c.json"'
PASSJ="${FAILJ/pass 5 fail 2/pass 5 fail 0}"
o=$(g "$PASSJ"); ok "verified pass: recorded on active task + checkpoint, no output" '[ -z "$o" ] && grep -q "\"src\": \"hook\"" "$P/handoffs/tasks/T-c.json" && grep -q verified-test-pass "$P/handoffs/tasks/T-c.json"'
NONT="${PASSJ/bash tests\/run_all.sh/ls}"; python3 - "$P" <<'PY'
import json,sys
p=sys.argv[1]+'/handoffs/tasks/T-c.json'; t=json.load(open(p)); t['test']={}; json.dump(t,open(p,'w'))
PY
g "$NONT"; ok "non-test command ignored" '! grep -q "\"src\": \"hook\"" "$P/handoffs/tasks/T-c.json"'
CHAIN="{\"session_id\":\"s1\",\"cwd\":\"$P\",\"hook_event_name\":\"PostToolUse\",\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"cd x && bash tests/run_all.sh 2>&1 | tail -1; bin/tz state\"},\"tool_response\":{\"stdout\":\"TOTAL pass 5 fail 0\"}}"; g "$CHAIN"
ok "chained command: only the test segment is recorded" 'grep -q "\"cmd\": \"bash tests/run_all.sh\"" "$P/handoffs/tasks/T-c.json"'
# before-limit checkpoint
big=$(python3 -c "print('x'*900000)"); echo "$big" > "$T/big.txt"
TR="$H/.claude/projects/x"; mkdir -p "$TR"
n checkpoint --next manual >/dev/null; ok "manual checkpoint saved" 'grep -q manual "$P/handoffs/tasks/T-c.json"'
python3 - "$Z" "$P" <<'PY'
import sys,os,json; sys.path.insert(0,sys.argv[1]+'/bin'); import tznext
tznext.checkpoint(sys.argv[2],'before-limit')
assert json.load(open(sys.argv[2]+'/handoffs/tasks/T-c.json'))['checkpoint']['reason']=='before-limit'
PY
ok "before-limit checkpoint path works, gated task untouched" '[ $? = 0 ] && grep -q "\"gate\": \"publish\"" "$P/handoffs/tasks/T-c.json"'
# corrupt task file: skipped, no crash
echo "{bad" > "$P/handoffs/tasks/T-bad.json"; o=$(n); ok "corrupt task file skipped" '[[ $o == *"NEXT"* ]]'
# resume with only local state in a fresh process
o=$(HOME="$T/empty" python3 "$Z/bin/tznext.py" --cwd "$P" pack); ok "fresh process resumes from files only" '[[ $o == *"task pack [c]"* ]]'
o=$(cd "$P" && HOME="$T/empty" python3 "$Z/bin/tz" resume 2>&1); ok "tz resume falls back to tz next pack when no tz handoff" '[[ $o == *"from tz next"* && $o == *"task pack [c]"* ]]'
# measure
python3 - "$T/s1.jsonl" <<'PY'
import json,sys
L=[]
def a(i,inp,cc,cr,out,cmd=''):
    c=[{"type":"tool_use","input":{"command":cmd}}] if cmd else []
    L.append(json.dumps({"type":"assistant","message":{"id":f"m{i}","content":c,"usage":{"input_tokens":inp,"cache_creation_input_tokens":cc,"cache_read_input_tokens":cr,"output_tokens":out}}}))
a(0,10,5000,0,50); a(1,5,100,5000,200); a(2,5,100,5100,100,"bash tests/run_all.sh"); a(3,5,100,5200,100)
open(sys.argv[1],'w').write('\n'.join(L)+'\n')
PY
o=$(n measure --transcript "$T/s1.jsonl"); ok "measure: startup 5010, repeated 15300, verify 205, work 510" '[[ $o == *"startup 5010"* && $o == *"repeated ctx 15300"* && $o == *"verify 205"* && $o == *"work 510"* && $o == *"4 replies"* ]]'
o=$(n measure --transcript "$T/none.jsonl" 2>&1); ok "missing transcript handled" '[[ $o != *Traceback* ]]'
o=$(HOME="$H" python3 "$Z/bin/tz" next --cwd "$P"); ok "tz next registered in CLI" '[[ $o == *"T"* || $o == *"NEXT"* ]]'
echo "pass: $pass fail: $fail"; [ $fail = 0 ]
