#!/bin/bash
# tzprice tests: family map, cost math, override file, bad JSON. Throwaway HOME.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; pass=0; fail=0; mkdir -p "$H/.claude/token-zombie"
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
p_() { HOME="$H" python3 -c "import sys; sys.path.insert(0,'$Z/bin'); import tzprice as t; $1"; }
ok "family opus" '[ "$(p_ "print(t.family(\"claude-opus-4-1\"))")" = opus ]'
ok "family haiku" '[ "$(p_ "print(t.family(\"claude-haiku-4-5\"))")" = haiku ]'
ok "family fable" '[ "$(p_ "print(t.family(\"claude-fable-1\"))")" = fable ]'
ok "unknown -> sonnet" '[ "$(p_ "print(t.family(\"gpt-x\"), t.family(None))")" = "sonnet sonnet" ]'
ok "price sonnet" '[ "$(p_ "print(t.price(\"sonnet\"))")" = "(3.0, 15.0)" ]'
ok "cost plain" '[ "$(p_ "print(round(t.cost_usd(\"sonnet\",1000000,1000000),4))")" = 18.0 ]'
ok "cost cache read/5m/1h" '[ "$(p_ "print(round(t.cost_usd(\"sonnet\",0,0,1000000,1000000,1000000),4))")" = 10.05 ]'
ok "tz price table" 'HOME="$H" python3 "$Z/bin/tzprice.py" | grep -q "as_of 2026-11-23"'
ok "tz price json" 'HOME="$H" python3 "$Z/bin/tzprice.py" haiku --json | python3 -c "import json,sys; d=json.load(sys.stdin); assert d[\"prices\"]=={\"haiku\":[1.0,5.0]}"'
echo '{"prices":{"sonnet":[2,10],"newm":[7,9]},"cache":{"read":0.2}}' > "$H/.claude/token-zombie/prices.json"
ok "override merges" '[ "$(p_ "print(t.price(\"sonnet\"), t.price(\"x-newm\"), t.price(\"opus\"), t.CACHE[\"read\"])")" = "(2.0, 10.0) (7.0, 9.0) (5.0, 25.0) 0.2" ]'
ok "override path shown" 'HOME="$H" python3 "$Z/bin/tzprice.py" | grep -q "$H/.claude/token-zombie/prices.json (found)"'
echo '{bad json' > "$H/.claude/token-zombie/prices.json"
ok "bad JSON ignored" '[ "$(p_ "print(t.price(\"sonnet\"), t.CACHE[\"read\"])")" = "(3.0, 15.0) 0.1" ]'
echo "pass $pass fail $fail"; rm -rf "$T"; [ $fail = 0 ]
