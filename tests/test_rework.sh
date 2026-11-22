#!/usr/bin/env bash
# tz rework: counts retry loops, repeated calls, repeated edits, fail->pass test cycles from a synthetic log
cd "$(dirname "$0")/.." || exit 1
T=$(mktemp -d); python3 - "$T/l.jsonl" <<'P'
import json,sys
L=[]
def use(i,n,inp): L.append({'message':{'content':[{'type':'tool_use','id':i,'name':n,'input':inp}]}})
def res(i,err): L.append({'message':{'content':[{'type':'tool_result','tool_use_id':i,'is_error':err}]}})
for k in range(3): use(f'f{k}','Bash',{'command':'false'}); res(f'f{k}',True)
use('t1','Bash',{'command':'pytest -q'}); res('t1',True)
use('t2','Bash',{'command':'pytest -q x'}); res('t2',False)
for k in range(3): use(f'e{k}','Edit',{'file_path':'/a/b.py','old_string':str(k)}); res(f'e{k}',False)
open(sys.argv[1],'w').write('\n'.join(json.dumps(x) for x in L)+'\n{"partial')
P
O=$(python3 bin/tz rework "$T/l.jsonl" --json); F=0
P=0
chk(){ echo "$O" | python3 -c "import json,sys;r=json.load(sys.stdin);sys.exit(0 if $1 else 1)" && { echo "ok $2"; P=$((P+1)); } || { echo "FAIL $2"; F=$((F+1)); }; }
chk "r['calls']==8 and r['errored']==4" counts
chk "r['retry_loops']==[['Bash',3]]" retry-loop
chk "r['files_edited_3plus']==[['b.py',3]]" edits
chk "r['test_runs']==2 and r['test_fail_then_pass']==1" fail-pass
python3 bin/tz rework /nonexistent >/dev/null 2>&1; [ $? -eq 1 ] && { echo "ok missing-log"; P=$((P+1)); } || { echo FAIL missing-log; F=$((F+1)); }
echo "pass $P fail $F"; [ $F = 0 ]
