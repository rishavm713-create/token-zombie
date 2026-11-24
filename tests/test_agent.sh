#!/usr/bin/env bash
# tz agent: phases run in order, debug on failed test, budget stop, file ownership, worktree, tz code --run
cd "$(dirname "$0")/.." || exit 1
R=$PWD; T=$(mktemp -d); export HOME="$T" TZ_DEDUPE=0; P=0; F=0
ok(){ if eval "$1"; then echo "ok $2"; P=$((P+1)); else echo "FAIL $2"; F=$((F+1)); fi; }
cat > "$T/fake" <<'PY'
#!/usr/bin/env python3
import json, os, sys
p = sys.argv[sys.argv.index('-p') + 1]
if 'Phase: build' in p and os.environ.get('FAKE_BUILD') != 'skip': open('out.txt', 'w').write('bad')
if 'Phase: debug' in p: open('out.txt', 'w').write('good')
tok = int(os.environ.get('FAKE_TOK', '100'))
print(json.dumps({'type': 'assistant', 'message': {'id': 'm' + str(len(p)), 'usage': {'input_tokens': tok, 'output_tokens': 1}}}))
print(json.dumps({'type': 'result', 'result': 'done'}))
PY
chmod +x "$T/fake"; export CLAUDE_BIN="$T/fake"
mkdir -p "$T/w"; cd "$T/w" && git init -q && git commit -q --allow-empty -m i
O=$(python3 "$R/bin/tz" agent "make out file" --test 'grep -q good out.txt'); echo "$O" | sed 's/^/   /'
ok "echo \"\$O\" | grep -q 'debug.*ok'" debug-after-failed-test
ok "echo \"\$O\" | tail -2 | head -1 | grep -q 'pass'" test-passes-after-debug
ok "[ \$(sqlite3 $T/.claude/token-zombie/tz.db \"select count(*) from events where kind='agent'\" 2>/dev/null || echo 0) -ge 4 ]" ledger-events
O=$(FAKE_TOK=999999 python3 "$R/bin/tz" agent "big spend" --budget 1000); ok "echo \"\$O\" | grep -q 'build.*budget'" budget-stop
ok "python3 -c \"import sys;sys.path.insert(0,'$R/bin');import tzagent as a;assert a.claim('t1',['x.py'])==[];assert a.claim('t2',['x.py','y.py'])==['x.py'];a.release('t1');assert a.claim('t2',['x.py'])==[]\"" ownership
python3 "$R/bin/tz" agent "wt task" --worktree >/dev/null 2>&1
ok "git worktree list | grep -q 'tz/wt-task'" worktree
python3 "$R/bin/tz" agent "own a" --dry --files z.py >/dev/null; python3 "$R/bin/tz" agent "own b" --dry --files z.py 2>&1 | grep -q refused; ok "[ $? = 0 ]" files-refused
O=$(python3 "$R/bin/tz" code --run "via code" --dry); ok "echo \"\$O\" | grep -q 'plan.*dry'" code-run
echo "pass $P fail $F"; [ $F = 0 ]
