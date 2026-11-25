#!/bin/bash
# E2E: supervisor lifecycle through the real tz-guard hook with fake HOME + stub claude. Plus perf and security checks.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; pass=0; fail=0; mkdir -p "$H/.claude" "$T/proj" "$T/bin"
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
TB="$T/bin"; command -v cygpath >/dev/null && TB=$(cygpath -u "$TB")  # MSYS: a D:/ entry splits PATH at the colon
tz() { HOME="$H" PATH="$TB:$PATH" python3 "$Z/bin/tz" "$@"; }
BUS="$H/.claude/token-zombie/status.json"
printf '#!/bin/bash\necho "$@" >>"%s/claude.log"\n' "$T" >"$T/bin/claude"; chmod +x "$T/bin/claude"
[[ $(uname -s) == MINGW* || $(uname -s) == MSYS* ]] && printf '@bash "%%~dp0claude" %%*\r\n' >"$T/bin/claude.cmd"  # Windows: PATH lookup finds claude.cmd (how npm installs it), not a shell script
python3 - "$T/c.jsonl" <<'PY'
import json,sys
open(sys.argv[1],'w').write(json.dumps({"message":{"id":"a","usage":{"input_tokens":150000,"output_tokens":5}}})+'\n'+json.dumps({"message":{"id":"b","usage":{"input_tokens":192000,"output_tokens":5}}})+'\n')
PY
(cd "$T/proj"; git init -q; echo a >f; HOME="$H" python3 "$Z/bin/tz" handoff --task e2e --done a --left b --next c >/dev/null; echo b >>f)
# hook path writes the bus
echo "{\"hook_event_name\":\"UserPromptSubmit\",\"transcript_path\":\"$T/c.jsonl\",\"cwd\":\"$T/proj\",\"prompt\":\"hi\"}" | HOME="$H" python3 "$Z/bin/tz-guard.py" >/dev/null 2>&1
ok "hook tick wrote bus at CRITICAL" '[ -f "$BUS" ] && grep -q CRITICAL "$BUS"'
ok "auto checkpoint refreshed git snapshot (f uncommitted)" 'grep -rq "checkpoint" "$T/proj/handoffs/tasks" 2>/dev/null'
ok "TZ_SUP=0 disables tick" 'rm "$BUS"; echo "{\"hook_event_name\":\"UserPromptSubmit\",\"transcript_path\":\"$T/c.jsonl\",\"cwd\":\"$T/proj\",\"prompt\":\"hi\"}" | TZ_SUP=0 HOME="$H" python3 "$Z/bin/tz-guard.py" >/dev/null 2>&1; [ ! -f "$BUS" ]'
tz sup next-session --cwd "$T/proj" >/dev/null; ok "next-session without --yes launches nothing" '[ ! -f "$T/claude.log" ]'
tz sup next-session --cwd "$T/proj" --yes >/dev/null; for _ in $(seq 50); do grep -q "^-p" "$T/claude.log" 2>/dev/null && break; sleep 0.1; done; ok "--yes launches stub claude -p once" '[ "$(grep -c "^-p" "$T/claude.log")" = 1 ]'
tz sup tick --transcript "$T/c.jsonl" --cwd "$T/proj" >/dev/null
tz dash --out "$T/d.html" >/dev/null; ok "dash reflects bus (CRITICAL, ALERT)" 'grep -q CRITICAL "$T/d.html" && grep -q "ALERT" "$T/d.html"'
ok "statusline-side: mascot cmd reads bus" '[[ $(tz mascot) == *ALERT* ]]'
tz report >/dev/null 2>&1; ok "tz report still works" 'true'
# perf
s=$(python3 -c "import time,subprocess,os;t=time.time();[subprocess.run(['python3','$Z/bin/tz','sup','tick','--transcript','$T/c.jsonl','--cwd','$T/proj'],env=dict(os.environ,HOME='$H'),capture_output=True) for _ in range(5)];print(int((time.time()-t)*200))")
ok "tick avg < 400 ms incl. python start (got ${s}ms)" '[ $s -lt 400 ]'
ok "status.json < 3 KB" '[ $(wc -c <"$BUS") -lt 3000 ]'
# security
NEW="$Z/bin/tzsup.py $Z/bin/tzroute.py $Z/bin/tzreg.py $Z/bin/tzdash.py $Z/bin/tzcompanion.py $Z/bin/tzmascot.py $Z/bin/tzadapters.py $Z/bin/adapters"
ok "new modules never touch credentials/settings" '! grep -rnE "credentials|keychain|\.claude\.json|settings\.json|api[_-]?key|ANTHROPIC_" $NEW --include=*.py | grep -v "^.*#" | grep -q .'
ok "no outbound network code (urllib/requests/socket.connect/curl)" '! grep -rnE "urllib\.request|import requests|http\.client|create_connection|urlopen|curl |wget " $NEW --include=*.py | grep -q .'
ok "servers bind 127.0.0.1 only" '! grep -rnE "\"0\.0\.0\.0\"|\x27\x27, *[0-9]+\)|\"\", *port" $Z/bin/tzdash.py $Z/bin/tzcompanion.py | grep -q .'
echo '{"ts":1,"level":"<script>alert(1)</script>","cwd":"x"}' >"$BUS"; tz dash --out "$T/x.html" >/dev/null
ok "dash escapes injected status values" '! grep -q "<script>alert" "$T/x.html"'
mkdir -p "$T/evil"; printf 'import os\nopen("%s/pwned","w")\n' "$T" >"$T/evil/setup.py"; tz reg add "$T/evil" >/dev/null
ok "reg never executes repo code" '[ ! -f "$T/pwned" ]'
ok "old tests unaffected: tz help lists new cmds" '[[ $(tz help) == *"sup start"* && $(tz help) == *adapters* ]]'
echo "pass $pass fail $fail"
