#!/bin/bash
# Context continuity: STATE.md, expensive-chat detection, waste audit, stats accounting, guard output-trim ledger.
# Fake HOME + temp git repo + synthetic chat log. Offline; no model calls; live ~/.claude untouched.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
export HOME="$T/home"; P="$T/proj"; S="$HOME/.claude/token-zombie"; pass=0; fail=0
mkdir -p "$S" "$P/bin" "$P/handoffs"
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
tz() { python3 "$Z/bin/tz" "$@"; }
# portable (GNU+BSD) time helpers: iso_ago SECONDS, age_file FILE SECONDS, mtime_age FILE
iso_ago() { python3 -c "import sys,time;print(time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(time.time()-int(sys.argv[1]))))" "$1"; }
age_file() { python3 -c "import os,sys,time;t=time.time()-int(sys.argv[2]);os.utime(sys.argv[1],(t,t))" "$1" "$2"; }
mtime_age() { python3 -c "import os,sys,time;print(int(time.time()-os.stat(sys.argv[1]).st_mtime))" "$1"; }
G="git -C $P -c user.email=t@t -c user.name=t"
printf '# Demo\n\nShip the demo app fast.\n' > "$P/README.md"; echo x > "$P/bin/a.py"
$G init -q . && $G add . && $G commit -qm init

# 1 STATE.md: built from the repo, compact, sections only rewritten when facts change
o=$(tz state --cwd "$P"); ok "state written, all sections" '[[ $o == *"updated sections master, current, session"* ]]'
F="$P/handoffs/STATE.md"
ok "state has objective, git, next, resume line" 'grep -q "Objective: Ship the demo app fast." "$F" && grep -q "Git: .*@.*, 0 uncommitted" "$F" && grep -q "Next action:" "$F" && grep -q "tz resume" "$F"'
ok "state <= 60 lines" '[ $(wc -l < "$F") -le 60 ]'
o=$(tz state --cwd "$P"); ok "unchanged facts => no rewrite" '[[ $o == *unchanged* ]]'
echo y >> "$P/bin/a.py"; o=$(tz state --cwd "$P"); ok "edit => only current section updated" '[[ $o == *"updated sections current"* && $o != *master* ]]'
ok "changed file listed" 'grep -q "Files changed: bin/a.py" "$F"'
tz next add A --title first --next "write A" --cwd "$P" >/dev/null; tz next add B --title second --dep A --cwd "$P" >/dev/null
tz state --cwd "$P" >/dev/null
ok "tasks: pending + blocked split" 'grep -q "Pending: A" "$F" && grep -q "Blocked: B" "$F"'
ok "HANDOFF.md / dated notes never created by state" '[ ! -e "$P/HANDOFF.md" ] && [ -z "$(ls "$P"/handoffs/20*.md 2>/dev/null)" ]'

# 2 expensive detection from real usage lines (cache reads weighted 0.1x)
L="$T/chat.jsonl"; python3 - "$L" <<'EOF'
import json, sys
with open(sys.argv[1], 'w') as f:
    for i in range(3):
        f.write(json.dumps({'type': 'assistant', 'uuid': f'u{i}', 'message': {'id': f'm{i}', 'usage': {'input_tokens': 5, 'cache_read_input_tokens': 20000 + i * 1000, 'cache_creation_input_tokens': 100, 'output_tokens': 50}}}) + '\n')
EOF
o=$(tz expensive --cwd "$P" --transcript "$L" --session s1); ok "small chat => not expensive, no checkpoint" '[[ $o == *"not expensive yet"* && $o == *"ctx 22105 [actual]"* ]]'
python3 - "$L" <<'EOF'
import json, sys
with open(sys.argv[1], 'a') as f:
    f.write(json.dumps({'type': 'assistant', 'uuid': 'big', 'message': {'id': 'mb', 'usage': {'input_tokens': 10, 'cache_read_input_tokens': 130000, 'cache_creation_input_tokens': 5000, 'output_tokens': 900}}}) + '\n')
    f.write(json.dumps({'type': 'user', 'message': {'role': 'user', 'content': 'BRIEF ' * 600}}) + '\n')
    f.write(json.dumps({'type': 'user', 'message': {'role': 'user', 'content': [{'type': 'text', 'text': 'BRIEF ' * 600}]}}) + '\n')
EOF
o=$(tz expensive --cwd "$P" --transcript "$L" --session s1)
ok "big context => EXPENSIVE + verified checkpoint" '[[ $o == *"EXPENSIVE: context 135k [actual]"* && $o == *"checkpoint VERIFIED: handoffs/STATE.md"* ]] || { echo "tz expensive said: ${o:0:900}"; false; }'
ok "explicit manual startup step" '[[ $o == *"MANUAL STEP"* && $o == *"Continue from handoffs/STATE.md"* ]]'
ok "cache reads shown, not called waste" '[[ $o == *"cache_read 193000 [actual]"* && $o != *"cache_read waste"* ]]'
o=$(tz expensive --cwd "$P" --transcript "$T/none.jsonl"); ok "no log => unknown, not expensive" '[[ $o == *"[unknown]"* && $o == *"not expensive"* ]]'
o=$(tz expensive --cwd "$T/nope" 2>&1); ok "bad dir => error" '[[ $o == *"not a directory"* ]]'

