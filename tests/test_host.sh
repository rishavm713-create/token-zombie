#!/bin/bash
# host.json written by tz-status.py from statusline JSON. Fake HOME only.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; mkdir -p "$H"; pass=0; fail=0
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
S() { HOME="$H" python3 "$Z/bin/tz-status.py"; }
F="$H/.claude/token-zombie/host.json"
o=$(echo '{"session_id":"s1","cost":{"total_cost_usd":1.25,"total_duration_ms":9000,"total_api_duration_ms":4000}}' | S); r=$?
ok "statusline exits 0 with cost" '[ $r = 0 ]'
ok "host.json written" '[ -f "$F" ]'
ok "host.json fields" 'python3 -c "import json,sys;d=json.load(open(sys.argv[1]));assert d[\"session\"]==\"s1\" and d[\"cost_usd\"]==1.25 and d[\"duration_ms\"]==9000 and d[\"api_duration_ms\"]==4000 and d[\"ts\"]>0" "$F"'
ok "no temp files left" '[ $(ls "$H/.claude/token-zombie" | grep -c tmp) = 0 ]'
rm -rf "$H/.claude"
o=$(echo '{"session_id":"s2"}' | S); r=$?
ok "no cost => no file" '[ $r = 0 ] && [ ! -f "$F" ]'
o=$(echo 'not json {{{' | S); r=$?
ok "garbage stdin => exit 0" '[ $r = 0 ]'
ok "garbage stdin => statusline prints" '[ -n "$o" ]'
ok "garbage stdin => no file" '[ ! -f "$F" ]'
o=$(echo '{"cost":{"total_cost_usd":"x"}}' | S); r=$?
ok "bad cost type => exit 0, no file" '[ $r = 0 ] && [ ! -f "$F" ]'
echo "host: pass $pass fail $fail"; [ $fail = 0 ]
