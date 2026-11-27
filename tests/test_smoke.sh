#!/bin/bash
# Paid smoke S1-S4, run OFFLINE with tests/fake/claude.py (no tokens, no network): pass path, every failure path,
# shared aggregate cap, live-config checksum, temp cleanup. TMPDIR is a test dir so leftovers are visible.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; pass=0; fail=0
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
mkdir -p "$T/cfg" "$T/tmp"; echo '{"a":1}' > "$T/live.json"
run() { o=$(TMPDIR="$T/tmp" TZ_PF_LIVE="$T/live.json" FAKE_LIVE="$T/live.json" TZ_AB_CLAUDE="$Z/tests/fake/claude.py" TZ_AB_CONFIG="$T/cfg" \
  FAKE_MODE="$1" TZ_PF_AGG="${2:-}" python3 "$Z/bin/tz" preflight --smoke --yes --evidence "$T/ev-$1$2" 2>&1); r=$?
  S="$T/ev-$1$2/smoke/smoke-summary.json"; }
sm() { python3 -c "import json;d=json.load(open('$S'));print($1)"; }
left() { ls "$T/tmp" | grep -c tzsmoke; }
leftls() { ls -la "$T/tmp" 2>&1 | head -5; }
run good
ok "good: S1 S2 S3 S4 PASS" '[[ $o == *"S1 PASS"* && $o == *"S2 PASS"* && $o == *"S3 PASS"* && $o == *"S4 PASS"* && $o == *"PASS smoke run"* ]]'
ok "good: model echoed a recall id that exists in the store" '[[ $o == *"S2 PASS"*"model echoed recall id True"* ]]'
ok "good: summary ok, live unchanged, temp removed" '[ "$(sm "d[\"ok\"], d[\"live_config_unchanged\"], d[\"temp_removed\"]")" = "True True True" ]'
ok "good: shared tokens counted across scenarios" '[ "$(sm "d[\"tokens\"]")" = 404 ]'
ok "good: no temp dirs left" '[ "$(left)" = 0 ] || { leftls >&2; false; }'
run bash; ok "S2 used Bash: FAIL, stops before S3" '[[ $o == *"S2 FAIL"*"other tools ["*"Bash"* && $o != *"S3 "* && $o == *"NOT READY"* ]]'
run noid; ok "S2 trimmed but model gave no id: FAIL" '[[ $o == *"S2 FAIL"*"echoed recall id False"* ]]'
run leak; ok "S4 model saw the middle code word: FAIL" '[[ $o == *"S4 FAIL"*"forbidden text seen True"* ]]'
run deny; ok "S1 permission denial: FAIL, nothing after" '[[ $o == *"S1 FAIL"*"denials 1"* && $o != *"S2 "* ]]'
run touchlive; ok "live config changed: run not ok" '[ "$(sm "d[\"live_config_unchanged\"], d[\"ok\"]")" = "False False" ] && [[ $o == *"live config unchanged False"* ]]'
echo '{"a":1}' > "$T/live.json"
run crash; ok "S3 process crash: FAIL, temp still removed" '[[ $o == *"S3 FAIL"* ]] && [ "$(left)" = 0 ]'
run good 250; ok "shared cap: S3 refused once 250 tokens are used" '[[ $o == *"S1 PASS"* && $o == *"S2 PASS"* && $o == *"S3 FAIL"* && $o != *"S4 "* ]]'
ok "shared cap: total stays within cap + one reply" '[ "$(sm "d[\"tokens\"] <= 250 + 101")" = True ]'
run good 99999999; ok "TZ_PF_AGG cannot raise the 900k cap" '[ "$(sm "d[\"cap\"]")" = 900000 ]'
run big; ok "300k-token reply: killed at the per-scenario cap, FAIL" '[[ $o == *"S1 FAIL"*"cap-session"* ]]'
ok "every run left no temp dirs" '[ "$(left)" = 0 ]'
# local MCP test server speaks MCP and hides the code word only in the middle
m=$(printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}}' '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"bigtext"}}' | TZ_SMOKE_SALT=s1 python3 "$Z/bin/tzmcpfake.py")
ok "MCP server: initialize, tools/list, tools/call; notification gets no reply" '[ "$(echo "$m" | wc -l | tr -d " ")" = 3 ] && [[ $m == *bigtext* && $m == *MIDDLE-CODEWORD-s1* ]]'
rm -rf "$T"; echo "smoke: pass $pass fail $fail"; [ $fail = 0 ]