# hook: fires once per session on UserPromptSubmit, then stays quiet
H='{"hook_event_name":"UserPromptSubmit","session_id":"hk","cwd":"'$P'","transcript_path":"'$L'","prompt":"go"}'
o=$(echo "$H" | TZ_LIMIT=20000 python3 "$Z/bin/tz-guard.py"); ok "guard emits checkpoint + manual step" '[[ $o == *"MANUAL STEP"* && $o == *VERIFIED* ]]'
o=$(echo "$H" | TZ_LIMIT=20000 python3 "$Z/bin/tz-guard.py"); ok "guard fires only once per session" '[[ $o != *"MANUAL STEP"* ]]'

# 3 accounting: measured vs est, unknown counted as events only, net = measured - overhead
echo '[{"t":1,"kind":"output-trim","tok":100,"basis":"measured","s":"a"},{"t":1,"kind":"dup","tok":40,"basis":"est","s":"a"},{"t":1,"kind":"x","tok":999,"basis":"unknown","s":"a"},{"t":1,"kind":"overhead-hook","tok":30,"basis":"measured","s":"a"}]' > "$S/ledger.json"
o=$(tz stats); ok "stats: measured/est/overhead/unknown separate" '[[ $o == *"saved [measured] 100"* && $o == *"saved [est] 40"* && $o == *"overhead [measured] 30"* && $o == *"unknown-size events 1"* ]]'
ok "stats: per-kind breakdown, measured and est apart" '[[ $o == *"by kind: "*"dup [est] 40 tok n=1"*"output-trim [measured] 100 tok n=1"* ]]'
ok "net = verified - overhead" '[[ $o == *"NET measured-only 70"* && $o == *"NET incl. estimates 110"* ]]'

# guard output-trim writes a measured ledger entry
rm -f "$S/ledger.json"; seq 1 20000 | sed 's/^/line /' > "$T/big.txt"
python3 -c "import json,sys;print(json.dumps({'hook_event_name':'PostToolUse','session_id':'tr','cwd':'/x','tool_name':'Grep','tool_input':{'pattern':'P','output_mode':'content'},'tool_response':{'mode':'content','content':open(sys.argv[1]).read()}}))" "$T/big.txt" | python3 "$Z/bin/tz-guard.py" > "$T/g.out"
ok "guard trimmed the output" 'grep -q updatedToolOutput "$T/g.out"'
ok "trim saved -> ledger output-trim measured >0" 'python3 -c "import json,sys;L=json.load(open(sys.argv[1]));e=[x for x in L if x[\"kind\"]==\"output-trim\"];sys.exit(0 if e and e[0][\"basis\"]==\"measured\" and e[0][\"tok\"]>0 else 1)" "$S/ledger.json"'
ok "one ledger entry per trim (no double count)" 'python3 -c "import json,sys;sys.exit(0 if len(json.load(open(sys.argv[1])))==1 else 1)" "$S/ledger.json"'
rm -f "$S/ledger.json"
python3 -c "import json,sys;print(json.dumps({'hook_event_name':'PostToolUse','session_id':'tb','cwd':'/x','tool_name':'Bash','tool_input':{'command':'cat big'},'tool_response':{'stdout':open(sys.argv[1]).read(),'stderr':'','interrupted':False}}))" "$T/big.txt" | python3 "$Z/bin/tz-guard.py" > "$T/b.out"
ok "big Bash stdout trimmed, shape kept" 'python3 -c "import json,sys;o=json.load(open(sys.argv[1]))[\"hookSpecificOutput\"][\"updatedToolOutput\"];sys.exit(0 if len(o[\"stdout\"])<20000 and \"stderr\" in o else 1)" "$T/b.out"'
ok "Bash trim -> measured output-trim ledger entry" 'python3 -c "import json,sys;L=json.load(open(sys.argv[1]));sys.exit(0 if [x for x in L if x[\"kind\"]==\"output-trim\" and x[\"basis\"]==\"measured\" and x[\"tok\"]>0] else 1)" "$S/ledger.json"'
echo x | python3 -c "import json,sys;print(json.dumps({'hook_event_name':'PostToolUse','session_id':'tb','cwd':'/x','tool_name':'Bash','tool_input':{'command':'ls'},'tool_response':{'stdout':'small','stderr':''}}))" | python3 "$Z/bin/tz-guard.py" > "$T/s.out"
ok "small Bash output untouched" '! grep -q updatedToolOutput "$T/s.out"'

