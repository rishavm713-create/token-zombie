#!/bin/bash
# Destructive-command guard is wired in BOTH install paths (plugin hooks.json + install.sh) and denies via the real hook. Fake HOME only.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; pass=0; fail=0; mkdir -p "$H/.claude"
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
pre() { python3 -c 'import json,sys;print(json.dumps({"session_id":"s","cwd":sys.argv[2],"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":sys.argv[1]}}))' "$1" "$T" | HOME="$H" python3 "$Z/bin/tz-guard.py"; }
ok "hooks.json PreToolUse matcher includes Bash" 'python3 -c "import json,sys;g=json.load(open(sys.argv[1]))[\"hooks\"][\"PreToolUse\"];assert any(\"Bash\" in x.get(\"matcher\",\"\").split(\"|\") for x in g)" "$Z/hooks/hooks.json"'
HOME="$H" bash "$Z/install.sh" >/dev/null
ok "install.sh PreToolUse matcher includes Bash" 'python3 -c "import json,sys;g=json.load(open(sys.argv[1]))[\"hooks\"][\"PreToolUse\"];assert any(\"Bash\" in x.get(\"matcher\",\"\").split(\"|\") for x in g)" "$H/.claude/settings.json"'
for c in "rm -rf /" 'rm -rf $HOME/' "bash -c 'rm -rf /'" "sudo rm -rf /usr" "cat ~/.ssh/id_rsa" "git reset --hard" "git push --force origin main"; do
  ok "denies: $c" '[[ "$(pre "$c")" == *"\"permissionDecision\": \"deny\""* ]]'
done
for c in "ls" "rm -rf node_modules" "rm -rf ./build" "git push --force-with-lease" "echo 'rm -rf /'"; do
  ok "allows: $c" '[[ "$(pre "$c")" != *deny* ]]'
done
ok "TZ_SAFE=0 disables" '[[ "$(TZ_SAFE=0 pre "rm -rf /")" != *deny* ]]'
rm -rf "$T"; echo "test_safe_hook: $pass passed, $fail failed"; [ $fail = 0 ]
