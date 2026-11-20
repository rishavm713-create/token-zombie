#!/bin/bash
# v0.1 CLI, config isolation, back-compat and failure-handling tests. Fake HOME.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; pass=0; fail=0; mkdir -p "$H/.claude"
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
tz() { HOME="$H" "$Z/bin/tz" "$@"; }
o=$(tz help); ok "help lists every command" 'for w in status startup optimize stats forecast handoff resume skills capabilities security audit report; do [[ $o == *"  $w"* ]] || exit 1; done'
tz nonsense 2>"$T/e"; r=$?; ok "unknown command => exit 2 + message" '[ $r = 2 ] && grep -q "unknown command" "$T/e"'
tz >/dev/null; ok "no args => help exit 0" '[ $? = 0 ]'
# each command is real
echo '{"message":{"id":"a","usage":{"input_tokens":10,"output_tokens":5}}}' > "$T/c.jsonl"
o=$(tz status --transcript "$T/c.jsonl"); ok "status real" '[[ $o == *"input 10 output 5"* ]]'
o=$(tz forecast --transcript "$T/c.jsonl"); ok "forecast real" '[[ $o == *burn* ]]'
o=$(tz optimize --transcript "$T/c.jsonl"); ok "optimize real" '[[ $o == *"reads [actual]"* ]]'
o=$(tz stats); ok "stats real" '[[ $o == *NET* ]]'
o=$(tz classify audit the repo); ok "classify real" '[[ $o == *"mode AUDIT"* ]]'
o=$(seq 1 300 | tz filter --lines 20 2>/dev/null | wc -l | tr -d ' '); ok "filter real" '[ "$o" -le 30 ]'
o=$(tz capabilities); ok "capabilities real" '[[ $o == skills* ]]'
o=$(tz skills); ok "skills real" '[[ $o == *"loaded at startup"* ]]'
mkdir -p "$T/d"; echo 'print(1)' > "$T/d/a.py"; o=$(tz security "$T/d"); ok "security real" '[[ $o == GREEN* ]]'
o=$(tz audit); ok "audit real (no skills dir ok)" '[[ $o == *audited* ]]'
o=$(tz startup 2>&1); ok "startup real (delegates to tz-status.py --startup)" '[ -n "$o" ]'
mkdir -p "$T/p"; o=$(tz handoff --cwd "$T/p" --task t --next go); ok "handoff via tz" '[[ $o == *"NEXT ACTION: go"* ]]'
o=$(tz resume --cwd "$T/p"); ok "resume via tz" '[[ $o == *"NEXT ACTION: go"* ]]'
o=$(tz report --transcript "$T/c.jsonl"); ok "report combines sections" '[[ $o == *"== STATUS"* && $o == *"== SAVINGS"* && $o == *"== CAPABILITIES"* ]]'
# config isolation
mkdir -p "$H/.claude/token-zombie"; echo '{"limit":12345}' > "$H/.claude/token-zombie/config.json"
o=$(tz config); ok "config from config.json" '[[ $o == *"limit = 12345 (config.json)"* ]]'
o=$(TZ_LIMIT=999 tz config); ok "env beats config" '[[ $o == *"limit = 999 (env)"* ]]'
ok "state dir is under fake HOME" '[ -d "$H/.claude/token-zombie" ]'
# bad input => one-line error, no traceback
o=$(tz handoff --cwd "$T/missing" 2>&1); ok "bad cwd no traceback" '[[ $o != *Traceback* ]]'
o=$(tz status --rate-limits '{x' 2>&1); ok "bad json no traceback" '[[ $o != *Traceback* && $o == *"not valid JSON"* ]]'
# back-compat: old entry points still run alone
o=$(echo '{}' | HOME="$H" python3 "$Z/bin/tz-status.py"); ok "tz-status.py still works" '[[ $o == *TZ* ]]'
echo '{"hook_event_name":"UserPromptSubmit","prompt":"x"}' | HOME="$H" python3 "$Z/bin/tz-guard.py"; ok "tz-guard.py still works" '[ $? = 0 ]'
bash "$Z/bin/tz-vet.sh" "$T/d" >/dev/null; ok "tz-vet.sh still works" '[ $? = 0 ]'
echo "cli: pass $pass fail $fail"; [ $fail = 0 ]
