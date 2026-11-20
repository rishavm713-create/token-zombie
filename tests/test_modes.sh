#!/bin/bash
# Modes: profiles, precedence, advice gating, safe `tz mode` writes. Fake HOME only.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; pass=0; fail=0; mkdir -p "$H/.claude/token-zombie" "$T/proj"
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
C="$H/.claude/token-zombie/config.json"
tz() { HOME="$H" python3 "$Z/bin/tz" "$@"; }
v() { tz mode | sed -n "s/^$1 = \([0-9]*\).*/\1/p"; }
hook() { echo "{\"hook_event_name\":\"$1\",\"session_id\":\"s$3\",\"transcript_path\":\"$T/c.jsonl\",\"cwd\":\"$T/proj\",\"prompt\":\"cut video captions\"$2}" | HOME="$H" TZ_SUP=0 python3 "$Z/bin/tz-guard.py"; }
mkc() { python3 - "$T/c.jsonl" "$1" <<'PY'
import json,sys
open(sys.argv[1],'w').write(json.dumps({"message":{"id":"a","usage":{"input_tokens":30000,"output_tokens":5}}})+'\n'+json.dumps({"message":{"id":"b","usage":{"input_tokens":int(sys.argv[2]),"output_tokens":5}}})+'\n')
PY
}
ok "missing config => full" '[[ $(tz mode | head -1) == "mode = full" && $(v limit) = 100000 ]]'
for m in off lite full ultra; do tz mode $m >/dev/null; ok "set $m" '[[ $(tz mode | head -1) == "mode = $m" ]]'; done
tz mode lite >/dev/null; ok "lite values" '[[ $(v limit) = 150000 && $(v hard) = 175000 && $(v read_warn) = 100000 ]]'
ok "lite advice" 'tz mode | grep -q "advice on:  read_nudge, next_task"'
tz mode ultra >/dev/null; ok "ultra values" '[[ $(v limit) = 60000 && $(v hard) = 120000 && $(v read_warn) = 20000 && $(v plan_warn) = 80 && $(v plan_stop) = 95 ]]'
tz mode off >/dev/null; ok "off thresholds = full" '[[ $(v limit) = 100000 && $(v hard) = 175000 && $(v plan_stop) = 97 ]]'
ok "off: all advice off" 'tz mode | grep -q "advice on:  none"'
# precedence
tz mode ultra >/dev/null; python3 - "$C" <<'PY'
import json,sys;c=json.load(open(sys.argv[1]));c['limit']=70000;json.dump(c,open(sys.argv[1],'w'))
PY
ok "explicit beats profile" '[[ $(v limit) = 70000 && $(v hard) = 120000 ]]'
ok "env beats explicit" '[[ $(TZ_LIMIT=80000 tz mode | sed -n "s/^limit = \([0-9]*\).*/\1/p") = 80000 ]]'
o=$(tz mode full); ok "set prints override note" '[[ $o == *"override the profile"*limit=70000* ]]'
ok "explicit key kept after set" 'grep -q "\"limit\": 70000" "$C"'
# bad input
cp "$C" "$T/before"; tz mode turbo 2>/dev/null; ok "bad mode exit 2" '[ $? = 2 ]'; ok "bad mode: file unchanged" 'cmp -s "$C" "$T/before"'
echo '{"mode":"bogus"}' > "$C"; ok "unknown mode value => full" '[[ $(tz mode | head -1) == "mode = full" ]]'
echo '[1,2]' > "$C"; tz mode lite 2>/dev/null; ok "non-object config refused (exit 1)" '[ $? = 1 ] && [[ $(cat "$C") == "[1,2]" ]]'
echo 'garbage{' > "$C"; tz mode lite 2>/dev/null; ok "corrupt config refused untouched" '[ $? = 1 ] && [[ $(cat "$C") == "garbage{" ]]'
ok "corrupt config: show does not crash" 'tz mode >/dev/null'
# backup + idempotent
rm -f "$C".bak-mode-*; echo '{"mode":"full","x":1}' > "$C"; tz mode lite >/dev/null
ok "backup written with old content" '[ $(ls "$C".bak-mode-* | wc -l) = 1 ] && grep -q "\"mode\":\"full\"" "$C".bak-mode-*'
ok "other keys preserved" 'grep -q "\"x\": 1" "$C"'
b=$(cat "$C"); tz mode lite >/dev/null; ok "idempotent re-set" '[[ $(cat "$C") == "$b" ]]'
ok "no tmp left" '[ ! -e "$C.tmp" ]'
# advice gating via hook. pack hint needs skillpack + parked pack
touch "$H/.claude/skillpack"; mkdir -p "$H/.claude/skills-off/video/x"
big="$T/big.txt"; head -c 60000 /dev/zero | tr '\0' 'a' > "$big"
rm -f "$C"; mkc 40000
ok "full: pack hint" '[[ $(hook UserPromptSubmit "" f) == *skill\ pack* ]]'
ok "full: big read nudged" '[[ $(hook PreToolUse ",\"tool_name\":\"Read\",\"tool_input\":{\"file_path\":\"$big\"}" f) == *deny* ]]'
tz mode off >/dev/null
ok "off: no pack hint" '[[ -z $(hook UserPromptSubmit "" o) ]]'
ok "off: no read nudge" '[[ -z $(hook PreToolUse ",\"tool_name\":\"Read\",\"tool_input\":{\"file_path\":\"$big\"}" o) ]]'
mkc 400000
ok "off: no next-task suggestion" '[[ -z $(hook UserPromptSubmit "" o) ]]'
ok "off: hard-limit warning still fires" '[[ $(hook PostToolUse ",\"tool_name\":\"Bash\"" o) == *"safe point"* ]]'
tz mode ultra >/dev/null
mkc 130000
ok "ultra: next-task suggestion at limit" '[[ $(hook UserPromptSubmit "" u3) == *"NEW task"* ]]'
echo "modes: pass $pass fail $fail"; [ $fail = 0 ]
