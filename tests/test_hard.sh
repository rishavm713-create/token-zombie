#!/bin/bash
# v0.2.1 hardening: hook lifecycle + activity, supervisor recovery, statusline, adapters, dash/companion security, overlay parity, A/B integrity, perf.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; pass=0; fail=0; mkdir -p "$H/.claude" "$T/proj" "$T/bin"
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
tz() { HOME="$H" PATH="$T/bin:$PATH" python3 "$Z/bin/tz" "$@"; }
ST="$H/.claude/token-zombie"; BUS="$ST/status.json"
hook() { echo "{\"hook_event_name\":\"$1\",\"session_id\":\"s1\",\"transcript_path\":\"$T/c.jsonl\",\"cwd\":\"$T/proj\",\"prompt\":\"hi\"$2}" | HOME="$H" python3 "$Z/bin/tz-guard.py"; }
mkc() { python3 - "$T/c.jsonl" "$1" <<'PY'
import json,sys
open(sys.argv[1],'w').write(json.dumps({"message":{"id":"a","usage":{"input_tokens":int(sys.argv[2]),"output_tokens":5}}})+'\n')
PY
}
mkc 30000; (cd "$T/proj"; git init -q; HOME="$H" python3 "$Z/bin/tz" handoff --task h --done a --left b --next c >/dev/null)
# --- activity from hook events (measured), never from mtime
ok "no events => activity UNKNOWN, mascot not CHOMP" '[[ $(tz mascot) != *CHOMP* ]] && python3 -c "import sys;sys.path.insert(0,\"$Z/bin\");import os;os.environ[\"HOME\"]=\"$H\";import tzbus;assert tzbus.activity()[0]==\"UNKNOWN\""'
hook UserPromptSubmit >/dev/null; ok "UserPromptSubmit => working (hook)" '[ "$(python3 -c "import json;print(json.load(open(\"$ST/status.json\"))[\"activity\"])")" = working ]'
ok "status.json says activity source" 'grep -q "\"activity_src\": \"hook\"" "$BUS"'
ok "working => CHOMP" '[[ $(tz mascot) == *CHOMP* ]]'
hook PostToolUse ',"tool_name":"Bash"' >/dev/null; ok "tool event refreshes activity.json only (no tick: tick_ms unchanged file)" 'grep -q PostToolUse "$ST/activity.json"'
hook Stop >/dev/null; ok "Stop => idle => HAPPY" '[[ $(tz mascot) == *HAPPY* ]] && grep -q "\"activity\": \"idle\"" "$BUS"'
python3 - "$ST/activity.json" <<'PY'
import json,sys,time
json.dump({"event":"PostToolUse","ts":int(time.time())-5000,"session":"s1"},open(sys.argv[1],'w'))
PY
ok "stale working (no Stop for 5000s: crash/interrupt) => UNKNOWN, not working" 'python3 -c "import sys;sys.path.insert(0,\"$Z/bin\");import os;os.environ[\"HOME\"]=\"$H\";import tzbus;a=tzbus.activity();assert a[0]==\"UNKNOWN\" and \"stale\" in a[1]"'
# --- TZ_SUP=0 disables everything
rm -rf "$ST/status.json" "$ST/activity.json"; echo "{\"hook_event_name\":\"UserPromptSubmit\",\"transcript_path\":\"$T/c.jsonl\",\"cwd\":\"$T/proj\",\"prompt\":\"x\"}" | TZ_SUP=0 HOME="$H" python3 "$Z/bin/tz-guard.py" >/dev/null
ok "TZ_SUP=0: no status.json, no activity.json" '[ ! -f "$BUS" ] && [ ! -f "$ST/activity.json" ]'
# --- continuation: levels trigger, checkpoint throttled, handoff prep, next-session
mkc 195000; hook UserPromptSubmit >/dev/null; ok "hook at 97% => CRITICAL in bus, checkpoint done" 'grep -q CRITICAL "$BUS" && grep -q "checkpoint" "$BUS"'
n1=$(grep -c checkpoint "$T/proj/handoffs/DAILY.md" 2>/dev/null || echo 0); hook UserPromptSubmit >/dev/null; hook Stop >/dev/null; n2=$(grep -c checkpoint "$T/proj/handoffs/DAILY.md" 2>/dev/null || echo 0)
ok "checkpoint throttled (no DAILY spam within 120 s)" '[ "$n1" = "$n2" ]'
ok "next-session emits quoted command from a REAL adapter" 'o=$(tz sup next-session --cwd "$T/proj"); [[ $o == "cd "*"claude -p"* ]]'
# --- recovery
echo '{"ts": 1, "lev' >"$BUS"; ok "corrupt status.json: tick recovers, evidence kept" 'tz sup tick --transcript "$T/c.jsonl" --cwd "$T/proj" >/dev/null && [ -f "$BUS.corrupt" ] && python3 -c "import json;json.load(open(\"$BUS\"))"'
echo 'not json' >"$ST/tasks.json"; ok "corrupt tasks.json: task cmd recovers" 'tz sup task r1 open --cwd "$T/proj" >/dev/null && [ -f "$ST/tasks.json.corrupt" ] && grep -q r1 "$ST/tasks.json"'
echo '[1]' >"$BUS"; ok "wrong-shaped status.json (list): dash + mascot + statusline survive" 'tz dash --out "$T/x.html" >/dev/null && tz mascot >/dev/null && echo "{}" | HOME="$H" python3 "$Z/bin/tz-status.py" >/dev/null'
ok "hook with garbage stdin does not crash (exit 0)" 'echo garbage | HOME="$H" python3 "$Z/bin/tz-guard.py" >/dev/null 2>&1'
ok "hook with empty stdin exits 0" 'HOME="$H" python3 "$Z/bin/tz-guard.py" </dev/null >/dev/null 2>&1'
ok "no leftover .tmp files in state dir" '[ -z "$(ls "$ST" | grep "\.tmp$")" ]'
# --- statusline
rm -f "$BUS"; o=$(echo "{\"transcript_path\":\"$T/c.jsonl\"}" | HOME="$H" python3 "$Z/bin/tz-status.py"); ok "statusline without bus: works, no emoji crash" '[[ $o == *TZ* ]]'
tz sup tick --transcript "$T/c.jsonl" --cwd "$T/proj" >/dev/null; o=$(echo "{\"transcript_path\":\"$T/c.jsonl\"}" | HOME="$H" python3 "$Z/bin/tz-status.py"); ok "statusline shows ALERT emoji from bus at CRITICAL" '[[ $o == *🚨* ]]'
for st in "SLEEP:{}" ; do :; done
ok "statusline mascot: all 5 states reachable via pure function" 'python3 -c "
import sys;sys.path.insert(0,\"$Z/bin\")
from tzmascot import mascot_state as m, STATES
got={m({}),m({\"ts\":1,\"level\":\"CRITICAL\"}),m({\"ts\":1,\"level\":\"NORMAL\",\"task_just_done\":True}),m({\"ts\":1,\"level\":\"ELEVATED\"}),m({\"ts\":1,\"level\":\"NORMAL\"})}
assert got==set(STATES),got"'
s0=$(python3 -c "import time,subprocess,os;t=time.time();[subprocess.run(['python3','$Z/bin/tz-status.py'],input='{}',text=True,env=dict(os.environ,HOME='$H'),capture_output=True) for _ in range(10)];print(int((time.time()-t)*100))")
ok "statusline < 250 ms per call incl. python start (got ${s0}ms)" '[ $s0 -lt 250 ]'
ok "statusline makes no AI/network calls" '! grep -nE "urllib\.request|import requests|anthropic|socket" "$Z/bin/tz-status.py" "$Z/bin/tzbus.py" "$Z/bin/tzmascot.py" | grep -q .'
# --- adapters
ok "all 8 adapters expose full interface" 'python3 -c "
import sys;sys.path.insert(0,\"$Z/bin\");import adapters as A
for n in A.NAMES:
    i=A.info(n);assert set(A.KEYS)<=set(i[\"capabilities\"]) and i[\"status\"] in (\"REAL\",\"RULES-ONLY\") and i[\"note\"]
assert A.supports(\"claude\",\"hooks\") and not A.supports(\"codex\",\"session_spawn\") and not A.supports(\"cursor\",\"hooks\") and not A.supports(\"antigravity\",\"hooks\")
assert [n for n in A.NAMES if A.info(n)[\"status\"]==\"REAL\"]==[\"claude\"]"'
for n in codex cursor windsurf gemini cline roo antigravity; do tz adapters --rules $n --out "$T/r-$n.md" >/dev/null; done
ok "rules generated for every non-claude adapter" 'for n in codex cursor windsurf gemini cline roo antigravity; do [ -s "$T/r-$n.md" ] || exit 1; done'
ok "claude adapter: usage parser works on a transcript" 'python3 -c "
import sys;sys.path.insert(0,\"$Z/bin\");import tzusage;assert tzusage.totals(\"$T/c.jsonl\")[\"last\"]>0"'
ok "adapters --json valid, installed_here boolean/None" 'tz adapters --json | python3 -c "import json,sys;j=json.load(sys.stdin);assert len(j)==8 and all(x[\"installed_here\"] in (True,False,None) for x in j)"'
# --- dashboard / companion security
P=$((20000+RANDOM%20000)); HOME="$H" python3 "$Z/bin/tz" companion --port $P >/dev/null 2>&1 & CP=$!; sleep 1; TOK=$(cat "$ST/companion.token")
c() { curl -s -o /dev/null -w %{http_code} "$@"; }
ok "bad Host header (DNS rebinding) => 403" '[ "$(c -H "Host: evil.example:$P" "http://127.0.0.1:$P/status.json?token=$TOK")" = 403 ]'
ok "POST/PUT/DELETE => 405 or 401, never 200" 'for m in POST PUT DELETE; do x=$(c -X $m "http://127.0.0.1:$P/status.json?token=$TOK"); [ "$x" != 200 ] || exit 1; done'
ok "header token accepted" '[ "$(c -H "X-TZ-Token: $TOK" "http://127.0.0.1:$P/status.json")" = 200 ]'
ok "status endpoint valid JSON on corrupt/missing bus" 'rm -f "$BUS"; curl -s -H "X-TZ-Token: $TOK" "http://127.0.0.1:$P/status.json" | python3 -c "import json,sys;json.load(sys.stdin)"'
ok "unknown path => 404 (with token)" '[ "$(c "http://127.0.0.1:$P/etc/passwd?token=$TOK")" = 404 ]'
ok "response headers: nosniff + CSP + no-store" 'h=$(curl -si "http://127.0.0.1:$P/?token=$TOK"); [[ $h == *nosniff* && $h == *Content-Security-Policy* && $h == *no-store* ]]'
ok "no listener on non-loopback" '! lsof -nP -iTCP:$P -sTCP:LISTEN | grep -qE "\*:$P|0\.0\.0\.0:$P"'
kill $CP; wait $CP 2>/dev/null; HOME="$H" python3 "$Z/bin/tz" companion --port $P >/dev/null 2>&1 & CP=$!; sleep 1
ok "restart on same port works" '[ "$(c "http://127.0.0.1:$P/?token=$TOK")" = 200 ]'
kill $CP; wait $CP 2>/dev/null
ok "bad --port rejected" '! tz companion --port abc >/dev/null 2>&1 && ! tz companion --port 80 >/dev/null 2>&1'
P=$((P+1)); HOME="$H" python3 "$Z/bin/tz" dash --serve --port $P >/dev/null 2>&1 & DP=$!; sleep 1
ok "dash --serve: no token 401, token 200 HTML, bad host 403" '[ "$(c "http://127.0.0.1:$P/")" = 401 ] && [[ $(curl -s "http://127.0.0.1:$P/?token=$TOK") == *"TOKEN ZOMBIE"* ]] && [ "$(c -H "Host: x:$P" "http://127.0.0.1:$P/?token=$TOK")" = 403 ]'
kill $DP; wait $DP 2>/dev/null
ok "no stray tz servers left running" '! pgrep -f "bin/tz (companion|dash) --(serve )?--?port?" >/dev/null && ! pgrep -f "tz (companion|dash).*--port" >/dev/null'
# --- overlay (native): build with CLT swiftc, selftest parity with python mascot
if [ -x "$Z/overlay/build/TZOverlay" ] || bash "$Z/overlay/build.sh" >/dev/null 2>&1; then
  mkdir -p "$T/ov"; for lv in NORMAL ELEVATED CRITICAL; do
    echo "{\"ts\":1,\"level\":\"$lv\",\"ctx_pct\":5,\"risk\":\"low\"}" >"$T/ov/status.json"
    py=$(python3 -c "import sys;sys.path.insert(0,\"$Z/bin\");from tzmascot import mascot_state;print(mascot_state({\"ts\":1,\"level\":\"$lv\"}))")
    sw=$(TZ_STATE_DIR="$T/ov" "$Z/overlay/build/TZOverlay" --selftest)
    ok "overlay parity $lv ($py)" '[[ $sw == *"$py"* ]]'
  done
  echo '{bad' >"$T/ov/status.json"; ok "overlay survives corrupt status" '[[ $(TZ_STATE_DIR="$T/ov" "$Z/overlay/build/TZOverlay" --selftest) == *SLEEP* ]]'
else echo "overlay: swiftc unavailable, skipped"; fi
# --- A/B integrity: killed runner is counted, hard caps clamp, NOT COMPARABLE
cat >"$T/claude" <<'PY'
#!/usr/bin/env python3
import json,time,sys
for i in range(200):
    print(json.dumps({"type":"assistant","message":{"id":f"m{i}","usage":{"input_tokens":1000,"output_tokens":0,"cache_read_input_tokens":0,"cache_creation_input_tokens":0}}}),flush=True); time.sleep(0.05)
PY
chmod +x "$T/claude"; echo p >"$T/p.txt"; mkdir -p "$T/w"
ab() { TZ_AB_CLAUDE="$T/claude" python3 "$Z/bin/tzab.py" --name "$1" --cwd "$T/w" --config "$T/cfg" --prompt-file "$T/p.txt" --evidence "$T/ev" "${@:2}"; }
ab K1 >/dev/null 2>&1 & KP=$!; sleep 1.5; kill -9 $KP; sleep 0.3; pkill -f "$T/claude" 2>/dev/null
ok "SIGKILLed runner leaves partial count" '[ -s "$T/ev/K1.partial.json" ] && [ ! -f "$T/ev/K1.result.json" ]'
ok "orphan partial counts toward aggregate (no cap bypass)" 'python3 -c "import sys;sys.path.insert(0,\"$Z/bin\");import tzab;assert tzab.agg_used(\"$T/ev\")>=1000"'
o=$(ab K2 --agg-cap 1500 2>&1); ok "second run limited by orphan spend (cap-aggregate or refused)" '[[ $o == *cap-aggregate* || $o == *refused* ]]'
ok "hard session cap clamps an oversized --cap flag" 'python3 -c "
import sys,os,shutil;sys.path.insert(0,\"$Z/bin\");os.environ[\"TZ_AB_CLAUDE\"]=\"$T/claude\"
import tzab;tzab.SESSION_CAP=3000
shutil.rmtree(\"$T/ev2\",ignore_errors=True)
r=tzab.run_session(\"C1\",\"$T/w\",\"$T/cfg\",\"p\",\"$T/ev2\",cap=10**9,agg_cap=10**9)
assert r[\"status\"]==\"cap-session\" and r[\"total\"]<=5000,r"' 
(TZ_AB_WALL_SECONDS=1 ab W1 >/dev/null 2>&1); ok "wall-clock kill: hung/slow child stopped, result written" '[ -f "$T/ev/W1.result.json" ]'
# compare: not comparable without --both-passed; overhead not double counted
python3 - "$T" <<'PY'
import json,sys
for n,t in (('b',100000),('o',60000)):
    open(f"{sys.argv[1]}/{n}.jsonl",'w').write(json.dumps({"message":{"id":"x","usage":{"input_tokens":t,"output_tokens":10}}})+'\n')
PY
o=$(tz bench compare --baseline "$T/b.jsonl" --optimized "$T/o.jsonl"); ok "NOT COMPARABLE without --both-passed, no savings claimed" '[[ $o == *"NOT COMPARABLE"* && $o != *VERDICT* ]]'
o=$(tz bench compare --baseline "$T/b.jsonl" --optimized "$T/o.jsonl" --both-passed --overhead-tok 500); ok "comparable: overhead outside transcripts subtracted once" '[[ $o == *VERDICT* && $o == *"extra overhead outside transcripts 500"* ]]'
# --- perf / resource
s=$(python3 -c "import time,subprocess,os;t=time.time();[subprocess.run(['python3','$Z/bin/tz-guard.py'],input='{\"hook_event_name\":\"PostToolUse\",\"cwd\":\"$T/proj\"}',text=True,env=dict(os.environ,HOME='$H'),capture_output=True) for _ in range(10)];print(int((time.time()-t)*100))")
ok "tool-event hook < 200 ms avg incl. python start (got ${s}ms)" '[ $s -lt 200 ]'
ok "state dir small (< 100 KB)" '[ $(du -sk "$ST" | cut -f1) -lt 100 ]'
ok "activity.json < 300 bytes" '[ $(wc -c <"$ST/activity.json") -lt 300 ]'
echo "hard: pass $pass fail $fail"
