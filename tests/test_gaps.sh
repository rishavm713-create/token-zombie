#!/bin/bash
# gap items: MCP schema cost, handoff chain + jsonl import, CI audit line, JS skeleton, rework score
cd "$(dirname "$0")/.." || exit 1
T=$(mktemp -d); P=0; F=0
ok(){ if [ "$2" = 0 ]; then echo "ok $1"; P=$((P+1)); else echo "FAIL $1"; F=$((F+1)); fi; }
python3 - "$T" <<'PY'
import json,sys,os
sys.path.insert(0,'bin'); T=sys.argv[1]
import tzstartup as s, tzhandoff as h, tzcompress as c, tzrework as r
# 1 MCP: measured from request shape, EST from deferred names
open(T+'/m.jsonl','w').write(json.dumps({'type':'api-request-shape','shape':{'tools':[{'name':'mcp__a__x'},{'name':'mcp__a__y'},{'name':'Bash'}]}})+'\n')
m=s.mcp_cost(T+'/m.jsonl'); assert m['a']['tools']==2 and m['a']['basis']=='MEASURED', m
open(T+'/d.jsonl','w').write(json.dumps({'type':'attachment','attachment':{'type':'deferred_tools_delta','addedNames':['mcp__b__t']}})+'\n')
assert s.mcp_cost(T+'/d.jsonl')['b']['basis']=='EST'
# 2 chain id stable across handoffs; import from log with partial line
os.makedirs(T+'/p'); a=h.handoff(T+'/p','t')[1]; b=h.handoff(T+'/p','t')[1]
assert a['chain']==b['chain'] and (a['seq'],b['seq'])==(1,2), (a,b)
L=[{'message':{'role':'user','content':'do X'}},{'message':{'role':'assistant','content':[{'type':'tool_use','id':'1','name':'Edit','input':{'file_path':'/a.py'}},{'type':'tool_result','tool_use_id':'1','is_error':True,'content':'boom'}]}}]
open(T+'/c.jsonl','w').write('\n'.join(map(json.dumps,L))+'\n{"partial')
f=h.import_jsonl(T+'/c.jsonl'); assert f['asks']==['do X'] and f['files']==['/a.py'] and f['errors']==['boom'], f
# 3 CI line
assert 'FAILING' in s.ci_line([{'conclusion':'failure','name':'ci','headBranch':'main'}]) and 'UNAVAILABLE' in s.ci_line(None)
# 4 JS skeleton: bodies cut, strings with braces safe, fail open on imbalance
sk,ok=c.js_skeleton('function a(x) { const s = "}"; return 1 }\nclass B { m(q): string { return "x" } }\n'); assert ok and sk.count('{ ... }')==2 and 'return' not in sk, sk
assert c.js_skeleton('function a( { oops')[1] is False
# 6 attribution + conflicts
import tzattr as t
L=[{'message':{'content':[{'type':'tool_use','id':'1','name':'mcp__srv__q','input':{}},{'type':'tool_use','id':'2','name':'Task','input':{}}]}},
   {'message':{'content':[{'type':'tool_result','tool_use_id':'1','content':'x'*400},{'type':'tool_result','tool_use_id':'2','content':'y','is_error':True}]}}]
open(T+'/a.jsonl','w').write('\n'.join(map(json.dumps,L)))
r2=t.attribute(T+'/a.jsonl'); assert r2['mcp:srv']['calls']==1 and r2['mcp:srv']['result_chars']>=400 and r2['subagent']['errors']==1, r2
cf=t.conflicts({'A.md':'Always read whole files before editing them.','B.md':'Never read whole files; use line ranges.'}); assert cf and cf[0][:2]==('A.md','B.md'), cf
assert not t.conflicts({'A.md':'Always run tests.','B.md':'Never commit secrets.'})
# 5 rework score
assert r.score(0,0,0,{},{})==0 and 0<r.score(10,5,2,{('B','k'):3},{})<=100
PY
ok "gaps (mcp, chain, import, ci, js, score)" $?
echo "pass $P fail $F"; [ $F = 0 ]
