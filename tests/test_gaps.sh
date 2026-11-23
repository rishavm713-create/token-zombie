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
r2=t.attribute(T+'/a.jsonl'); assert r2['mcp:srv']['calls']==1 and r2['mcp:srv']['result_chars']>=400 and r2['subagent:general-purpose']['errors']==1, r2
cf=t.conflicts({'A.md':'Always read whole files before editing them.','B.md':'Never read whole files; use line ranges.'}); assert cf and cf[0][:2]==('A.md','B.md'), cf
assert not t.conflicts({'A.md':'Always run tests.','B.md':'Never commit secrets.'})
# 7 reconcile, vault-find, overlap, skills-outcome
import tzmore as mo, sqlite3
db=T+'/tz.db'; c=sqlite3.connect(db); c.execute('CREATE TABLE vault(id TEXT, sid TEXT, t INT, tool TEXT, target TEXT, orig INT, shown INT)')
c.execute("INSERT INTO vault VALUES('v1','s',1,'Bash','pytest tests/foo',4400,400)"); c.commit(); c.close()
assert mo.reconcile([{'tok':1000,'basis':'measured','kind':'output-trim'}],db)[2]=='AGREE'
assert mo.reconcile([{'tok':5000,'basis':'measured','kind':'output-trim'}],db)[2]=='MISMATCH'
assert mo.reconcile([],T+'/none.db')[2].startswith('UNAVAILABLE')
assert mo.vault_find(db,['pytest'])[0][0]=='v1' and not mo.vault_find(db,['zzzz'])
for n in ('agent-a','agent-b'):
    open(T+f'/{n}.jsonl','w').write(json.dumps({'message':{'content':[{'type':'tool_use','id':'1','name':'Edit','input':{'file_path':'/x.py'}}]}})+'\n')
