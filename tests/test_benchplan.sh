#!/bin/bash
# tzab plan: free dry run, correct matrix and worst-case bill, no model call.
Z="$(cd "$(dirname "$0")/.." && pwd)"; pass=0; fail=0
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
o=$(python3 "$Z/bin/tzab.py" plan --tasks 2 --trials 5 --cap 1000000 --agg-cap 30000000 --usd-per-mtok 3)
j() { echo "$o" | python3 -c "import json,sys;d=json.load(sys.stdin);print($1)"; }
ok "20 sessions" '[ "$(j "d[\"sessions\"]")" = 20 ]'
ok "worst case = 20M tokens" '[ "$(j "d[\"worst_case_tokens\"]")" = 20000000 ]'
ok "usd est 60" '[ "$(j "d[\"worst_case_usd\"]")" = 60.0 ]'
ok "needs owner ok" '[ "$(j "d[\"needs_owner_ok\"]")" = True ]'
ok "alternating order" '[ "$(j "d[\"order_per_task\"][1]")" = tz ]'
echo "benchplan: pass $pass fail $fail"; [ $fail = 0 ]
