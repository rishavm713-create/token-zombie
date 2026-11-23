#!/bin/bash
# tz bench replay: offline counterfactual on fixture logs (no model call)
cd "$(dirname "$0")/.." || exit 1
P=0; F=0; ok(){ if eval "$2"; then P=$((P+1)); else F=$((F+1)); echo "FAIL: $1"; fi; }
T=$(mktemp -d); mkdir -p "$T/p"
python3 - "$T/p" <<'PY'
import json, sys
d = sys.argv[1]
big = 'x' * 50000
def a(i, tools=()):  # assistant reply with usage
    return {'type': 'assistant', 'message': {'id': f'm{i}', 'model': 'claude-sonnet-5-5', 'usage': {'input_tokens': 1000, 'output_tokens': 100},
            'content': [{'type': 'tool_use', 'id': t, 'name': n, 'input': inp} for t, n, inp in tools]}}
def r(t, text):
    return {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': t, 'content': text}]}}
off = [a(0, [('t1', 'Bash', {'command': 'ls'})]), r('t1', big), a(1, [('t2', 'Grep', {'pattern': 'q'})]), r('t2', 'hit'),
       a(2, [('t3', 'Grep', {'pattern': 'q'})]), r('t3', 'hit'), a(3), a(4)]
on = [{'type': 'attachment', 'attachment': {'type': 'hook_additional_context', 'content': ['TOKEN ZOMBIE core rules ' + 'y' * 400]}},
      a(0, [('t1', 'Read', {'file_path': '/f'})]), r('t1', 'head\n[TOKEN ZOMBIE trimmed: /f (30000 chars) not shown]'), a(1), a(2)]
for name, rows in (('off.jsonl', off), ('on.jsonl', on)):
    open(f'{d}/{name}', 'w').write('\n'.join(json.dumps(x) for x in rows) + '\n')
PY
J=$(python3 bin/tz bench replay --root "$T" --json)
g(){ python3 -c "import json,sys; d=json.loads(sys.argv[1]); print($2)" "$J"; }
ok "one TZ-off and one TZ-on chat" '[ "$(g x "d[\"tz_off\"][\"sessions\"],d[\"tz_on\"][\"sessions\"]")" = "1 1" ]'
ok "50k Bash output would be trimmed" '[ "$(g x "d[\"tz_off\"][\"mechanical\"]>0")" = True ]'
ok "real trim marker counted as MEASURED" '[ "$(g x "d[\"tz_on\"][\"actual\"]>0")" = True ]'
ok "TZ hook text counted as overhead" '[ "$(g x "d[\"tz_on\"][\"overhead\"]>0")" = True ]'
ok "identical Grep repeat counted as advice" '[ "$(g x "d[\"all\"][\"advice\"]>0")" = True ]'
ok "verdict nets overhead" '[ "$(g x "abs(d[\"verdict\"][\"net_saved_ieq\"]-d[\"verdict\"][\"trim_saved_ieq\"]+d[\"verdict\"][\"overhead_ieq\"])<=1")" = True ]'
ok "text report runs" 'python3 bin/tz bench replay --root "$T" | grep -q "NET"'
rm -rf "$T"; echo "test_replay: pass $P fail $F"; [ $F = 0 ]