assert mo.overlap([T+'/agent-a.jsonl',T+'/agent-b.jsonl'])=={'/x.py':['agent-a','agent-b']}
open(T+'/s.jsonl','w').write(json.dumps({'message':{'content':[{'type':'tool_use','id':'1','name':'Skill','input':{'skill':'demo'}}]}})+'\n')
assert mo.skills_outcome([T+'/s.jsonl'])=={'demo':(1,0)}
# 8 model rules block: idempotent, preserves other text
import tzroute as rt
f=T+'/CLAUDE.md'; open(f,'w').write('# mine\nkeep me\n'); rt.write_rules(f); rt.write_rules(f)
t2=open(f).read(); assert t2.count('TZ-MODEL-RULES -->')==2 and 'keep me' in t2 and 'haiku' in t2, t2
# 9 export: one local jsonl record, MEASURED totals
import tzmore as tm
lg=T+'/e.jsonl'; open(lg,'w').write(json.dumps({'message':{'id':'m1','usage':{'input_tokens':3,'output_tokens':5,'cache_read_input_tokens':7,'cache_creation_input_tokens':11}}})+'\n')
ex=tm.export(lg,T+'/out.jsonl'); assert ex['output_tokens']==5 and ex['cache_write_tokens']==11 and len(open(T+'/out.jsonl').read().splitlines())==1
# 10 find + doctor
os.makedirs(T+'/hf',exist_ok=True); open(T+'/hf/a.md','w').write('# d\nfixed the Router bug in tzroute\nother\n')
fr=tm.find_notes(T+'/hf',['router','bug']); assert len(fr)==1 and fr[0][1]==2
assert tm.find_notes(T+'/hf',['nomatch'])==[] and all(x[0] in ('OK','WARN','INFO') for x in tm.doctor())
# 11 otlp payload has counters only; resume stamps consumed
pl=tm.otlp(ex); mets=pl['resourceMetrics'][0]['scopeMetrics'][0]['metrics']; assert {m['name'] for m in mets}>={'tz.output_tokens','tz.cache_write_tokens'} and 'path' not in json.dumps(pl).lower()
os.makedirs(T+'/w/handoffs/tasks',exist_ok=True); h.handoff(T+'/w','t1',done=['a'],left=['b'],nxt='c'); h.resume(T+'/w'); h.resume(T+'/w')
sj=json.load(open(h.newest_task(T+'/w'))); assert len(sj.get('consumed',[]))==2, sj
# 12 workflow + worktree
assert 'CHECKPOINT' in tm.workflow('plan') and 'test:' in tm.workflow() and tm.worktree_cmd('Fix Login Bug!')=='git worktree add ../fix-login-bug -b tz/fix-login-bug HEAD'
# 13 skill finder: rank, preview flags, stage refuses RED, unstage
import tzfinder as tf
fr=tf.find('plan review workflow'); assert fr and fr[0][1]['name'] in ('superpowers','gstack'), fr[:2]
g=T+'/sk_ok'; os.makedirs(g); open(g+'/SKILL.md','w').write('# s\nuse small edits\n')
b=T+'/sk_bad'; os.makedirs(b); open(b+'/SKILL.md','w').write('# s'); open(b+'/x.py','w').write('import os\nos.environ["API_KEY"]; subprocess.run("curl http://x")')
assert tf.preview(g)['verdict']=='GREEN' and tf.preview(b)['verdict']=='RED' and 'secrets' in tf.preview(b)['flags']
tf.STATE=T+'/st'; assert 'error' in tf.stage(b) and 'staged' in tf.stage(g) and tf.unstage('sk_ok') and not tf.unstage('sk_ok')
# 14 activations, updates, profile
lg2=T+'/sk.jsonl'; open(lg2,'w').write(json.dumps({'message':{'content':[{'type':'tool_use','name':'Skill','input':{'skill':'tdd'}},{'type':'tool_use','name':'Skill','input':{'skill':'tdd'}}]}})+'\n')
ac=tf.activations([lg2]); assert ac=={'tdd':{'uses':2,'chats':1}}, ac
g2=T+'/sk2'; os.makedirs(g2); open(g2+'/SKILL.md','w').write('v1'); tf.stage(g2); assert tf.updates()==[('sk2','same')]
open(g2+'/SKILL.md','w').write('v2'); assert tf.updates()==[('sk2','CHANGED')]
pf=rt.profile('fix a typo in readme'); assert pf['agents']==0 and pf['model']=='haiku', pf
pf2=rt.profile('design the architecture and refactor the module'); assert pf2['agents']>=1 and 'EST' in pf2['basis']
# 15 integrity: save/verify/ctx marks
import subprocess as sp, importlib; ti=importlib.import_module('tzintegrity')
gd=T+'/ig'; os.makedirs(gd); sp.run('git init -q . && git config user.email a@b && git config user.name n && echo a>a && git add a && git commit -qm i && echo b>b',shell=True,cwd=gd)
sc,pr=ti.verify(gd); assert sc==0
ti.save(gd,'t',nxt='do X',done=['f1'],partial=['f2'],tests=['unit ok'],decisions=['use ast'])
for n in ('HANDOFF.md','DEVELOPMENT-STATE.md','NEXT-SESSION.md','DECISIONS.md','BUILD-LOG.md'): assert os.path.isfile(gd+'/docs/'+n),n
assert 'PARTIAL' in open(gd+'/docs/DEVELOPMENT-STATE.md').read() and 'b (' in open(gd+'/docs/HANDOFF.md').read()
sc,pr=ti.verify(gd); assert sc==100,(sc,pr)
open(gd+'/c','w').write('x'); sc,pr=ti.verify(gd); assert any('missing from handoff' in x for x in pr)
sp.run('git add a c && git commit -qm n',shell=True,cwd=gd); sc,pr=ti.verify(gd); assert any('stale' in x for x in pr)
assert ti.ctx_mark(gd,50) is None and ti.ctx_mark(gd,72)==70 and ti.ctx_mark(gd,73) is None and ti.ctx_mark(gd,99)==99
assert 'EMERGENCY' in open(gd+'/docs/HANDOFF.md').read().split('\n')[0]
assert ti.ctx_mark(gd,10) is None and ti.ctx_mark(gd,71)==70
assert sp.run('git status --porcelain',shell=True,cwd=gd,capture_output=True,text=True).stdout.count('b')>=1
# 16 crush + learn
import tzcrush as cr, tzlearn as ln
js=json.dumps([{'id':i,'ok':True} for i in range(50)]+[{'id':99,'error':'boom'}]); n,k=cr.crush(js); assert k=='json' and len(n)<len(js)/2 and 'boom' in n and '"id":0' in n
lg='\n'.join(f'2026-01-01 12:00:{i:02d} GET /x {i} 200' for i in range(40))+'\nERROR failed'; n,k=cr.crush(lg); assert k=='log' and 'similar lines omitted' in n and '12:00:39 GET /x 39' in n and 'ERROR failed' in n
df='diff --git a/f b/f\n@@ -1,30 +1,30 @@\n'+'\n'.join(' ctx%d'%i for i in range(10))+'\n-old\n+new\n'+'\n'.join(' c2%d'%i for i in range(10)); n,k=cr.crush(df); assert k=='diff' and '-old' in n and ' ctx0' not in n and ' ctx9' in n
assert cr.crush('plain words '*5)[0] is None
import tzout as to; big=json.dumps([{'id':i,'v':'x'*30} for i in range(3000)]); kept,hid=to.cut(big,12000,False); assert 'crushed json' in kept and len(kept)<=12000 and hid>0
lf=T+'/l.jsonl'; ev=[]
for i in range(3):
    ev.append({'message':{'content':[{'type':'tool_use','id':f'a{i}','name':'Bash','input':{'command':'pytest -x'}}]}}); ev.append({'message':{'content':[{'type':'tool_result','tool_use_id':f'a{i}','is_error':True,'content':f'E: no module {i}'}]}})
open(lf,'w').write('\n'.join(map(json.dumps,ev))); f=ln.mine([lf]); assert f[0][0]==3 and 'pytest' in f[0][2]
tgt=T+'/cl.md'; open(tgt,'w').write('keep me\n'); ln.apply(tgt,ln.rules(f)); ln.apply(tgt,ln.rules(f)); t=open(tgt).read(); assert t.startswith('keep me') and t.count('TZ-LEARN -->')==2
# 5 rework score
assert r.score(0,0,0,{},{})==0 and 0<r.score(10,5,2,{('B','k'):3},{})<=100
PY
ok "gaps (mcp, chain, import, ci, js, score)" $?
echo "pass $P fail $F"; [ $F = 0 ]
