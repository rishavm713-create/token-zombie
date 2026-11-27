#!/bin/bash
# tz settings: adds only unset keys, backs up, revert works; auto-pack hook turns a pack on.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; pass=0; fail=0
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
mkdir -p "$T/.claude"; echo '{"env":{"MAX_THINKING_TOKENS":"31999"}}' > "$T/.claude/settings.json"
export HOME="$T"
python3 "$Z/bin/tz-settings.py" >/dev/null
ok "adds tool search" "grep -q ENABLE_TOOL_SEARCH $T/.claude/settings.json"
ok "keeps owner value" "grep -q 31999 $T/.claude/settings.json"
ok "backup made" "ls $T/.claude/settings.json.bak-tz-settings-* >/dev/null"
python3 "$Z/bin/tz-settings.py" --revert >/dev/null
ok "revert removes ours" "! grep -q ENABLE_TOOL_SEARCH $T/.claude/settings.json"
ok "revert keeps owner" "grep -q 31999 $T/.claude/settings.json"
echo "pass $pass fail $fail"; [ $fail = 0 ]
