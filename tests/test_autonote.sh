#!/bin/bash
# Offline auto-note: written by hook (no model), throttled, injected into a NEW chat only when work was left open. Fake HOME.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; W="$T/proj"; mkdir -p "$H/.claude" "$W"; pass=0; fail=0
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
LOG="$T/log.jsonl"
echo '{"type":"user","message":{"role":"user","content":"build the thing"}}' > "$LOG"
echo '{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":"u1","name":"mcp__ccd_turn__update_plan","input":{"items":[{"content":"step A","status":"completed"},{"content":"step B open","status":"in_progress"}]}}]}}' >> "$LOG"
P="{\"session_id\":\"a1\",\"cwd\":\"$W\",\"transcript_path\":\"$LOG\",\"hook_event_name\":\"PostToolUse\",\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"ls\"}}"
echo "$P" | HOME="$H" TZ_SUP=0 TZ_DEDUPE=0 python3 "$Z/bin/tz-guard.py"; sleep 3
N=$(ls "$H"/.claude/token-zombie/last-*.md 2>/dev/null | head -1)
ok "note written by hook, offline" '[ -n "$N" ]'
ok "note names the open step" 'grep -q "Next step: step B open" "$N"'
ok "note is small" '[ "$(wc -c < "$N")" -le 1600 ]'
rm -f "$N"; echo "$P" | HOME="$H" TZ_SUP=0 TZ_DEDUPE=0 python3 "$Z/bin/tz-guard.py"; sleep 2
ok "throttled: no second write within 2 min" '[ -z "$(ls "$H"/.claude/token-zombie/last-*.md 2>/dev/null)" ]'
cp "$H/.claude/token-zombie/compact-a1.md" "$T/body.md"
K=$(python3 -c "import hashlib;print('last-'+hashlib.sha1('$W'.encode()).hexdigest()[:10]+'.md')")
cp "$T/body.md" "$H/.claude/token-zombie/$K"
S="{\"session_id\":\"b2\",\"cwd\":\"$W\",\"source\":\"startup\",\"hook_event_name\":\"SessionStart\"}"
o=$(echo "$S" | HOME="$H" TZ_FRESH_BG=0 python3 "$Z/bin/tz-start.py")
ok "new chat gets the open-work note" '[[ $o == *"step B open"* ]]'
ok "resume does not get it" '[[ $(echo "${S/startup/resume}" | HOME="$H" TZ_FRESH_BG=0 python3 "$Z/bin/tz-start.py") != *"previous chat here"* ]]'
sed -i.bak 's/Next step: .*/Next step: all listed steps done/' "$H/.claude/token-zombie/$K"
o=$(echo "$S" | HOME="$H" TZ_FRESH_BG=0 python3 "$Z/bin/tz-start.py")
ok "finished work is not re-injected" '[[ $o != *"previous chat here"* ]]'
mkdir -p "$W/handoffs"; echo "${P/PostToolUse/Stop}" | sed 's/}$/,"trigger":"auto"}/' | HOME="$H" TZ_DEDUPE=0 python3 "$Z/bin/tz-compact.py"
HF=$(ls "$W"/handoffs/*-auto.md 2>/dev/null | head -1)
ok "offline daily handoff written" '[ -n "$HF" ]'
ok "handoff lists done and left" 'grep -q "step A" "$HF" && grep -q "step B open" "$HF"'
ok "handoff <= 30 lines" '[ "$(wc -l < "$HF")" -le 30 ]'
echo "autonote: pass $pass fail $fail"; [ $fail -eq 0 ]
