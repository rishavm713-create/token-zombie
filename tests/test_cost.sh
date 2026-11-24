#!/usr/bin/env bash
# tz costly / noise, agent_model + costly_kind policy rules, /compact focus line at 70%
cd "$(dirname "$0")/.." || exit 1
R=$PWD; T=$(mktemp -d); export HOME="$T"; P=0; F=0
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
echo "pass $P fail $F"; [ $F = 0 ]
