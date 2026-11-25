#!/usr/bin/env bash
# visible 'Token Zombie is on' line at session start (default on, off with TZ_FEAT_BANNER=0)
cd "$(dirname "$0")/.." || exit 1
T=$(mktemp -d); export HOME="$T" TZ_FRESH_BG=0; P=0; F=0
ok(){ if eval "$1"; then echo "ok $2"; P=$((P+1)); else echo "FAIL $2"; F=$((F+1)); fi; }
IN='{"hook_event_name":"SessionStart","session_id":"s","cwd":"/tmp","source":"startup"}'
ok "echo '$IN' | python3 bin/tz-start.py | python3 -c \"import json,sys;d=json.load(sys.stdin);sys.exit(0 if 'Token Zombie' in d['systemMessage'] else 1)\"" banner-on
ok "! echo '$IN' | TZ_FEAT_BANNER=0 python3 bin/tz-start.py | grep -q systemMessage" banner-off
echo "pass $P fail $F"; [ $F = 0 ]
