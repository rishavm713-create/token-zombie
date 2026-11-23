#!/bin/bash
# tzlib.dup_hook: a hook registered twice (plugin + settings.json) runs once per identical event.
D="$(cd "$(dirname "$0")/.." && pwd)"; P=0; F=0; T=$(mktemp -d)
ok(){ if [ "$1" = "$2" ]; then P=$((P+1)); else F=$((F+1)); echo "FAIL: $3 (got $1 want $2)"; fi; }
run(){ HOME=$T TZ_DEDUPE=$1 python3 -c "import sys; sys.path.insert(0,'$D/bin'); import tzlib; print(tzlib.dup_hook('g', sys.argv[1]))" "$2"; }
ok "$(run 1 '{"a":1}')" False "first copy runs"
ok "$(run 1 '{"a":1}')" True "second identical copy skipped"
ok "$(run 1 '{"a":2}')" False "different payload runs"
ok "$(run 0 '{"a":2}')" False "TZ_DEDUPE=0 disables"
out=$(echo '{"hook_event_name":"PreToolUse","tool_name":"Grep","tool_use_id":"x1","tool_input":{}}' | HOME=$T TZ_DEDUPE=1 python3 "$D/bin/tz-guard.py"; echo "rc=$?")
out2=$(echo '{"hook_event_name":"PreToolUse","tool_name":"Grep","tool_use_id":"x1","tool_input":{}}' | HOME=$T TZ_DEDUPE=1 python3 "$D/bin/tz-guard.py"; echo "rc=$?")
ok "$out2" "rc=0" "guard second copy exits 0 silently"
rm -rf "$T"; echo "pass $P fail $F"; [ $F = 0 ]