# 4 waste audit: duplicated handoff docs, long notes, repeated reads, pasted briefs
D2="$P/handoffs"; LONGL="Decision: keep all facts in the master file and never repeat them in daily notes."
printf '# a\n%s\n' "$LONGL" > "$D2/2026-01-01.md"; printf '# b\n%s\n%s\n' "$LONGL" "$(printf 'z%.0s' $(seq 1 5000))" > "$D2/2026-01-02.md"
echo '{"/p/x.py||":{"mt":1,"h":"a","n":3}}' > "$S/reads-s9.json"
o=$(tz waste-audit --cwd "$P" --transcript "$L")
ok "audit: duplicated handoff lines" '[[ $o == *"1 lines repeated across files"* ]]'
ok "audit: long note flagged" '[[ $o == *"long note 2026-01-02.md"* ]]'
ok "audit: repeated read" '[[ $o == *"repeated unchanged reads [measured]: 1 (x.py x3)"* ]]'
ok "audit: pasted brief repeat" '[[ $o == *"pasted briefs [measured]: 2 user messages"* && $o != *"repeats cost ~0 tok"* ]]'
o=$(tz waste-audit --cwd "$P" --transcript ''); ok "audit: no log => briefs unknown" '[[ $o == *"pasted briefs: unknown"* || $o == *"pasted briefs [measured]"* ]]'
# 5 early churn: one line of checkpoint advice per new signal, never blocks; /compact when a turn closes past the limit
C="$T/c.jsonl"; u() { python3 -c "import json,sys;print(json.dumps({'type':'assistant','uuid':sys.argv[1],'message':{'id':sys.argv[1],'usage':{'input_tokens':5,'cache_read_input_tokens':int(sys.argv[2]),'cache_creation_input_tokens':0,'output_tokens':10}}}))" "$@" >> "$C"; }
u c0 20000
g() { python3 -c "import json,sys;print(json.dumps(dict(hook_event_name=sys.argv[1],session_id=sys.argv[2],cwd=sys.argv[3],transcript_path=sys.argv[4],**json.loads(sys.argv[5]))))" "$1" "$2" "$P" "$C" "$3" | python3 "$Z/bin/tz-guard.py"; }
for i in 1 2 3; do g PostToolUse c1 '{"tool_name":"Edit","tool_input":{"file_path":"/p/a.py","old_string":"x","new_string":"y"}}' >/dev/null; done
o=$(g UserPromptSubmit c1 '{"prompt":"go on"}'); ok "churn: same file 3x => checkpoint advice" '[[ $o == *"churn (a.py edited/read 3x"* && $o == *"tz state"* && $o == *"do not stop mid-task"* && $o != *permissionDecision* ]]'
ok "TZ advice text -> measured overhead ledger entry with source" 'python3 -c "import json,sys;L=json.load(open(sys.argv[1]));sys.exit(0 if [e for e in L if e[\"kind\"]==\"overhead-hook\" and e[\"src\"]==\"advice text UserPromptSubmit\" and e[\"tok\"]>0] else 1)" "$S/ledger.json"'
o=$(g UserPromptSubmit c1 '{"prompt":"go on"}'); ok "churn: same signal said once" '[[ $o != *churn* ]]'
for i in 1 2 3; do g PostToolUse c1 '{"tool_name":"Read","tool_input":{"file_path":"/p/s'$i'.png"}}' >/dev/null; done
o=$(g UserPromptSubmit c1 '{"prompt":"next"}'); ok "churn: 3 images" '[[ $o == *"3 images in chat"* ]]'
for i in 1 2; do g UserPromptSubmit c4 '{"prompt":"Please fix the login button now"}' >/dev/null; done
o=$(g UserPromptSubmit c4 '{"prompt":"please fix the  login button now"}'); ok "churn: repeated instruction 3x" '[[ $o == *"same instruction 3x"* ]]'
o=$(g UserPromptSubmit c5 '{"prompt":"ok"}'); u c1 60000
o=$(g UserPromptSubmit c5 '{"prompt":"ok"}'); ok "churn: fast growth, small edits" '[[ $o == *"+40k tokens since last prompt, edits small"* ]]'
# stay-or-fresh: no fixed size; fires only when this chat's own numbers say a fresh session is cheaper, and the prompt looks new
B='{"tool_name":"Bash","tool_input":{"command":"ls"},"tool_response":{"stdout":"a","stderr":""}}'
g UserPromptSubmit c8 '{"prompt":"fix the login button colour"}' >/dev/null; for i in $(seq 10); do g PostToolUse c8 "$B" >/dev/null; done
o=$(g UserPromptSubmit c8 '{"prompt":"also make the login button rounded"}'); ok "decide: follow-up (shared words) => stay" '[[ $o != *stay-or-fresh* ]]'
o=$(g UserPromptSubmit c8 '{"prompt":"ok"}'); ok "decide: short reply => stay" '[[ $o != *stay-or-fresh* ]]'
o=$(g UserPromptSubmit c8 '{"prompt":"write release notes for version three"}'); ok "decide: unrelated, 40k history x 10 steps => fresh" '[[ $o == *"stay-or-fresh [est]"* && $o == *"steps/task"* && $o == *"startup 20k [measured]"* && $o == *"tz handoff"* && $o == *"STATE.md only"* && $o == *"stay here"* ]]'
g UserPromptSubmit c9 '{"prompt":"fix the login button colour"}' >/dev/null; g PostToolUse c9 "$B" >/dev/null
o=$(g UserPromptSubmit c9 '{"prompt":"write release notes for version three"}'); ok "decide: unrelated but 1 step/task => stay" '[[ $o != *stay-or-fresh* ]]'
o=$(TZ_CACHE_TTL=0 g UserPromptSubmit c9 '{"prompt":"translate homepage into spanish"}'); ok "decide: cache expired while idle => fresh" '[[ $o == *"cache expired"* ]]'
o=$(TZ_FRESH_OVERLAP=1 TZ_CACHE_TTL=0 g UserPromptSubmit c9 '{"prompt":"rename release database tables"}'); ok "decide: overlap threshold configurable" '[[ $o != *stay-or-fresh* ]]'
o=$(python3 -c "import sys;sys.path.insert(0,'$Z/bin');import tzcont as c;print(not c.stay_or_fresh(6000,20000,50,3,0,40), not c.stay_or_fresh(150000,20000,50,3,0,40))")
ok "decide: tiny history or past limit => silent (limit has its own line)" '[[ $o == "True True" ]]'
o=$(TZ_LIMIT=20000 g Stop c6 '{}'); ok "turn closed past limit => /compact advice to user" '[[ $o == *systemMessage* && $o == *"run /compact"* ]]'
o=$(TZ_LIMIT=20000 g Stop c6 '{}'); ok "/compact advice once per 25k step" '[[ $o != *compact* ]]'
o=$(g Stop c7 '{}'); ok "under limit => no /compact advice" '[[ $o != *compact* ]]'

