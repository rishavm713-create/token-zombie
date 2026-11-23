#!/bin/bash
# Policy engine test (advice only). Isolated temp HOME. Run: bash tests/test_policy.sh
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; pass=0; fail=0
mkdir -p "$H/.claude/skills" && touch "$H/.claude/skillpack"
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
g() { HOME="$H" python3 "$Z/bin/tz-guard.py"; }
ev() { echo "{\"hook_event_name\":\"PreToolUse\",\"session_id\":\"$1\",\"tool_name\":\"$2\",\"tool_input\":$3}"; }
seq 1 2000 > "$T/long.txt"; echo hi > "$T/short.txt"
P="$H/.claude/token-zombie/policy.json"

o=$(ev p1 Read "{\"file_path\":\"$T/long.txt\"}" | g); ok "read_cap_lines" '[[ $o == *read_cap_lines* ]]'
o=$(ev p1 Read "{\"file_path\":\"$T/long.txt\",\"limit\":20}" | g); ok "ranged read no cap" '[[ $o != *read_cap_lines* ]]'
o=$(ev p2 Bash '{"command":"git log"}' | g); ok "bash git log" '[[ $o == *bash_output_cap* ]]'
o=$(ev p2 Bash '{"command":"find / -name x"}' | g); ok "bash find /" '[[ $o == *bash_output_cap* ]]'
o=$(ev p2 Bash '{"command":"git log -n 5"}' | g); ok "bash git log -n ok" '[[ $o != *bash_output_cap* ]]'
o=$(ev p2 Bash '{"command":"git log | head -5"}' | g); ok "bash piped head ok" '[[ $o != *bash_output_cap* ]]'
o=$(ev p3 Read "{\"file_path\":\"$T/short.txt\"}" | g); ok "first read silent" '[ -z "$o" ]'
o=$(ev p3 Read "{\"file_path\":\"$T/short.txt\"}" | g); ok "dup_read" '[[ $o == *dup_read* ]]'
for i in 1 2 3 4 5; do o=$(ev p4 Edit "{\"file_path\":\"$T/a.txt\"}" | g); done
ok "no churn at 5" '[[ $o != *churn* ]]'
o=$(ev p4 Edit "{\"file_path\":\"$T/a.txt\"}" | g); ok "churn at 6" '[[ $o == *churn* ]]'
o=$(ev p5 Bash '{"command":"git push origin main"}' | g); ok "gate push" '[[ $o == *gate* && $o == *approval* ]]'
o=$(ev p5 Bash '{"command":"npm publish"}' | g); ok "gate npm publish" '[[ $o == *gate* ]]'
o=$(ev p5 Bash '{"command":"ls"}' | g); ok "plain ls silent" '[ -z "$o" ]'
# context_pct via check
echo '{"context_pct":86}' > "$T/c.json"
o=$(HOME="$H" python3 "$Z/bin/tzpolicy.py" check "$T/c.json"); ok "context_pct 85 tier" '[[ $o == *context_pct* && $o == *86%* ]]'
echo '{"context_pct":50}' > "$T/c.json"
o=$(HOME="$H" python3 "$Z/bin/tzpolicy.py" check "$T/c.json"); ok "context_pct 50 quiet" '[[ $o == "no advice" ]]'
# init / show
HOME="$H" python3 "$Z/bin/tzpolicy.py" init >/dev/null; ok "init writes" '[ -f "$P" ]'
echo '{"marker":1}' > "$P"; HOME="$H" python3 "$Z/bin/tzpolicy.py" init >/dev/null; ok "init keeps existing" 'grep -q marker "$P"'
# user override: disable gate, change churn threshold
echo '{"rules":{"gate":{"enabled":false},"churn":{"threshold":1}}}' > "$P"
o=$(ev p6 Bash '{"command":"git push"}' | g); ok "override disables gate" '[ -z "$o" ]'
ev p7 Edit "{\"file_path\":\"$T/b.txt\"}" | g >/dev/null
o=$(ev p7 Edit "{\"file_path\":\"$T/b.txt\"}" | g); ok "override churn=1" '[[ $o == *churn* ]]'
o=$(HOME="$H" python3 "$Z/bin/tzpolicy.py" show | python3 -c 'import json,sys;print(json.load(sys.stdin)["rules"]["churn"]["message"][:5])'); ok "merge keeps default message" '[ "$o" = "{path" ]'
# bad JSON
echo '{bad' > "$P"
o=$(ev p8 Bash '{"command":"git push"}' | g); ok "bad JSON -> defaults" '[[ $o == *gate* ]]'
e=$(HOME="$H" python3 "$Z/bin/tzpolicy.py" show 2>&1 >/dev/null); ok "bad JSON warns" '[[ $e == *warning* ]]'
rm -f "$P"
# kill switch
o=$(ev p9 Bash '{"command":"git push"}' | TZ_POLICY=0 g); ok "TZ_POLICY=0 silent" '[ -z "$o" ]'
# never deny/block (policy-only paths)
all=$(for c in "git push" "git log" "find / -x" "npm publish"; do ev p10 Bash "{\"command\":\"$c\"}" | g; done; for i in 1 2 3 4 5 6 7; do ev p10 Edit "{\"file_path\":\"$T/z\"}" | g; done)
ok "advice output present" '[[ $all == *policy* ]]'
ok "no deny/block decision" '[[ $all != *deny* && $all != *permissionDecision* && $all != *'"decision"'* ]]'
echo "pass $pass fail $fail"; rm -rf "$T"; [ $fail -eq 0 ]
