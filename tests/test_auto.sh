#!/bin/bash
# levels, instructions lint, profile (dry-run/--yes via stub skillpack), subagent model routing. Fake HOME.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; pass=0; fail=0; mkdir -p "$H/.claude/skills-off/video/cut"
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
printf -- '---\nname: video-cut\ndescription: cut video captions shorts podcast clips youtube edits\n---\n' > "$H/.claude/skills-off/video/cut/SKILL.md"
u() { HOME="$H" python3 "$Z/bin/tzusage.py" status --transcript "$T/none" --rate-limits "$1"; }
for p in "10:NORMAL" "65:ELEVATED" "92:APPROACHING LIMIT" "98:CRITICAL" "100:EXHAUSTED"; do
  o=$(u "{\"five_hour\":{\"used_percentage\":${p%%:*}}}"); ok "level ${p#*:}" '[[ $o == *"level: ${p#*:}"* ]]'; done
o=$(u '{"five_hour":{"used_percentage":98}}'); ok "CRITICAL says handoff, EXHAUSTED says no bypass" '[[ $o == *"tz handoff now"* ]]'
o=$(u '{"five_hour":{"used_percentage":100}}'); ok "exhausted action honest" '[[ $o == *"cannot bypass"* ]]'
# instructions lint
mkdir -p "$T/pr"; python3 -c "print('a long repeated rule line that is duplicated in two files ok\n'*1 + 'x'*9000)" > "$H/.claude/CLAUDE.md"; python3 -c "print('a long repeated rule line that is duplicated in two files ok')" > "$T/pr/CLAUDE.md"
o=$(cd "$T/pr" && HOME="$H" python3 "$Z/bin/tzcap.py" instructions --home "$H"); ok "instructions: sizes + large flag + duplicate" '[[ $o == *"large"* && $o == *"duplicate long lines across files: 1"* ]]'
# profile
o=$(HOME="$H" python3 "$Z/bin/tzcap.py" profile cut video captions youtube shorts --home "$H"); ok "profile plans pack, changes nothing" '[[ $o == *"on  video"* && $o == *"plan only"* ]]'
printf '#!/bin/bash\necho "$@" > "%s/called"\n' "$T" > "$H/.claude/skillpack"; chmod +x "$H/.claude/skillpack"
HOME="$H" python3 "$Z/bin/tzcap.py" profile cut video captions youtube shorts --home "$H" >/dev/null; ok "no --yes: skillpack NOT run" '[ ! -e "$T/called" ]'
o=$(HOME="$H" python3 "$Z/bin/tzcap.py" profile cut video captions youtube shorts --yes --home "$H"); ok "--yes runs skillpack on video" '[ "$(cat $T/called)" = "on video" ] && [[ $o == *"applied on video"* ]]'
o=$(HOME="$H" python3 "$Z/bin/tzcap.py" profile fix typo --yes --home "$H"); ok "irrelevant task: no pack" '[[ $o == *"no pack needed"* ]]'
o=$(HOME="$H" python3 "$Z/bin/tzopt.py" classify research and compare vector dbs); ok "subagent model haiku for research" '[[ $o == *"subagent model param: haiku"* ]]'
o=$(HOME="$H" python3 "$Z/bin/tzopt.py" classify audit repo security); ok "audit keeps deterministic scan" '[[ $o == *"tz security"* ]]'
echo "auto: pass $pass fail $fail"; [ $fail = 0 ]