# 6 lean rules: compact stand-in for caveman + ponytail, only when neither plugin is on
st() { echo "{\"cwd\":\"$P\",\"source\":\"${1:-startup}\",\"session_id\":\"ls\"}" | python3 "$Z/bin/tz-start.py"; }
echo '{"enabledPlugins":{"caveman@caveman":true,"ponytail@ponytail":true}}' > "$HOME/.claude/settings.json"
o=$(st); ok "lean rules off while caveman/ponytail enabled" '[[ $o != *"lean rules"* ]]'
echo '{"enabledPlugins":{"caveman@caveman":false,"ponytail@ponytail":false,"x@y":true}}' > "$HOME/.claude/settings.json"
o=$(st); ok "lean rules on when both plugins off, small" '[[ $o == *"TOKEN ZOMBIE core rules"* && $o == *"smallest complete change"* && $o == *"read code before editing"* && $o == *"test real changes"* ]] && [ ${#o} -lt 4500 ]'
o=$(st compact); ok "lean rules kept after compaction" '[[ $o == *"lean rules"* ]]'
cp "$S/config.json" "$T/cfg.bak" 2>/dev/null; echo '{"lean_rules":false}' > "$S/config.json"
o=$(st); ok "lean rules: config off" '[[ $o != *"lean rules"* ]]'
rm -f "$S/config.json" "$HOME/.claude/settings.json"

# 7 rolling 24h window: real usage rows (main vs subagent, deduped by id) + ledger split; history per day
R="$HOME/.claude/projects/p"; mkdir -p "$R/s1/subagents"; now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
u() { echo "{\"timestamp\":\"$1\",\"message\":{\"id\":\"$2\",\"model\":\"$3\",\"usage\":{\"input_tokens\":10,\"cache_read_input_tokens\":90,\"output_tokens\":5}}}"; }
{ u "$now" m1 opus; u "$now" m1 opus; u 2020-01-01T00:00:00Z m0 opus; } > "$R/s1.jsonl"; u "$now" a1 haiku > "$R/s1/subagents/agent-x.jsonl"
echo "[{\"t\":$(date +%s),\"kind\":\"rtk\",\"tok\":50,\"basis\":\"measured\"},{\"t\":1,\"kind\":\"rtk\",\"tok\":7,\"basis\":\"measured\"},{\"t\":$(date +%s),\"kind\":\"overhead-hook\",\"tok\":3,\"basis\":\"measured\"}]" > "$S/ledger.json"
o=$(tz stats); ok "24h: used from logs, dedup, old rows out, main/agent split" '[[ $o == *"LAST 24H"*"210 tok in 2 model calls"* && $o == *"main  opus: 1 calls, 105"* && $o == *"agent haiku: 1 calls, 105"* ]]'
ok "24h: ledger window only, overhead apart" '[[ $o == *"saved [measured] 50 [est] 0 | TZ overhead [measured] 3"* ]]'
# fresh-chat counterfactual: new chat after a big one in the same project, EST label, never in measured
R2="$HOME/.claude/projects/q"; mkdir -p "$R2"; t1=$(iso_ago 1800); t2=$(iso_ago 1200)
c() { echo "{\"timestamp\":\"$1\",\"message\":{\"id\":\"$2\",\"usage\":{\"input_tokens\":0,\"cache_read_input_tokens\":$3,\"output_tokens\":1}}}"; }
c "$t1" o1 100000 > "$R2/old.jsonl"; { c "$t2" n1 20000; c "$now" n2 30000; } > "$R2/new.jsonl"
o=$(tz stats); ok "fresh.json for the panel" 'python3 -c "import json;d=json.load(open(\"$S/fresh.json\"));assert d[\"tok\"]==16000 and d[\"n\"]==1 and \"EST\" in d[\"basis\"]"'
o=$(tz stats); ok "fresh-chat saving: 2 calls x 0.1 x (100k-20k) - startup write 0 = 16k input-eq, EST not measured" '[[ $o == *"fresh-chat saving 24h [EST counterfactual"*"16,000 input-eq tok"* && $o == *"saved [measured] 50 [est] 0"* ]]'
ok "24h: history kept per day" '[[ $o == *"history (per day"*"0k/50"* ]] && [ -s "$S/history.json" ]'

