#!/usr/bin/env bash
# tz go: install-state check (temp HOME only, never the live ~/.claude)
cd "$(dirname "$0")/.." || exit 1
T=$(mktemp -d); export HOME="$T"; unset CLAUDE_CONFIG_DIR; P=0; F=0
ok(){ if eval "$1"; then echo "ok $2"; P=$((P+1)); else echo "FAIL $2"; F=$((F+1)); fi; }
ok "python3 bin/tz go | grep -q 'tz go --yes'" missing-next-step
mkdir -p "$T/.claude"; echo '{"hooks":{"Stop":[{"hooks":[{"command":"x/tz-guard.py"}]}]}}' > "$T/.claude/settings.json"
ok "python3 bin/tz go | grep -q 'Nothing to do'" ok-state
echo '{bad' > "$T/.claude/settings.json"
ok "! python3 bin/tz go >/dev/null" broken-exit1
ok "python3 bin/tz help 2>&1 | grep -q 'go \[--yes\]'" in-help
echo "pass $P fail $F"; [ "$F" = 0 ]
