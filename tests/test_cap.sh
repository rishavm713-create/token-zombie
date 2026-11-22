#!/bin/bash
# v0.1 capability + security tests. Fake HOME only; scans temp dirs.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; pass=0; fail=0
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
c() { python3 "$Z/bin/tzcap.py" "$@" --home "$H"; }
mk() { mkdir -p "$1"; printf -- '---\nname: %s\ndescription: %s\n---\nbody\n' "$2" "$3" > "$1/SKILL.md"; }
mk "$H/.claude/skills/pdf-tool" pdf-tool "extract text tables from pdf documents and merge split pdf files"
mk "$H/.claude/skills/pdf-two" pdf-two "extract text tables from pdf documents and merge split pdf files"
mk "$H/.claude/skills/ui" ui-design "design polish user interface components critique"
mk "$H/.claude/skills-off/video/cut" video-cut "cut video captions shorts podcast clips youtube edits"
echo '{"enabledPlugins":{"a@b":true,"c@d":false},"mcpServers":{"fs":{}},"hooks":{"Stop":[{"hooks":[{"command":"x"}]}]}}' > "$H/.claude/settings.json"
o=$(c capabilities); ok "inventory counts" '[[ $o == *"skills 3"* && $o == *"parked 1"* && $o == *"plugins enabled 1"* && $o == *"MCP servers 1"* && $o == *"hooks 1"* ]]'
ok "plugin/MCP schema cost UNKNOWN not invented" '[[ $o == *UNKNOWN* ]]'
ok "duplicate capabilities found" '[[ $o == *"pdf-tool ~ pdf-two"* || $o == *"pdf-two ~ pdf-tool"* ]]'
o=$(c skills); ok "startup vs parked split" '[[ $o == *"loaded at startup: 3"* && $o == *"parked: 1"* && $o == *"NOT loaded"* ]]'
o=$(c skills cut video captions for my youtube shorts); ok "relevance: parked pack suggested, asks first" '[[ $o == *"video-cut"* && $o == *"skillpack on video"* && $o == *"ask first"* ]]'
o=$(c skills fix a typo in readme); ok "no relevant skill => none" '[[ $o == none* ]]'
o=$(c skills design polish interface components); ok "installed match says already loaded" '[[ $o == *"ui-design"*"already loaded"* ]]'
# security grading
mkdir -p "$T/g" "$T/y" "$T/r"; echo 'print("hi")' > "$T/g/a.py"
echo 'cat ~/.ssh/''id_rsa' > "$T/r/s.sh"
echo '{"mcpServers":{}}' > "$T/y/.mcp.json"
o=$(c security "$T/g"); r=$?; ok "GREEN + disclaimer" '[[ $o == GREEN* && $o == *"not proof"* && $r = 0 ]]'
o=$(c security "$T/y"); ok "YELLOW for shipped MCP" '[[ $o == YELLOW* ]]'
o=$(c security "$T/r"); r=$?; ok "RED + exit 1 for secret exfil" '[[ $o == RED* && $r = 1 ]]'
c security "$T/none" 2>/dev/null; ok "bad dir => exit 2" '[ $? = 2 ]'
o=$(c audit); ok "audit summarises all skill dirs" '[[ $o == *"audited 3 of 3"* ]]'
cp -r "$T/r" "$H/.claude/skills/evil"; o=$(c audit); r=$?; ok "audit exit 1 on RED" '[[ $o == *"RED evil"* && $r = 1 ]]'
ok "read-only: settings untouched" 'grep -q "a@b" "$H/.claude/settings.json"'
# instructions conflicts
P="$T/proj"; mkdir -p "$P"; mkdir -p "$H/.claude"
printf 'Always commit changes after each finished task in this project.\nReply in short terse messages for the owner always.\n' > "$H/.claude/CLAUDE.md"
printf 'Never commit changes after each finished task in this project.\nReply in short terse messages for the owner always.\n' > "$P/CLAUDE.md"
o=$(cd "$P" && python3 "$Z/bin/tzcap.py" instructions --home "$H")
ok "conflict found with both file:line" '[[ $o == *"EST keyword heuristic] possible conflict"* && $o == *"CLAUDE.md:1"* ]]'
ok "duplicate found" '[[ $o == *"duplicate: "*"CLAUDE.md:2"* ]]'
printf 'Use pytest for running every unit test here.\n' > "$H/.claude/CLAUDE.md"
printf 'Keep replies short and plain for the owner.\n' > "$P/CLAUDE.md"
o=$(cd "$P" && python3 "$Z/bin/tzcap.py" instructions --home "$H")
ok "clean files => none" '[[ $o == *"no likely conflicts found"* && $o != *"duplicate: "* ]]'
echo "cap: pass $pass fail $fail"; [ $fail = 0 ]
