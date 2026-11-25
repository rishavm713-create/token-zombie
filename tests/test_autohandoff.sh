#!/bin/bash
# Auto handoff at the limit: note written (<=30 lines, never over an owner note), bar flag, positive wording, stderr trim, routing line.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/h"; mkdir -p "$H/.claude" "$T/p"; pass=0; fail=0
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
cd "$T/p" && git init -q . && echo a > a.txt
HOME="$H" python3 - "$Z" "$T/p" <<'PY' > "$T/o.txt" 2>&1
import sys, os, json
sys.path.insert(0, sys.argv[1] + '/bin'); cwd = sys.argv[2]
import tzhandoff, tzcont, tzout
p = tzhandoff.auto_note(cwd, 120000)
print('NOTE', os.path.basename(p), len(open(p).read().splitlines()) <= 30)
open(p, 'w').write('owner wrote this\n')
print('KEEP', tzhandoff.auto_note(cwd, 120000) is None)
tzcont.newchat_flag({'session_id': 's'}, 120000)
print('FLAG', json.load(open(os.path.expanduser('~/.claude/token-zombie/newchat.json'))))
tzcont.newchat_flag({'session_id': 's'}, 5000)
print('CLEAR', json.load(open(os.path.expanduser('~/.claude/token-zombie/newchat.json')))['over'])
r, saved = tzout.trim({'tool_name': 'Bash', 'tool_input': {}, 'tool_response': {'stdout': 'x', 'stderr': 'e\n' * 30000}, 'session_id': 's'})
print('STDERR', saved > 0)
PY
ok "note written" "grep -q 'NOTE 20.*True' $T/o.txt"
ok "owner note kept" "grep -q 'KEEP True' $T/o.txt"
ok "flag over" "grep -q \"FLAG.*'over': True\" $T/o.txt"
ok "flag cleared" "grep -q 'CLEAR False' $T/o.txt"
ok "stderr trimmed" "grep -q 'STDERR True' $T/o.txt"
ok "routing line" "grep -q 'cheap subagent' $Z/bin/tz-start.py"
ok "no negative wording" "! grep -qiE 'warn|danger|too big|bloated' <<< \"\$(grep -o 'Best next step[^.]*' $Z/bin/tzcont.py)\""
echo "pass $pass fail $fail"