# 8 Session Economics: continue/compact/fresh over 5/10/20 turns from measured usage; econ.json; projected vs actual
cd "$T"; R3="$HOME/.claude/projects/$(echo "$T/econ" | sed 's/[^a-zA-Z0-9]/-/g')"; mkdir -p "$R3" "$T/econ"
ts() { iso_ago $(( $1 * 60 )); }
um() { echo "{\"type\":\"user\",\"timestamp\":\"$1\",\"message\":{\"role\":\"user\",\"content\":\"$2\"}}"; }
ar() { echo "{\"timestamp\":\"$1\",\"message\":{\"id\":\"$2\",\"model\":\"claude-sonnet-5-5\",\"usage\":{\"input_tokens\":100,\"cache_read_input_tokens\":$3,\"cache_creation_input_tokens\":$4,\"output_tokens\":500}}}"; }
{ um "$(ts 50)" "build the thing please"; ar "$(ts 50)" e1 0 19900; ar "$(ts 49)" e1 0 19900; ar "$(ts 48)" e2 19900 40000
  um "$(ts 47)" "now test the thing"; ar "$(ts 46)" e3 59900 40000; ar "$(ts 45)" e4 99900 20000; } > "$R3/old.jsonl"
o=$(python3 -c "import sys;sys.path.insert(0,'$Z/bin');import tzcont as c;m=c.measure('$R3/old.jsonl');print(m['used'],m['base'],m['steps'],int(m['grow']),round(m['hit'],2),m['out'],c._fam(m['model']))")
ok "econ: measured history/startup/steps/growth/hit/out/model (dedup by id)" '[ "$o" = "120000 20000 2.0 33333 0.6 500.0 sonnet" ]'
o=$(python3 -c "
import sys;sys.path.insert(0,'$Z/bin');import tzcont as c
m=dict(used=150000,base=20000,steps=3,grow=2000,hit=0.9,out=400,model='opus');e=c.econ(m)
s=dict(m,used=22000);f=c.econ(s)
print(sorted(e)==[5,10,20], c.best(e,10), c.best(f,10), e[20]['fresh'][1]>e[5]['fresh'][1], e[10]['calls'], c.econ(dict(m,model='haiku'))[10]['fresh'][1]<e[10]['fresh'][1], c.econ(m,gap=999)[5]['continue'][0]>e[5]['continue'][0])")
ok "econ: big history -> fresh, small -> continue; 20>5 turns; haiku cheaper; idle cache re-write" '[ "$o" = "True fresh continue True 30 True True" ]'
o=$(tz stats --transcript "$R3/old.jsonl")
ok "tz stats: SESSION ECONOMICS block, API-eq label, 5/10/20 rows" '[[ $o == *"SESSION ECONOMICS [EST"*"API-equivalent"*"plan quota is separate"* && $o == *"next call ("*"cache):"*"next  5 turns: continue"* && $o == *"next 20 turns:"*"-> fresh"* ]]'
ok "econ.json: panel numbers + one projection, no ledger entry" 'python3 -c "import json;d=json.load(open(\"$S/econ.json\"));n=d[\"now\"];assert n[\"best\"]==\"fresh\" and n[\"fresh\"]<n[\"continue\"] and \"EST\" in n[\"basis\"] and \"$R3/old.jsonl\" in d[\"proj\"]" && ! grep -q econ "$S/ledger.json"'
{ um "$(ts 10)" "fresh task brief"; ar "$(ts 10)" f1 0 22000; ar "$(ts 9)" f2 22000 3000; ar "$(ts 8)" f3 25000 3000; } > "$R3/new.jsonl"
o=$(tz stats --transcript "$R3/new.jsonl")
ok "projected vs actual after a switch to fresh (partial until 10 turns)" '[[ $o == *"projected vs actual (fresh, 3/"*"input-eq [partial]"* ]]'
o=$(cd "$T/econ" && tz route build a parser)
ok "tz route: session line with 10-turn \$ and best choice" '[[ $o == *"session: next 10 turns continue \$"*"compact \$"*"fresh \$"*"[EST API-equivalent"* ]]'
o=$(python3 -c "import sys;sys.path.insert(0,'$Z/bin');import tzcont as c;print(c.stay_or_fresh(90000,20000,50,3,0,40))")
ok "stay-or-fresh names the /compact cost too" '[[ $o == *"/compact ~"*"k;"* ]]'
cd "$Z"

# 9 loop detection, claim board, idle-cache, stalled subagent, pack cleanup (advice only)
py() { python3 -c "import sys,json;sys.path.insert(0,'$Z/bin');import tzcont as c;$1"; }
o=$(py "
d=dict(session_id='L1',tool_name='Bash',tool_input={'command':'ls'})
r=[c.tool_advice(d) for _ in range(4)]
print(r[0]=='',r[1]=='','loop: Bash same input 3x' in r[2],r[3]=='')")
ok "loop: 3rd identical call speaks once" '[ "$o" = "True True True True" ]'
o=$(py "
e=lambda s,f:dict(session_id=s,tool_name='Edit',tool_input={'file_path':f})
a=c.tool_advice(e('aaaaaaaa11','/x/f.py')); b=c.tool_advice(e('bbbbbbbb22','/x/f.py')); b2=c.tool_advice(e('bbbbbbbb22','/x/f.py'))
print(a=='','another chat aaaaaaaa edited f.py' in b,b2=='')
c.release_claims('bbbbbbbb22'); print(c.tool_advice(e('cccccccc33','/x/f.py'))=='')
d=json.load(open('$S/claims.json')); print('/x/f.py' in d and d['/x/f.py']['sid']=='cccccccc33')")
ok "claims: other chat warned once per file; release on end; atomic json" '[ "$o" = "$(printf "True True True\nTrue\nTrue")" ]'
o=$(py "
print(c.idle_advice({},50000,100)=='', c.idle_advice({},10000,9999)=='', c.idle_advice({},50000,9999))")
ok "idle: only past ttl and 20k history, with cost line" '[[ $o == "True True TOKEN ZOMBIE: idle "*"min, the prompt cache likely expired"*"~50k history at 1.25x (~62k input-eq)" ]]'
mkdir -p "$HOME/.claude/projects/pp/SS1/subagents"; A="$HOME/.claude/projects/pp/SS1/subagents/agent-z.jsonl"
echo '{"message":{"stop_reason":"tool_use"}}' > "$A"; age_file "$A" 1200
o=$(py "print(c.stall_advice(dict(session_id='SS1')))"); ok "stall: silent mid-work subagent flagged" '[[ $o == *"subagent may be stalled (agent-z silent"* ]]'
echo '{"message":{"stop_reason":"end_turn"}}' > "$A"; age_file "$A" 1200
o=$(py "print(c.stall_advice(dict(session_id='SS1')))"); ok "stall: finished subagent not flagged" '[ -z "$o" ]'
mkdir -p "$HOME/.claude/skills-off/vidx"; echo x > "$HOME/.claude/skills-off/vidx/a"
o=$(py "
d=dict(session_id='PK1',prompt='hello there build it'); c.churn_prompt(d,1000)
import shutil; shutil.rmtree('$HOME/.claude/skills-off/vidx')
a=c.pack_cleanup(d); b=c.pack_cleanup(d); print(a); print(b=='')")
ok "cleanup: pack turned on this chat listed once" '[ "$o" = "$(printf "TOKEN ZOMBIE: skill packs still on: vidx (~/.claude/skillpack off vidx)\nTrue")" ]'

# 10 Stop refreshes fresh.json (TOKENS SAVED fresh-chat part) when older than 5 min
rm -f "$S/fresh.json"; echo '{"hook_event_name":"Stop","session_id":"fs","cwd":"/x"}' | python3 "$Z/bin/tz-guard.py" >/dev/null
ok "Stop writes fresh.json when missing" '[ -s "$S/fresh.json" ]'
age_file "$S/fresh.json" 86400; echo '{"hook_event_name":"Stop","session_id":"fs","cwd":"/x"}' | python3 "$Z/bin/tz-guard.py" >/dev/null
ok "Stop refreshes a stale fresh.json" '[ $(mtime_age "$S/fresh.json") -lt 60 ]'

# 11 fresh-chat linking by the folder a chat worked in (not where it was opened), within 24 h
R4="$HOME/.claude/projects"; mkdir -p "$R4/-a" "$R4/-b"; t1=$(iso_ago 72000)
w() { echo "{\"cwd\":\"$4\",\"timestamp\":\"$1\",\"message\":{\"id\":\"$2\",\"usage\":{\"input_tokens\":0,\"cache_read_input_tokens\":$3,\"output_tokens\":1}}}"; }
w "$t1" w1 120000 /work/proj > "$R4/-a/old.jsonl"; { w "$now" w2 20000 "$HOME"; w "$now" w3 30000 /work/proj; } > "$R4/-b/new.jsonl"
o=$(python3 -c "import sys;sys.path.insert(0,'$Z/bin');import tzopt;print([x for x in tzopt.fresh_saved() if x[0]=='proj'])")
ok "fresh link: different open folders, same work folder, 20 h gap -> 2 x 0.1 x (120k-20k) = 20k" '[ "$o" = "[('"'"'proj'"'"', 120000, 2, 20000)]" ]'

# 12 file guard BEFORE the write, circuit breaker, replay, skill effectiveness (advice only)
o=$(py "
w=lambda s,f:dict(session_id=s,tool_name='Write',tool_input={'file_path':f})
c.tool_advice(dict(session_id='aaaaaaaa11',tool_name='Edit',tool_input={'file_path':'/x/g.py'}))
g=c.file_guard(w('bbbbbbbb22','/x/g.py')); g2=c.file_guard(w('bbbbbbbb22','/x/g.py'))
print('another live chat aaaaaaaa' in g and 'before this write' in g, g2=='', c.file_guard(w('aaaaaaaa11','/x/g.py'))=='')
d=json.load(open('$S/claims.json'))['/x/g.py']; print(d['pid']>0 and d['exp']>d['t'])
d2=json.load(open('$S/claims.json')); d2['/x/dead.py']={'sid':'zzzzzzzz','t':__import__('time').time(),'pid':99999999,'exp':__import__('time').time()+9}
json.dump(d2,open('$S/claims.json','w')); print(c.file_guard(w('bbbbbbbb22','/x/dead.py'))=='')")
ok "file guard: warns before the write once, own/dead-pid claims silent, claim has pid+exp" '[ "$o" = "$(printf "True True True\nTrue\nTrue")" ]'
python3 -c "import json;p='$S/claims.json';d=json.load(open(p));d['/x/g.py']['pid']=$(cat /proc/$$/winpid 2>/dev/null || echo $$);json.dump(d,open(p,'w'))"
o=$(echo '{"hook_event_name":"PreToolUse","session_id":"gg2","tool_name":"Edit","tool_input":{"file_path":"/x/g.py"}}' | python3 "$Z/bin/tz-guard.py")
ok "guard hook: PreToolUse Edit emits the warning as context, never deny" '[[ $o == *"another live chat aaaaaaaa"* && $o != *deny* ]]'
o=$(py "
f=lambda t,cmd='ls',bad=True:dict(session_id='CB1',tool_name=t,tool_input={'command':cmd},tool_response={'is_error':bad})
r=[c.breaker(f('Bash','make')) for _ in range(4)]
print(r[0]=='',r[1]=='','circuit breaker: Bash command failed 3x' in r[2],r[3]=='')
r=[c.breaker(f('Grep',str(i))) for i in range(3)]; print('Grep failed 3x' in r[2])
c.breaker(f('Read','a')); c.breaker(f('Read','b')); c.breaker(f('Read','c',False)); print(c.breaker(f('Read','d'))=='')
print(c.breaker(dict(session_id='CB2',hook_event_name='PostToolUseFailure',tool_name='X',tool_input={}))=='')")
ok "breaker: 3 same failing command / tool in a row, once, success resets" '[ "$o" = "$(printf "True True True True\nTrue\nTrue\nTrue")" ]'
o=$(echo '{"hook_event_name":"Stop","session_id":"cb3","cwd":"/x"}' | python3 "$Z/bin/tz-guard.py"; echo "rc=$?")
ok "Stop hook never blocks" '[[ $o != *block* && $o == *rc=0 ]]'
RP="$T/rp.jsonl"; a() { echo "{\"type\":\"assistant\",\"timestamp\":\"$now\",\"message\":{\"id\":\"$1\",\"usage\":{\"input_tokens\":10,\"cache_read_input_tokens\":$2,\"cache_creation_input_tokens\":$3,\"output_tokens\":5},\"content\":[{\"type\":\"tool_use\",\"name\":\"$4\",\"input\":{\"command\":\"$5\"}}]}}"; }
{ a m1 1000 0 Bash "ls"; a m2 50000 4000 Bash "ls"; a m3 2000 0 Read "x"; a m4 1000 0 Bash "ls"; } > "$RP"
o=$("$Z/bin/tz" replay "$RP")
ok "replay: 4 replies, costliest first (50k read+4k write = 10+5000+5000), repeats counted, EST basis shown" '[[ $o == *"REPLAY 4 replies"* && $o == *"#2 "*"10.0k"* && $o == *"3x  Bash ls"* && $o == *"input 1x, cache read 0.1x"* ]]'
SR="$T/hh/.claude/projects"; mkdir -p "$SR/p"; sk() { echo "{\"type\":\"assistant\",\"timestamp\":\"$now\",\"message\":{\"id\":\"$1\",\"usage\":{\"input_tokens\":1000,\"output_tokens\":1},\"content\":[{\"type\":\"tool_use\",\"name\":\"Skill\",\"input\":{\"skill\":\"foo\"}}]}}"; }
tr() { echo "{\"type\":\"user\",\"message\":{\"content\":[{\"type\":\"tool_result\",\"content\":\"$1\"}]}}"; }
{ sk a1; a b1 0 0 Bash x; tr "12 passed, 0 failed"; } > "$SR/p/c1.jsonl"; { sk a2; sk a3; tr "3 failed"; } > "$SR/p/c2.jsonl"
o=$(py "
r=c.skill_effect('$SR')['foo']; print(r['uses'],r['chats'],r['pass'],r['tests'],round(r['avg_tok']))")
ok "skill effect: uses 3, chats 2, 1/2 chats end passing, tokens = input-eq after first use" '[ "$o" = "3 2 1 2 1505" ]'
ok "tz skills --effect prints EST label and the skill" '[[ $(python3 "$Z/bin/tzcap.py" skills --effect --home "$T/hh") == *"[EST"*"foo"* ]]'

o=$(py "
r=c.ieq((0,10,100,1000,5,'',400)); print(r)")
ok "ieq: 1 h-TTL cache writes cost 2x (1.25x on all writes + 0.75x extra on the 1 h part), old 6-field tuples unchanged" '[ "$o" = "1570.0" ] && [ "$(py "print(c.ieq((0,10,100,1000,5,\"\")))")" = "1270.0" ]'
echo '{"type":"assistant","timestamp":"2026-11-22T10:00:00Z","message":{"id":"w1","usage":{"input_tokens":0,"cache_creation_input_tokens":1000,"cache_creation":{"ephemeral_5m_input_tokens":600,"ephemeral_1h_input_tokens":400},"output_tokens":1},"content":[]}}' > "$T/w.jsonl"
ok "calls(): reads the 1 h part from usage.cache_creation" '[ "$(py "print(c.calls(\"$T/w.jsonl\")[0][6])")" = 400 ]'

o=$(py "
m=dict(used=100000,out=500,model='claude-sonnet-5',base=0,steps=1,grow=0,hit=.9,t=0,n=3)
print(*c.next_call(m,0)[:2], round(c.next_call(m,0)[2],4), *c.next_call(m,99999)[:2])")
ok "next_call: warm = 0.1x history (10000 in-eq, \$0.0375), cold = 1.25x (125000)" '[ "$o" = "warm 10000 0.0375 cold 125000" ]'

# coding row: edits vs test runs (counts measured; pass/fail read from output text); one Stop advice line, never blocks
g PostToolUse CD1 '{"tool_name":"Edit","tool_input":{"file_path":"/p/a.py","old_string":"x","new_string":"y"}}' >/dev/null
g PostToolUse CD1 '{"tool_name":"Write","tool_input":{"file_path":"/p/NOTES.md","content":"x"}}' >/dev/null
o=$(python3 -c "import sys;sys.path.insert(0,'$Z/bin');import tzcont as c;print(c.code_line('CD1'))")
ok "coding: 1 code edit (md ignored), 0 tests, 1 untested" '[[ $o == *"1 code edits, 0 test runs, last test none, 1 edits untested"* ]]'
o=$(g Stop CD1 '{}'); ok "coding: untested edit => one advice line" '[[ $o == *"1 code edit(s) with no test run since"* && $o != *permissionDecision* ]]'
o=$(g Stop CD1 '{}'); ok "coding: advice said once" '[[ $o != *"no test run since"* ]]'
g PostToolUse CD1 '{"tool_name":"Bash","tool_input":{"command":"bash tests/run_all.sh"},"tool_response":"3 failed, 5 passed"}' >/dev/null
o=$(python3 -c "import sys;sys.path.insert(0,'$Z/bin');import tzcont as c;print(c.code_line('CD1'))")
ok "coding: test run clears untested, reads fail" '[[ $o == *"1 test runs, last test fail, 0 edits untested"* ]]'
g PostToolUse CD1 '{"tool_name":"Bash","tool_input":{"command":"bash tests/run_all.sh"},"tool_response":"TOTAL pass 763 fail 0"}' >/dev/null
o=$(python3 -c "import sys;sys.path.insert(0,'$Z/bin');import tzcont as c;print(c.code_line('CD1'))")
ok "coding: 'fail 0' in output is a pass" '[[ $o == *"last test pass"* ]]'
ok "coding.json published for the panel" 'python3 -c "import json,sys;d=json.load(open(sys.argv[1]));sys.exit(0 if d[\"edits\"]==1 and d[\"runs\"]==2 and d[\"last\"]==\"pass\" else 1)" "$S/coding.json"'
tz systems --json --session CD1 > "$T/sys.json"
ok "systems: 8 systems, coding row, honest UNSUPPORTED" 'python3 -c "import json,sys;s=json.load(open(sys.argv[1]))[\"systems\"];assert len(s)==8;assert \"2 test runs\" in s[\"quality\"][\"happening\"];assert \"agent_id\" in s[\"agents\"][\"status\"]" "$T/sys.json"'

echo "cont: pass $pass fail $fail"; [ $fail = 0 ]
