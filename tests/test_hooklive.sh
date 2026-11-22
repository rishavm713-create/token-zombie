#!/usr/bin/env bash
# tz hooks live: p50/p95/fail aggregated from live-<sid>.json written by the guard (temp HOME)
cd "$(dirname "$0")/.." || exit 1
H=$(mktemp -d); P=0; F=0
HOME=$H python3 - <<'Y'
import sys; sys.path.insert(0,'bin')
import tzlive
for i,ms in enumerate([10,20,30,40,100]): tzlive.timing('s1','Stop',ms,40,failed=(i==4))
tzlive.timing('s2','Stop',50,0)
Y
O=$(HOME=$H python3 bin/tz hooks live --json)
chk(){ if echo "$O" | python3 -c "import json,sys;d=json.load(sys.stdin)['Stop'];sys.exit(0 if $1 else 1)"; then P=$((P+1)); else F=$((F+1)); echo "FAIL $1"; fi; }
chk "d['n']==6"; chk "d['fail']==1"; chk "d['p50']==35.0"; chk "d['p95']==100"; chk "d['max']==100"
echo "pass $P fail $F"; [ $F -eq 0 ]
# interrupted agents: SessionEnd marks still-running agents
H2=$(mktemp -d)
R=$(HOME=$H2 python3 - <<'Y'
import sys,json; sys.path.insert(0,'bin')
import tzlive
for e,a in [('SubagentStart','a1'),('SubagentStart','a2'),('SubagentStop','a1'),('SessionEnd','')]:
    tzlive.on_event({'hook_event_name':e,'session_id':'z','agent_id':a,'agent_type':'Explore'})
print(json.dumps({k:v['status'] for k,v in tzlive._load(tzlive.path('z'))['agents'].items()}))
Y
)
[ "$R" = '{"a1": "done", "a2": "interrupted"}' ] && echo "pass interrupted" || { echo "FAIL interrupted: $R"; exit 1; }
