#!/bin/bash
# On-demand capabilities: off by default, on for a task, off at chat end, verified, logged, rollback. Fake HOME only.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
export HOME="$T/home"; C="$HOME/.claude"; S="$C/token-zombie"; pass=0; fail=0
mkdir -p "$S" "$C/skills/editsutra" "$C/skills/handoff"
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
tz() { python3 "$Z/bin/tz" "$@"; }
g() { echo "{\"hook_event_name\":\"$1\",\"session_id\":\"$2\",\"prompt\":\"$3\",\"cwd\":\"$T\"}" | python3 "$Z/bin/tz-guard.py"; }
echo '{"mcpServers":{"premiere-pro":{"command":"node","args":["x.js"]}},"other":1}' > "$HOME/.claude.json"
echo '{"enabledPlugins":{"token-zombie@token-zombie":true,"humanizer@humanizer":false}}' > "$C/settings.json"
echo x > "$C/skills/editsutra/SKILL.md"; cp "$HOME/.claude.json" "$T/orig.json"

# default off
o=$(tz ondemand off premiere-pro editsutra); ok "off: MCP + skill verified" '[[ $o == *"premiere-pro (mcp): off VERIFIED"* && $o == *"editsutra (skill): off VERIFIED"* ]]'
ok "off: MCP parked, not deleted; other keys kept" 'python3 -c "import json;a=json.load(open(\"$HOME/.claude.json\"));p=json.load(open(\"$S/parked-mcp.json\"));assert \"premiere-pro\" not in a[\"mcpServers\"] and a[\"other\"]==1 and p[\"premiere-pro\"][\"command\"]==\"node\""'
ok "off: skill moved, not deleted" '[ -f "$C/skills-off/_tz/editsutra/SKILL.md" ] && [ ! -d "$C/skills/editsutra" ]'
ok "backup made before change" 'ls -a "$S/cap-backups/" | grep -q "^.claude.json."'
o=$(tz ondemand off token-zombie@token-zombie handoff); ok "essential items protected" '[[ $o == *protected* ]] && python3 -c "import json;assert json.load(open(\"$C/settings.json\"))[\"enabledPlugins\"][\"token-zombie@token-zombie\"]" && [ -d "$C/skills/handoff" ]'
o=$(tz ondemand off claude-in-chrome scheduled-tasks mcp-registry); ok "app built-ins: explained, not touched" '[[ $o == *"managed by the desktop app"* ]]'

# detect -> on for the task
o=$(g UserPromptSubmit s1 "cut the premiere timeline"); ok "prompt needs premiere: hint names the command" '[[ $o == *"tz ondemand on premiere-pro --session s1"* ]]'
o=$(tz ondemand on premiere-pro editsutra --session s1); ok "on: verified, next-chat limit stated" '[[ $o == *"premiere-pro (mcp): on VERIFIED"*"next chat"* && $o == *"editsutra (skill): on VERIFIED"* ]]'
ok "on: config restored exactly" 'python3 -c "import json;assert json.load(open(\"$HOME/.claude.json\"))==json.load(open(\"$T/orig.json\"))"'
o=$(tz ondemand on humanizer@humanizer --session s1); ok "plugin on verified" '[[ $o == *"on VERIFIED"* ]]'

# another chat also uses premiere: kept on at s1 end
tz ondemand on premiere-pro --session s2 >/dev/null
g SessionEnd s1 >/dev/null
o=$(tz ondemand); ok "chat end: s1-only caps off, shared one kept" '[[ $o == *"editsutra"*"skill"*"off"* ]] && python3 -c "import json;a=json.load(open(\"$HOME/.claude.json\"));s=json.load(open(\"$C/settings.json\"));assert \"premiere-pro\" in a[\"mcpServers\"] and not s[\"enabledPlugins\"][\"humanizer@humanizer\"]"'
o=$(tz ondemand off premiere-pro --session s2); ok "off again verified" '[[ $o == *"off VERIFIED"* ]]'

# events in 24h report + dashboard
o=$(tz stats); ok "24h report lists events" '[[ $o == *"on-demand events 24h"*"on premiere-pro ok"* && $o == *"off editsutra ok"* ]]'
tz dash --out "$T/d.html" >/dev/null; ok "dashboard shows events" 'grep -q "On-demand capabilities" "$T/d.html" && grep -q "premiere-pro" "$T/d.html"'

# recovery: one-command rollback restores newest backups and parked skills
tz ondemand off editsutra >/dev/null 2>&1; o=$(tz ondemand rollback); ok "rollback restores" '[[ $o == *restored* ]] && [ -d "$C/skills/editsutra" ]'
echo '{broken' > "$HOME/.claude.json"; o=$(tz ondemand on premiere-pro 2>&1); ok "broken config: refused, file untouched" '[[ $o == *"not valid JSON; nothing changed"* ]] && [ "$(cat "$HOME/.claude.json")" = "{broken" ]'

echo "ondemand: pass $pass fail $fail"; [ $fail = 0 ]
