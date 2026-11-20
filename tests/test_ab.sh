#!/bin/bash
# A/B runner caps, evidence, isolation. Uses a stub `claude` (no tokens spent, no network, no login).
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; pass=0; fail=0
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
cat > "$T/claude" <<'PY'
#!/usr/bin/env python3
import json,os,sys
n=int(os.environ.get('STUB_REPLIES','3')); per=int(os.environ.get('STUB_TOK','1000'))
open(os.environ['STUB_CFGLOG'],'w').write(os.environ.get('CLAUDE_CONFIG_DIR',''))
open(os.environ['STUB_CFGLOG']+'.env','w').write(' '.join(k for k in os.environ if k.startswith(('ANTHROPIC_','CLAUDE')) and k!='CLAUDE_CONFIG_DIR'))
open(os.environ['STUB_CFGLOG']+'.argv','w').write(' '.join(sys.argv))
print(json.dumps({"type":"system","message":"plain-text notice"}),flush=True)  # real streams carry text messages too
for i in range(n):
    u={"input_tokens":per//4,"output_tokens":per//4,"cache_read_input_tokens":per//4,"cache_creation_input_tokens":per//4}
    print(json.dumps({"type":"assistant","message":{"id":f"m{i}","usage":u}}),flush=True)
PY
chmod +x "$T/claude"; echo "do the task" > "$T/p.txt"; mkdir "$T/w"
r() { STUB_CFGLOG="$T/cfglog" TZ_AB_CLAUDE="$T/claude" python3 "$Z/bin/tzab.py" --name "$1" --cwd "$T/w" --config "$T/cfg" --prompt-file "$T/p.txt" --evidence "$T/ev" "${@:2}"; }
o=$(r A1 --cap 1500000); ok "normal run ok, total = all four kinds (3 replies x 1000)" '[[ $o == *"\"status\": \"ok\""* && $o == *"\"total\": 3000"* ]]'
ok "uses only the given CLAUDE_CONFIG_DIR" '[ "$(cat $T/cfglog)" = "$T/cfg" ]'
ok "raw stream + result preserved" '[ -s "$T/ev/A1.stream.jsonl" ] && [ -s "$T/ev/A1.result.json" ]'
ok "aggregate recorded" 'grep -q "\"total\": 3000" "$T/ev/aggregate.json"'
o=$(STUB_REPLIES=50 r A2 --cap 5000); rc=$?; ok "per-session cap stops it, exit 3" '[ $rc = 3 ] && [[ $o == *cap-session* ]] && [[ $(python3 -c "import json;print(json.load(open(\"$T/ev/A2.result.json\"))[\"total\"])") -le 6000 ]]'
o=$(STUB_REPLIES=50 r A3 --cap 1500000 --agg-cap 9000); ok "aggregate cap stops it (3000+5000 used; limit 9000)" '[[ $o == *cap-aggregate* ]]'
o=$(r A4 --agg-cap 8000 2>&1); rc=$?; ok "aggregate exhausted => refused, no session started" '[[ $o == *refused-aggregate* ]] && [ $rc = 3 ]'
ok "cap messages never continue: aggregate file monotone" '[ "$(python3 -c "import json;print(json.load(open(\"$T/ev/aggregate.json\"))[\"total\"])")" -ge 8000 ]'
o=$(ANTHROPIC_AUTH_TOKEN=leak ANTHROPIC_BASE_URL=http://localhost:3001 CLAUDE_CODE_MESSAGING_TOKEN=leak CLAUDECODE=1 r A5); ok "provider env from parent never reaches the isolated run (401 fix)" '[ -f "$T/cfglog.env" ] && [ ! -s "$T/cfglog.env" ] && [ "$(cat "$T/cfglog")" = "$T/cfg" ]'
ok "headless run can edit and run tests (no unanswerable prompts)" 'grep -q -- "--permission-mode acceptEdits" "$T/cfglog.argv"'
echo "ab: pass $pass fail $fail"; [ $fail = 0 ]
