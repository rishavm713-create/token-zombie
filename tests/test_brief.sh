#!/bin/bash
# tz brief: start brief + done record written (<=30 lines), advice only.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; pass=0; fail=0
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
cd "$T" && git init -q . && echo a > a
HOME="$T" python3 "$Z/bin/tzbrief.py" start --task demo >/dev/null
HOME="$T" python3 "$Z/bin/tzbrief.py" done --summary built >/dev/null
ok "start brief" "grep -q 'Start brief' handoffs/*-start.md"
ok "done record" "grep -q 'Result: built' handoffs/*-done.md"
ok "small" "[ \$(cat handoffs/*-start.md handoffs/*-done.md | wc -l) -le 30 ]"
ok "advice only" "grep -q 'advice only' handoffs/*-done.md"
echo "pass $pass fail $fail"; [ $fail = 0 ]
