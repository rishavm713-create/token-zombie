#!/bin/bash
# beads-style blocked_by + ready query in tzsup tasks
cd "$(dirname "$0")/.."; T=$(mktemp -d); export HOME="$T"; P=0; F=0
ok(){ if eval "$2" >/dev/null 2>&1; then P=$((P+1)); else F=$((F+1)); echo "FAIL $1"; fi; }
python3 - "$PWD/bin" > "$T/out" <<'P'
import sys; sys.path.insert(0, sys.argv[1]); import tzsup
tzsup.task_set('a'); tzsup.task_set('b', blocked_by=['a']); tzsup.task_set('c')
r1 = sorted(t['id'] for t in tzsup.ready())
tzsup.task_set('a', status='done')
print(r1, sorted(t['id'] for t in tzsup.ready()))
P
ok "b blocked while a open" 'grep -q "^\[.a., .c.\]" "$T/out"'
ok "b ready after a done" 'grep -q "\[.b., .c.\]$" "$T/out"'
echo "memwin: pass $P fail $F"; [ $F = 0 ]
