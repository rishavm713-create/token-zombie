#!/bin/bash
# bench tests: structure, labels, arithmetic, isolation (never writes real HOME state).
Z="$(cd "$(dirname "$0")/.." && pwd)"; pass=0; fail=0; ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
export HOME="$(mktemp -d)"; mkdir -p "$HOME/.claude/token-zombie"; echo keep > "$HOME/.claude/token-zombie/x"  # fake HOME with a state dir to watch
B0=$(ls ~/.claude/token-zombie 2>/dev/null | md5); j=$("$Z/bin/tz" bench --json); o=$("$Z/bin/tz" bench --chat-tokens 50000)
ok "labels MEASURED/EST/UNKNOWN all present" '[[ $o == *MEASURED* && $o == *EST* && $o == *UNKNOWN* && $o == *NET* ]]'
ok "dup-read: 4 of 5 flagged" 'python3 -c "import json,sys;d=json.loads(sys.argv[1]);assert d[\"dup_read\"][\"flagged\"]==4" "$j"'
ok "filter keeps the error and shrinks >80%" 'python3 -c "import json,sys;d=json.loads(sys.argv[1])[\"filter\"];assert d[\"kept_error\"] and d[\"after\"]<0.2*d[\"before\"]" "$j"'
ok "resume small (<2k tok)" 'python3 -c "import json,sys;assert json.loads(sys.argv[1])[\"resume\"][\"resume_tok\"]<2000" "$j"'
ok "saved arithmetic: chat - resume" 'python3 -c "import json,sys;r=json.loads(sys.argv[1])[\"resume\"];assert r[\"saved_tok\"]==r[\"carried_chat_tok\"]-r[\"resume_tok\"]" "$j"'
ok "chat-tokens param changes result" '[[ $o == *"carrying 50000"* ]]'
ok "hooks fast (<1500 ms each)" 'python3 -c "import json,sys;assert json.loads(sys.argv[1])[\"overhead\"][\"hook_ms_max\"]<1500" "$j"'
ok "net measured-only <= net with estimates" 'python3 -c "import json,sys;n=json.loads(sys.argv[1])[\"net\"];assert n[\"measured_only_tok\"]<=n[\"with_estimates_tok\"]" "$j"'
ok "state dir untouched" '[ "$B0" = "$(ls ~/.claude/token-zombie 2>/dev/null | md5)" ]'
# real A/B compare from two chat logs
mk() { python3 - "$1" "$2" "$3" <<'PY'
import json,sys
inp,out,dup=int(sys.argv[2]),int(sys.argv[3]),0
L=[json.dumps({"message":{"id":"m1","usage":{"input_tokens":inp,"output_tokens":out,"cache_creation_input_tokens":1000,"cache_read_input_tokens":5000}}})]
L.append(json.dumps({"message":{"content":[{"type":"tool_use","id":"t1","name":"Read","input":{"file_path":"/a"}}]}}))
L.append(json.dumps({"message":{"content":[{"type":"tool_result","tool_use_id":"t1","content":"x"}]}}))
open(sys.argv[1],'w').write("\n".join(L)+"\n")
PY
}
TT=$(mktemp -d); mk $TT/b.jsonl 20000 3000; mk $TT/o.jsonl 8000 2000
o=$("$Z/bin/tz" bench compare --baseline $TT/b.jsonl --optimized $TT/o.jsonl --overhead-tok 500 --both-passed)
ok "compare: work net = 24000-(11000+500)=12500 (52%)" '[[ $o == *"net 12500 (52.1%)"* && $o == *POSITIVE* ]]'
o=$("$Z/bin/tz" bench compare --baseline $TT/b.jsonl --optimized $TT/o.jsonl --overhead-tok 500); ok "no quality confirmation => NOT COMPARABLE, no claim" '[[ $o == *"NOT COMPARABLE"* && $o != *VERDICT* ]]'
o=$("$Z/bin/tz" bench compare --baseline $TT/b.jsonl --optimized $TT/o.jsonl --overhead-tok 99999 --both-passed); ok "overhead larger than saving => NOT positive" '[[ $o == *"NOT positive"* ]]'
"$Z/bin/tz" bench compare --baseline $TT/none --optimized $TT/o.jsonl >/dev/null 2>&1; ok "missing log => exit 2" '[ $? = 2 ]'
o=$("$Z/bin/tz" bench compare --baseline $TT/b.jsonl --baseline $TT/b.jsonl --optimized $TT/o.jsonl --overhead-tok 0 --both-passed); ok "multiple trials averaged" '[[ $o == *"baseline 2 / optimized 1"* ]]'
# no double counting: a populated ledger must NOT change net
o=$(HOME=$HX "$Z/bin/tz" bench compare --baseline $TT/b.jsonl --optimized $TT/o.jsonl --both-passed)
ok "ledger overhead NOT subtracted again (net 13000)" '[[ $o == *"net 13000 (54.2%)"* && $o == *"already INSIDE"* ]]'
echo "bench: pass $pass fail $fail"; [ $fail = 0 ]
