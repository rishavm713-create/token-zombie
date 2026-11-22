#!/bin/bash
# v0.1 usage-intelligence tests (context math, token sums, 5h/7d, forecast, warn states). Fake HOME.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; pass=0; fail=0; mkdir -p "$H/.claude"
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
u() { HOME="$H" python3 "$Z/bin/tzusage.py" "$@"; }
python3 - "$T/c.jsonl" <<'PY'
import json,sys,datetime as d
t0=d.datetime(2026,11,20,10,0,0,tzinfo=d.timezone.utc); L=[]
for i,(inp,out,cr) in enumerate([(100,50,20000),(100,60,40000),(100,70,60000)]):
    L.append(json.dumps({"timestamp":(t0+d.timedelta(minutes=i*2)).isoformat(),"message":{"id":f"m{i}","usage":{"input_tokens":inp,"output_tokens":out,"cache_read_input_tokens":cr,"cache_creation_input_tokens":0}}}))
L.append(L[-1])  # duplicate line of same reply
open(sys.argv[1],'w').write('\n'.join(L)+'\n')
PY
o=$(u status --transcript "$T/c.jsonl" --cwd "$T"); r=$?
ok "token sums actual + dedupe (in 300, out 180, cr 120000, 3 replies)" '[[ $o == *"input 300 output 180 cache_read 120000"* && $o == *"3 replies"* ]]'
ok "context % math (60100 of 200k = 30%)" '[[ $o == *"60k tokens = 30%"* && $o == *"[est: window"* ]]'
ok "burn forecast labelled est (~10000/min, ~13 min)" '[[ $o == *"burn [est] ~10000"* && $o == *"~13 min"* ]]'
ok "no rate_limits => stated, no invented 5h %" '[[ $o == *"not provided"* && $o != *"5h ["* ]]'
ok "ok state exit 0" '[ $r = 0 ] && [[ $o == *"state: OK"* ]]'
RL=$(python3 -c "import time,json;print(json.dumps({'five_hour':{'used_percentage':50,'resets_at':int(time.time())+9000},'seven_day':{'used_percentage':20}}))")
o=$(u status --transcript "$T/c.jsonl" --rate-limits "$RL"); ok "5h actual + reset + est full; 7d without reset" '[[ $o == *"5h [actual] 50% resets"* && $o == *"[est]"* && $o == *"7d [actual] 20%"* ]]'
ok "7d without resets_at has no forecast/reset" '[[ $(echo "$o" | grep "^7d") != *resets* && $(echo "$o" | grep "^7d") != *full* ]]'
o=$(u status --transcript "$T/c.jsonl" --rate-limits '{"five_hour":{"used_percentage":92}}'); r=$?; ok "warn state at 92%" '[[ $o == *"state: WARN"* && $r = 0 ]]'
o=$(u status --transcript "$T/c.jsonl" --rate-limits '{"five_hour":{"used_percentage":98}}'); r=$?; ok "stop state at 98% exit 3" '[[ $o == *"state: STOP"* && $r = 3 ]]'
o=$(TZ_CTX_WINDOW=60000 u status --transcript "$T/c.jsonl"); ok "ctx_window configurable (env)" '[[ $o == *"= 100%"* && $o == *"STOP"* ]]'
o=$(u forecast --transcript "$T/c.jsonl"); ok "forecast shows burn + state only" '[[ $o == burn* && $o != *tokens\ \[actual* ]]'
o=$(u status --transcript "$T/none.jsonl"); ok "missing log handled" '[[ $o == *"no token usage"* ]]'
o=$(u status --rate-limits '{bad' 2>&1); ok "bad rate-limits JSON => error" '[[ $o == *"not valid JSON"* ]]'
echo '{"message":{"usage":{"input_tokens":5}}} garbage' > "$T/g.jsonl"; o=$(u status --transcript "$T/g.jsonl"); ok "corrupt log line skipped" '[[ $o == *"no token usage"* ]]'
J=$(mktemp); echo '{"uuid":"a","message":{"id":"m1","usage":{"input_tokens":1,"output_tokens":9,"cache_creation":{"ephemeral_5m_input_tokens":7,"ephemeral_1h_input_tokens":3}},"content":[{"type":"thinking","thinking":"abcdefgh"}]}}' > $J
o=$(HOME="$H" python3 -c "import sys;sys.path.insert(0,'$Z/bin');import tzusage as u;t=u.totals('$J');print(t['w5'],t['w1h'],t['think'])")
ok "cache 5m/1h split + thinking est" '[[ $o == "7 3 2" ]]'
echo "usage: pass $pass fail $fail"; [ $fail = 0 ]
