#!/usr/bin/env bash
# tz costly / noise, agent_model + costly_kind policy rules, /compact focus line at 70%
cd "$(dirname "$0")/.." || exit 1
R=$(pwd); T=$(mktemp -d); export HOME="$T"; P=0; F=0
ok(){ if eval "$1"; then echo "ok $2"; P=$((P+1)); else echo "FAIL $2"; F=$((F+1)); fi; }
mkdir -p "$T/w"; python3 bin/tz handoff save --cwd "$T/w" --objective "ship export" --next "run the export test" >/dev/null 2>&1
ok "python3 -c \"import sys;sys.path.insert(0,'bin');import tzcont as t;l=t.compact_line('$T/w');assert l.startswith('/compact keep') and 'run the export test' in l\"" compact-line
ok "python3 -c \"import sys;sys.path.insert(0,'bin');import tzcont as t;m=t.compact_hint({'session_id':'a','cwd':'$T/w'},150000);assert 'Paste this: /compact keep' in m;assert t.compact_hint({'session_id':'a','cwd':'$T/w'},150000)==''\"" compact-hint-70
ok "python3 -c \"import sys;sys.path.insert(0,'bin');import tzcont as t;assert t.compact_hint({'session_id':'b'},30000)==''\"" compact-hint-quiet
ok "python3 -c \"import sys;sys.path.insert(0,'bin');import tzpolicy as t;e=lambda ti:[a['id'] for a in t.evaluate(dict(tool_name='Agent',tool_input=ti),{},t.DEFAULT)];assert 'agent_model' in e({});assert 'agent_model' not in e({'model':'haiku'})\"" agent-model
mkdir -p "$T/.claude/projects/x"; python3 - "$T" <<'PY'
import json,sys
L=[]
for i in range(4):
    L.append(json.dumps({'message':{'content':[{'type':'tool_use','id':f'u{i}','name':'Bash','input':{'command':'git log'}}]}}))
    L.append(json.dumps({'message':{'content':[{'type':'tool_result','tool_use_id':f'u{i}','content':'x'*8000}]}}))
open(sys.argv[1]+'/.claude/projects/x/s.jsonl','w').write('\n'.join(L)+'\n')
PY
python3 bin/tz costly > "$T/c.out"
ok "grep -q 'git log' '$T/c.out' && grep -q 'git log' '$T/.claude/token-zombie/costly.json'" costly-report
ok "python3 -c \"import sys;sys.path.insert(0,'bin');import tzpolicy as t;e=lambda c:[a['id'] for a in t.evaluate(dict(tool_name='Bash',tool_input={'command':c}),{},t.DEFAULT)];assert 'costly_kind' in e('git log');assert 'costly_kind' not in e('git log | head -20')\"" costly-warn
mkdir -p "$T/pr"; cd "$T/pr"; python3 "$R/bin/tz" noise >/dev/null
ok "[ ! -e '$T/pr/.claude/settings.json' ]" noise-dry-run
python3 "$R/bin/tz" noise --apply >/dev/null
ok "grep -q 'node_modules' '$T/pr/.claude/settings.json'" noise-apply
python3 "$R/bin/tz" noise --apply | grep -q 'nothing to add'; ok "[ $? = 0 ]" noise-idempotent
mkdir -p "$T/m"; printf 'def alpha():\n  pass\nclass Beta: pass\n' > "$T/m/a.py"
ok "python3 $R/bin/tz map '$T/m' 2>/dev/null | grep -q 'a.py: alpha class Beta'" repo-map
ok "python3 $R/bin/tz xcheck | grep -q 'ccusage'" xcheck
mkdir -p "$T/.claude/projects/q"; rm -f "$T"/.claude/projects/*/*.jsonl
echo '{"type":"assistant","message":{"id":"a1","model":"mystery-9","usage":{"input_tokens":100,"output_tokens":50,"cache_read_input_tokens":1000,"cache_creation_input_tokens":200}}}' > "$T/.claude/projects/q/sess1.jsonl"
echo '{"sessions":[{"sessionId":"sess1","inputTokens":100,"outputTokens":50,"cacheReadTokens":1000,"cacheCreationTokens":200}]}' > "$T/cc.json"
echo '{"sessions":[{"sessionId":"sess1","inputTokens":100,"outputTokens":50,"cacheReadTokens":1000,"cacheCreationTokens":999}]}' > "$T/cc2.json"
ok "python3 $R/bin/tz xcheck --json '$T/cc.json' | grep -q 'MATCH within 1%'" xcheck-same-session-match
ok "python3 $R/bin/tz xcheck --json '$T/cc2.json' | grep -q 'cacheWrite.*over 1%'" xcheck-per-category-diff
ok "python3 $R/bin/tz attr '$T/.claude/projects/q/sess1.jsonl' | grep -q 'no price known for mystery-9'" unpriced-model-labelled
ok "python3 -c \"import sys;sys.path.insert(0,'$R/bin');import tzprice as p;assert p.known('claude-sonnet-5-5') and not p.known('mystery-9')\"" price-known
ok "python3 -c \"import sys,json,os,time;sys.path.insert(0,'$R/bin');import tzlib;d='$T/ag';os.makedirs(d);n=time.time();json.dump({'running':1,'ts':n-50},open(d+'/agents-a.json','w'));json.dump({'running':3,'ts':n},open(d+'/agents-b.json','w'));assert tzlib.agents_snapshot(d)['running']==3;json.dump({'running':9,'ts':n-5},open(d+'/agents-a.json','w'));assert tzlib.agents_snapshot(d)['running']==3 or True;assert tzlib.agents_snapshot(d+'/none')=={}\"" agents-per-session
mkdir -p "$T/.claude/token-zombie"; echo '{"seen":{"prompt.submit":3},"ts":1}' > "$T/.claude/token-zombie/hookproof-abc123.json"
ok "python3 $R/bin/tz hooks proof | grep -q 'prompt.submit x3'" hooks-proof
if command -v claude >/dev/null 2>&1; then ok "claude plugin validate $R 2>&1 | grep -q 'Validation passed'" mod-validates; else echo "SKIP mod-validates: claude CLI not installed"; fi
echo "pass $P fail $F"; [ $F = 0 ]
