#!/bin/bash
# Phase 1 gap detectors: agents queued/failed, abandoned, stalled (real ledger signals, fake HOME).
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; pass=0; fail=0
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
R=$(HOME="$T" PYTHONPATH="$Z/bin" python3 - <<'P'
import tzlive, time, json
n=1000000
s=tzlive.blank()
s['agents']={'a':dict(status='starting',t0=n-400),'b':dict(status='starting',t0=n-10),'c':dict(status='failed',t0=n-50),
 'd':dict(status='running',t0=n-4000),'e':dict(status='interrupted',t0=n-9),'f':dict(status='done',t0=n-9)}
s['last_t']=n-700; s['rep']=dict(k='x',n=5)
print(json.dumps(tzlive.detect(s,n)))
s2=tzlive.blank(); s2['last_t']=n-5
print(json.dumps(tzlive.detect(s2,n)))
print(json.dumps(tzlive.detect(None,n)))
for i in range(4): tzlive.on_event(dict(session_id='g',hook_event_name='PostToolUse',tool_name='Bash',tool_input={'command':'ls'}),now=n+i)
print(json.dumps(tzlive.detect(tzlive._load(tzlive.path('g')),n+5)))
P
)
l1=$(echo "$R"|sed -n 1p); l2=$(echo "$R"|sed -n 2p); l3=$(echo "$R"|sed -n 3p); l4=$(echo "$R"|sed -n 4p)
j() { echo "$1" | python3 -c "import json,sys;d=json.load(sys.stdin);print($2)"; }
ok "queued=2" '[ "$(j "$l1" "d[\"queued\"]")" = 2 ]'
ok "stuck queued=1" '[ "$(j "$l1" "d[\"stuck_queued\"]")" = 1 ]'
ok "failed=1" '[ "$(j "$l1" "d[\"failed\"]")" = 1 ]'
ok "abandoned=2 (old running + interrupted)" '[ "$(j "$l1" "d[\"abandoned\"]")" = 2 ]'
ok "stalled: idle + repeat" '[ "$(j "$l1" "len(d[\"stalled\"])")" = 2 ]'
ok "quiet session: no stall" '[ "$(j "$l2" "len(d[\"stalled\"])")" = 0 ]'
ok "bad input fail-open" '[ "$l3" = "{}" ]'
ok "repeat counted from real events" '[ "$(j "$l4" "len(d[\"stalled\"])")" = 1 ]'
echo "gaps_p1: pass $pass fail $fail"; [ $fail = 0 ]
