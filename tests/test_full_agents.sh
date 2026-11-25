#!/usr/bin/env bash
# tz agent / live / coord: assign, duplicate detection, collect results, monitor, complete build, coordination
cd "$(dirname "$0")/.." || exit 1
R=$(pwd); T=$(mktemp -d); export HOME="$T" TZ_DEDUPE=0; P=0; F=0
ok(){ if eval "$1"; then echo "ok $2"; P=$((P+1)); else echo "FAIL $2"; F=$((F+1)); fi; }
tz(){ python3 "$R/bin/tz" "$@"; }
cat > "$T/fake" <<'PY'
#!/usr/bin/env python3
import json, os, sys, time
p = sys.argv[sys.argv.index('-p') + 1]
if os.environ.get('FAKE_SLOW'): time.sleep(float(os.environ['FAKE_SLOW']))
if 'Phase: build' in p: open('app.py', 'w').write('print("bad")\n')
if 'Phase: debug' in p: open('app.py', 'w').write('print("good")\n')
print(json.dumps({'type': 'assistant', 'message': {'id': 'm' + str(len(p)), 'usage': {'input_tokens': 100, 'output_tokens': 1}}}))
print(json.dumps({'type': 'result', 'result': 'done'}))
PY
chmod +x "$T/fake"; export CLAUDE_BIN="$T/fake"
mkdir -p "$T/w" && cd "$T/w" && git init -q && git -c user.email=t@t -c user.name=t commit -q --allow-empty -m i
# 27: plan -> build -> test gate -> debug -> pass, end to end, result is on disk
O=$(tz agent "build tiny app" --test 'python3 app.py | grep -q good'); echo "$O" | sed 's/^/   /'
ok "[ \"\$(python3 app.py)\" = good ]" build-complete-app
ok "echo \"\$O\" | grep -q '^plan' && echo \"\$O\" | grep -q '^test .*pass'" build-phases-plan-test
# 24: collect results of finished agents
C=$(tz agent --collect); echo "$C" | sed 's/^/   /'
ok "echo \"\$C\" | grep -q 'done .*build-tiny-app' && echo \"\$C\" | grep -q 'build .*ok' && echo \"\$C\" | grep -q 'diff:'" collect-results
ok "echo \"\$C\" | grep -q '1 done'" collect-count
# 21: assign work, owned files released after the run so the next agent can take them
tz agent "edit one" --files a.py >/dev/null 2>&1
ok "tz agent 'edit two' --files a.py --dry >/dev/null 2>&1" assign-files-free-after-run
# 22/59/23: a running agent is visible and a duplicate is refused
FAKE_SLOW=6 tz agent "slow job" --files s.py >/dev/null 2>&1 &
BG=$!; for i in 1 2 3 4 5 6 7 8 9 10; do tz agent --list | grep -q '^running' && break; sleep 0.5; done
L=$(tz agent --list); echo "$L" | sed 's/^/   /'
ok "echo \"\$L\" | grep -q '^running .*pid=[0-9]* age=[0-9]*s .*files=s.py task=slow job'" monitor-running-agent
LV=$(tz live agents); ok "echo \"\$LV\" | grep -q 'running .*slow job'" live-shows-agent
E=$(tz agent "Slow  job!" 2>&1); ok "echo \"\$E\" | grep -q 'refused: duplicate work'" duplicate-task-refused
E=$(tz agent "other job" --files s.py 2>&1); ok "echo \"\$E\" | grep -q 'refused: owned'" duplicate-files-refused
ok "tz agent 'Slow job' --allow-dup --dry >/dev/null 2>&1" duplicate-override
wait $BG
ok "tz agent --list | grep -q '^done .*slow job'" finished-agent-state
# 25: coordination
tz coord post "write api" >/dev/null; tz coord post "write ui" --after 1 >/dev/null
E=$(CLAUDE_SESSION_ID=bob tz coord claim 2); ok "echo \"\$E\" | grep -q 'refused: #2 waits for #1'" dependency-blocks-claim
CLAUDE_SESSION_ID=alice tz coord claim 1 >/dev/null
E=$(CLAUDE_SESSION_ID=bob tz coord claim 1); ok "echo \"\$E\" | grep -q 'refused: #1 is claimed by alice'" claim-conflict
tz coord handoff 1 bob "api half done" | grep -q 'handoff from' ; ok "[ \$? = 0 ]" handoff
ok "CLAUDE_SESSION_ID=bob tz coord claim 1 | grep -q 'claimed  *bob'" handoff-claimed-by-target
(sleep 1; tz coord done 1 >/dev/null) &
ok "tz coord wait 1 --timeout 10 | grep -q 'done'" wait-until-done
wait
ok "CLAUDE_SESSION_ID=bob tz coord claim 2 | grep -q 'claimed  *bob'" dependency-released
tz coord post "never done" >/dev/null; tz coord wait 3 --timeout 1 >/dev/null; ok "[ \$? = 4 ]" wait-timeout
echo "pass $P fail $F"; [ $F = 0 ]
