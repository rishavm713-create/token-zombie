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
mkdir -p "$T/h"; python3 - "$PWD/bin" > "$T/o2" <<'P'
import sys, os; sys.path.insert(0, sys.argv[1]); import tzhandoff as h
print(h.tail_lines(b"a\nb\nc\n", 2) == b"b\nc\n", h.tail_lines(b"a\nb", 5) == b"a\nb", h.tail_lines(b"", 3) == b"")
P
ok "tail_lines copied helper" 'grep -q "^True True True" "$T/o2"'
echo "memwin: pass $P fail $F"; [ $F = 0 ]
