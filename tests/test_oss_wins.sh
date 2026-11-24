#!/bin/bash
# OSS-derived wins: JSON outlier retention (headroom idea), ANSI/progress strip (rtk idea), unchanged re-read stub (lean-ctx idea). Temp HOME, no model calls.
D=$(cd "$(dirname "$0")/.." && pwd); B=$D/bin; T=$(mktemp -d); export HOME="$T"; trap 'rm -rf "$T"' EXIT; mkdir -p "$HOME/.claude/token-zombie"
pass=0; fail=0; ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
py() { python3 -I -c "import sys; sys.path.insert(0,'$B'); $1"; }
cat > "$T/o.py" <<'P'
import sys; sys.path.insert(0, sys.argv[1])
import tzcrush, json
d = [{"ms": 100 + i % 3, "id": i} for i in range(60)]; d[30]["ms"] = 987654
s = json.dumps(d, indent=1); r, k = tzcrush.crush(s)
print("987654" in r and len(r) < len(s) * 0.5)
P
ok "outlier kept in crushed JSON" '[ "$(python3 -I "$T/o.py" "$B")" = True ]'
ok "ANSI + progress redraws stripped" '[ "$(py "import tzcrush;x=\"\\x1b[31mERR\\x1b[0m\\n\"+\"p 1%\\rp 50%\\rp 100%\\n\"*40;r,k=tzcrush.crush(x);print(\"\\x1b\" not in r and \"p 1%\" not in r and \"p 100%\" in r)")" = True ]'
ok "clean never drops error lines" '[ "$(py "import tzcrush;x=\"\\n\".join([\"ok line %d\"%i for i in range(50)]+[\"FATAL boom\"]+[\"ok line %d\"%i for i in range(50)]);r,k=tzcrush.crush(x);print(\"FATAL boom\" in (r or x))")" = True ]'
big=$(python3 -c "print('\n'.join('line %d body body body' % i for i in range(1,300)))")
rd() { python3 -c "import json,sys;print(json.dumps({'session_id':'s9','tool_name':'Read','tool_input':{'file_path':'/x/a.py'},'tool_response':{'type':'text','file':{'filePath':'/x/a.py','content':sys.argv[1],'numLines':299}}}))" "$1" | python3 "$B/tzout.py" hook; }
o1=$(rd "$big"); ok "first read untouched" '[ -z "$o1" ]'
o2=$(rd "$big"); ok "identical re-read stubbed" '[[ $o2 == *"unchanged since you read it"* ]]'
o3=$(rd "$big changed"); ok "changed file not stubbed" '[ -z "$o3" ]'
ok "stub is same shape" 'echo "$o2" | python3 -c "import json,sys;o=json.load(sys.stdin)[\"hookSpecificOutput\"][\"updatedToolOutput\"];assert set(o[\"file\"])=={\"filePath\",\"content\",\"numLines\"}"'
python3 -c "import sys;sys.path.insert(0,'$B');import tzlive;tzlive.on_event({'session_id':'s9','hook_event_name':'PreCompact'})"
o4=$(rd "$big changed"); ok "after PreCompact: no stub" '[ -z "$o4" ]'
echo "oss_wins: pass $pass fail $fail"; [ $fail = 0 ]
