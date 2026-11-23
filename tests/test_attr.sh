#!/bin/bash
# tz attr: per-subagent-type attribution (MEASURED usage vs EST chars/4), main row, totals, --json. Temp dir only, never the real HOME.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; pass=0; fail=0
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
mkdir -p "$T/p/sess1/subagents"
python3 - "$T/p" <<'PY'
import json, sys
d = sys.argv[1]; L = lambda f, rows: open(f, 'w').write(''.join(json.dumps(r) + '\n' for r in rows))
def a(i, model, inp, out, cr=0, cw=0):
    return {'message': {'id': i, 'model': model, 'role': 'assistant', 'content': [{'type': 'text', 'text': 'x'}], 'usage': {'input_tokens': inp, 'output_tokens': out, 'cache_read_input_tokens': cr, 'cache_creation_input_tokens': cw}}}
def tu(i, name, inp): return {'message': {'id': 'm' + i, 'model': 'claude-sonnet', 'content': [{'type': 'tool_use', 'id': i, 'name': name, 'input': inp}], 'usage': {'input_tokens': 100, 'output_tokens': 10}}}
def tr(i, aid, txt): return {'toolUseResult': {'agentId': aid}, 'message': {'content': [{'type': 'tool_result', 'tool_use_id': i, 'content': txt}]}}
L(d + '/sess1.jsonl', [tu('t1', 'Agent', {'subagent_type': 'Explore', 'model': 'haiku'}), tr('t1', 'aaa', 'x' * 400),
   tu('t2', 'Task', {}), tr('t2', 'bbb', 'y' * 40), tu('t3', 'mcp__srv__q', {}), tr('t3', None, 'z' * 80)])
L(d + '/sess1/subagents/agent-aaa.jsonl', [a('s1', 'claude-haiku', 1000, 200, 5000, 300), a('s1', 'claude-haiku', 1000, 200), a('s2', 'claude-haiku', 500, 50)])
L(d + '/sess1/subagents/agent-bbb.jsonl', [a('g1', 'claude-sonnet', 2000, 400)])
PY
J=$(python3 "$Z/bin/tzattr.py" attr "$T/p/sess1.jsonl" --json)
q() { echo "$J" | python3 -c "import json,sys;d=json.load(sys.stdin);print($1)"; }
ok "Explore row input"        '[ "$(q "d[\"rows\"][\"subagent:Explore\"][\"input\"]")" = 1500 ]'
ok "Explore output + cache"   '[ "$(q "d[\"rows\"][\"subagent:Explore\"][\"output\"],d[\"rows\"][\"subagent:Explore\"][\"cache_read\"],d[\"rows\"][\"subagent:Explore\"][\"cache_write\"]")" = "250 5000 300" ]'
ok "Explore model recorded"   '[ "$(q "d[\"rows\"][\"subagent:Explore\"][\"models\"][0]")" = haiku ]'
ok "default type general-purpose" '[ "$(q "d[\"rows\"][\"subagent:general-purpose\"][\"input\"]")" = 2000 ]'
ok "no bare subagent key"     '[ "$(q "\"subagent\" in d[\"rows\"]")" = False ]'
ok "result chars EST (400)"   '[ "$(q "d[\"rows\"][\"subagent:Explore\"][\"result_chars\"]")" -ge 400 ]'
ok "mcp row kept"             '[ "$(q "d[\"rows\"][\"mcp:srv\"][\"calls\"]")" = 1 ]'
ok "main row own usage"       '[ "$(q "d[\"rows\"][\"main\"][\"input\"],d[\"rows\"][\"main\"][\"output\"]")" = "300 30" ]'
ok "total input adds up"      '[ "$(q "d[\"total\"][\"input\"]")" = 3800 ]'
ok "total usd = sum of rows"  '[ "$(q "abs(d[\"total\"][\"usd\"]-sum(v[\"usd\"] for v in d[\"rows\"].values()))<1e-3")" = True ]'
ok "usd positive, haiku<sonnet per tok" '[ "$(q "d[\"rows\"][\"subagent:Explore\"][\"usd\"]>0")" = True ]'
O=$(python3 "$Z/bin/tzattr.py" attr "$T/p/sess1.jsonl")
ok "text: Explore row"        '[[ $O == *subagent:Explore*MEASURED* ]]'
ok "text: main + TOTAL"       '[[ $O == *main* && $O == *TOTAL* ]]'
ok "text: EST label"          '[[ $O == *EST* ]]'
ok "conflicts untouched"      'python3 "$Z/bin/tzattr.py" conflicts "$T/p/sess1.jsonl" | grep -q "possible conflicts"'
echo "pass $pass fail $fail"; rm -rf "$T"; [ $fail = 0 ]
