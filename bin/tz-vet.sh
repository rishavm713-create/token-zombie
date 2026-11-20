#!/bin/bash
# Token-zombie vet: read-only scan of a downloaded skill/plugin folder BEFORE installing it.
# Usage: bash tz-vet.sh <dir>. HIGH = genuinely dangerous pattern (exit 1). REVIEW = docs mention a HIGH pattern
# (read whether it is described or instructed). INFO = normal but worth a look.
# Each finding prints why it matters and file:line evidence. Never installs or runs anything.
D="${1:?usage: tz-vet.sh <dir>}"; hi=0
SELF="$(basename "$0")"  # skip this scanner's own pattern lines
DOC=(--include='*.md' --include='*.txt' --include='*.mdc')
CODE=(--exclude='*.md' --exclude='*.txt' --exclude='*.mdc' --exclude='*.min.js' --exclude='*.map')
scan() { # level, why, regex, [grep include/exclude args]
  r=$(grep -rnIE --exclude-dir=.git --exclude-dir=node_modules --exclude="$SELF" "${@:4}" "$3" "$D" 2>/dev/null | head -4)
  [ -z "$r" ] && return
  echo "[$1] $2"; echo "$r" | cut -c1-160 | sed 's/^/    /'
  [ "$1" = HIGH ] && hi=1
}
both() { # HIGH in code; REVIEW in docs (may only describe it, but a SKILL.md can also tell Claude to do it)
  scan HIGH "$1" "$2" "${CODE[@]}"; scan REVIEW "docs mention: $1 (read: describes it, or tells Claude to do it?)" "$2" "${DOC[@]}"
}
both "downloads and runs code (pipe to shell): can run anything later" \
  '(curl|wget)[^|;]*\|[[:space:]]*(sudo[[:space:]]+)?(ba|z)?sh\b|(ba|z)?sh[[:space:]]+<\([[:space:]]*(curl|wget)|eval[[:space:]]+"?\$\((curl|wget)'
both "reads secrets/credentials: possible data theft" \
  '\.ssh/id_|\.aws/credentials|security find-(generic|internet)-password|Login Data|cookies\.sqlite|keychain-db'
scan HIGH "sends local files or env to a server: possible exfiltration" \
  'curl[^#]*(-d|--data[a-z-]*|-F|--upload-file)[[:space:]]*@|(process\.env|os\.environ)[^#]*(fetch|post|requests)|(dig|nslookup)[[:space:]][^#]*\$[({]' "${CODE[@]}"
both "deletes outside its own folder" \
  'rm[[:space:]]+-[rRf]+[[:space:]]+("?(~|\$HOME|/Users|/home)|/[[:space:]]|/\*)'
scan HIGH "hidden code: decodes then executes" \
  '(eval|exec)[[:space:]]*\(.*(atob|b64decode|base64|fromCharCode)|base64[[:space:]]+(-d|--decode)[^|]*\|[[:space:]]*(ba|z)?sh' "${CODE[@]}"
both "persistence: runs again later without asking (cron, launchd, shell startup files)" \
  'crontab[[:space:]]+-|launchctl[[:space:]]+(load|bootstrap|submit)|Library/LaunchAgents|>>?[[:space:]]*"?(~|\$HOME)/\.(bash|zsh)(rc|_profile)|>>?[[:space:]]*"?(~|\$HOME)/\.profile'
both "turns off permission prompts" 'dangerously-skip-permissions|bypassPermissions|"defaultMode"[[:space:]]*:[[:space:]]*"(bypass|acceptEdits)'
# phrase right after a quote/backtick = quoted as an example (a scanner's docs), not an instruction
scan HIGH "prompt injection: tells Claude to hide things or ignore rules" \
  '(^|[^"`'"'"'[:alnum:]])((ignore|disregard)[[:space:]]+(all[[:space:]]+)?(previous|prior|above)[[:space:]]+instructions|(do not|don.t|never)[[:space:]]+(tell|inform|show)[[:space:]]+the[[:space:]]+user|without[[:space:]]+(asking|telling)[[:space:]]+the[[:space:]]+user)' "${DOC[@]}"
u=$(LC_ALL=C grep -rnlI --exclude-dir=.git --exclude-dir=node_modules -e $'\xe2\x80[\x8b-\x8f]' -e $'\xe2\x80[\xaa-\xae]' -e $'\xe2\x81[\xa0\xa6-\xa9]' "$D" 2>/dev/null | head -4)
[ -n "$u" ] && { echo "[HIGH] hidden unicode (zero-width or text-direction chars): text can say something other than what you see"; echo "$u" | sed 's/^/    /'; hi=1; }
m=$(find "$D" -type f \( -name '*.js' -o -name '*.py' -o -name '*.sh' \) -not -path '*/.git/*' -not -path '*/node_modules/*' -size +2k -exec awk 'length > 3000 {print FILENAME; exit}' {} \; | head -3)
[ -n "$m" ] && echo "[INFO] minified/unreadable code (not pattern-scanned reliably; trust only a known upstream):" && echo "$m" | sed 's/^/    /'
scan INFO "network calls (normal for API skills; check the hosts)" \
  '(fetch|axios\.(get|post)|requests\.(get|post)|urlopen)\(|https?://[a-z0-9.-]+/api'
scan INFO "runs shell commands (check what)" 'child_process|subprocess\.|os\.system\(|execSync\('
scan INFO "touches Claude config (needs your approval to install)" 'settings\.json|\.claude/hooks|enabledPlugins'
echo "files: $(find "$D" -type f -not -path '*/.git/*' | wc -l | tr -d ' '), size: $(du -sh "$D" | cut -f1)"
[ -f "$D/.mcp.json" ] && echo "[INFO] ships an MCP server: adds ~130 tokens per tool at every chat start"
find "$D" -maxdepth 3 -name hooks.json -not -path '*/node_modules/*' | head -3 | sed 's/^/[INFO] hooks file: /'
if [ $hi = 1 ]; then echo "VERDICT: HIGH findings above. Do not install until each line is read and explained."; exit 1; fi
echo "VERDICT: no HIGH findings. Read INFO lines + README, then ask the owner before installing."
