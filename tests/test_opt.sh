#!/bin/bash
# v0.1 optimization tests: dup-read, cache invalidation, log analysis, filter, classify, ledger. Fake HOME.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; pass=0; fail=0; mkdir -p "$H/.claude"
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
o_() { HOME="$H" python3 "$Z/bin/tzopt.py" "$@"; }
hook() { echo "{\"session_id\":\"$1\",\"tool_input\":{\"file_path\":\"$T/f.txt\"$2}}" | o_ hook; }
echo hello > "$T/f.txt"
o=$(hook s1); ok "first read: no advice" '[ -z "$o" ]'
o=$(hook s1); ok "second unchanged read: advice, not deny" '[[ $o == *"already read"* && $o != *deny* ]]'
echo changed >> "$T/f.txt"; o=$(hook s1); ok "file changed: cache invalidated, no advice" '[ -z "$o" ]'
o=$(hook s1); ok "after change re-read flagged again" '[[ $o == *"already read"* ]]'
o=$(hook s2); ok "other session independent" '[ -z "$o" ]'
o=$(hook s3 ',"limit":5'); o=$(hook s3 ',"limit":5'); ok "ranged re-read flagged" '[[ $o == *"already read"* ]]'
echo 'junk' | o_ hook >/dev/null; ok "hook survives bad input" '[ $? = 0 ]'
# log analysis
python3 - "$T/c.jsonl" <<'PY'
import json,sys
L=[];n=0
def use(name,inp,res):
    global n; n+=1; i=f"t{n}"
    L.append(json.dumps({"message":{"content":[{"type":"tool_use","id":i,"name":name,"input":inp}]}}))
    L.append(json.dumps({"message":{"content":[{"type":"tool_result","tool_use_id":i,"content":res}]}}))
use("Read",{"file_path":"/a"},"x"*4000); use("Read",{"file_path":"/a"},"x"*4000)   # dup
use("Edit",{"file_path":"/b"},"ok"); use("Read",{"file_path":"/b"},"y"*100); use("Edit",{"file_path":"/b"},"ok"); use("Read",{"file_path":"/b"},"y"*100)  # not dup
use("Read",{"file_path":"/c"},"z"*50000)   # big full read
use("Bash",{"command":"make build"},"o"*1000); use("Bash",{"command":"make build"},"o"*1000)  # repeated cmd
open(sys.argv[1],'w').write('\n'.join(L)+'\n')
PY
o=$(o_ optimize --transcript "$T/c.jsonl")
ok "dup read found, edit-between not counted" '[[ $o == *"duplicate full reads 1"* && $o == *"/a"* ]]'
ok "repeated command found" '[[ $o == *"repeated commands w/ same output 1"* ]]'
ok "big full read advice (not a block)" '[[ $o == *"big full read: /c"* && $o == *"offset/limit"* ]]'
ok "avoidable labelled est (4000+1000 chars = 1250)" '[[ $o == *"avoidable [est] ~1250"* ]]'
python3 -c "import json;u=json.dumps({'message':{'content':[{'type':'tool_use','id':'x1','name':'Bash','input':{'command':'make all'}}]}});r=json.dumps({'message':{'content':[{'type':'tool_result','tool_use_id':'x1','content':'o'*900}]}});m=json.dumps({'message':{'id':'m1','usage':{'input_tokens':1000,'cache_read_input_tokens':9000}}});open('$T/c2.jsonl','w').write(u+chr(10)+u+chr(10)+r+chr(10)+m+chr(10)+m+chr(10))"
o=$(o_ optimize --transcript "$T/c2.jsonl"); ok "one call logged twice (same tool_use id) is not a repeat" '[[ $o == *"repeated commands w/ same output 0"* ]]'
ok "per-call re-sent context measured once per reply" '[[ $o == *"model calls [actual] 1;"* && $o == *"avg ~10k"* && $o == *"cache_read 47%"* ]]'
o=$(o_ optimize --transcript "$T/none"); ok "missing log handled" '[[ $o == *"no chat log"* || $o == *"reads [actual] 0"* ]]'
# filter
python3 -c "print('ok line\n'*200 + 'ERROR boom\n' + '\n'.join(f'l{i}' for i in range(300)))" > "$T/big.out"
o=$(o_ filter --lines 20 < "$T/big.out" 2>"$T/err"); ok "filter keeps error, caps lines, collapses repeats" '[[ $o == *"ERROR boom"* && $o == *"repeated 199x"* && $(echo "$o" | wc -l) -le 30 ]]'
ok "filter reports measured sizes" 'grep -q "chars measured" "$T/err"'
echo short | o_ filter > "$T/s" 2>/dev/null; ok "small output unchanged" '[ "$(cat $T/s)" = short ]'
# classify
for pair in "audit this repo for vulnerabilities:AUDIT" "research and compare vector dbs:RESEARCH" "fix typo in readme:QUICK" "refactor the parser:ENGINEERING" "hello there:STANDARD"; do
  o=$(o_ classify "${pair%%:*}"); ok "classify ${pair##*:}" '[[ $o == "mode ${pair##*:}"* ]]'; done
# ledger / net
o=$(o_ stats); ok "stats separates measured/est/overhead + net" '[[ $o == *"[measured]"* && $o == *"[est]"* && $o == *"overhead"* && $o == *NET* ]]'
# guard integration: dup small read gets advice (no deny); big full read still nudged once then allowed
g() { HOME="$H" python3 "$Z/bin/tz-guard.py"; }
q="{\"hook_event_name\":\"PreToolUse\",\"session_id\":\"gi\",\"tool_input\":{\"file_path\":\"$T/f.txt\"}}"
o=$(echo "$q" | g); ok "guard: first small read quiet" '[ -z "$o" ]'
o=$(echo "$q" | g); ok "guard: repeat unchanged read => advice, never deny" '[[ $o == *additionalContext* && $o != *deny* ]]'
o=$(o_ stats); ok "hook advice counted as overhead" '[[ $o == *"overhead [measured]"* && $o != *"overhead [measured] 0 tok"* ]]'
echo "opt: pass $pass fail $fail"; [ $fail = 0 ]
