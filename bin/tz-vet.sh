#!/bin/bash
# Token-zombie vet: read-only scan of a downloaded skill/plugin folder BEFORE installing it.
# Usage: bash tz-vet.sh <dir>. HIGH = genuinely dangerous pattern (exit 1). LOW = HIGH pattern only in non-executable data under tests/fixtures/docs. A HIGH pattern in a code comment = REVIEW (an agent may read it). REVIEW = docs mention a HIGH pattern
# (read whether it is described or instructed). INFO = normal but worth a look.
# Each finding prints why it matters and file:line evidence. Never installs or runs anything.
D="${1:?usage: tz-vet.sh <dir>}"; hi=0
SELF="$(basename "$0")"  # skip this scanner's own pattern lines
DOC=(--include='*.md' --include='*.txt' --include='*.mdc')
CODE=(--exclude='*.md' --exclude='*.txt' --exclude='*.mdc' --exclude='*.min.js' --exclude='*.map')
# Downgrade by execution risk, not by folder. A HIGH hit is LOW only when it cannot run:
#  - a comment line in code, or
#  - a data file (json/csv/yaml/xml/...) under tests/fixtures/examples/docs paths, not executable, no shebang, not a CI workflow.
# Executable files (script extension, shebang, exec bit, CI workflow, Makefile/Dockerfile) stay HIGH wherever they live:
# test helpers and CI run too. Text Claude reads (.md/.mdc/.txt) is never downgraded.
NONPROD='/(tests?|__tests__|spec|specs|fixtures?|bench|benchmarks?|evals?|evaluation|examples?|e2e|docs?)/'
DATA='\.(json|jsonl|csv|tsv|ya?ml|xml|toml|ini|cfg|conf|snap|golden|out|log|svg|html?)$'
runs() { # file -> 0 if it can execute
  case "$1" in *.github/workflows/*|*/Makefile|*/makefile|*/Dockerfile|*/justfile) return 0;; esac
  [ -x "$1" ] && return 0
  [ "$(head -c2 "$1" 2>/dev/null)" = '#!' ] && return 0
  echo "$1" | grep -qE "$DATA" && return 1
  return 0  # unknown or script extension: assume it runs
}
split() { # stdin grep -n lines -> "P<TAB>line" (stays HIGH) or "L<TAB>line" (cannot run)
  while IFS= read -r l; do
    [ -z "$l" ] && continue
    v=""; r=$l; case "$l" in [A-Za-z]:[/\\]*) v=${l:0:2}; r=${l:2};; esac  # Windows drive letter: its colon is part of the path
    f=$v${r%%:*}; c=${r#*:*:}; c=${c#"${c%%[![:space:]]*}"}
    if echo "$f" | grep -qE '\.(md|mdc|txt)$'; then printf 'P\t%s\n' "$l"
    elif echo "$c" | grep -qE '^(#[^!]|#$|//|/\*|\*|<!--|--[[:space:]])'; then printf 'C\t%s\n' "$l"
    elif echo "/$f" | grep -qE "$NONPROD" && ! runs "$f"; then printf 'L\t%s\n' "$l"
    else printf 'P\t%s\n' "$l"; fi
  done
}
scan() { # level, why, regex, [grep include/exclude args]
  r=$(grep -rnIE --exclude-dir=.git --exclude-dir=node_modules --exclude="$SELF" "${@:4}" "$3" "$D" 2>/dev/null | head -200)
  [ -z "$r" ] && return
  if [ "$1" = HIGH! ]; then echo "[HIGH] $2"; echo "$r" | head -4 | cut -c1-160 | sed 's/^/    /'; hi=1; return; fi  # never downgraded
  if [ "$1" = HIGH ]; then
    t=$(echo "$r" | split); p=$(echo "$t" | grep '^P' | cut -f2- | head -4); n=$(echo "$t" | grep -c '^L'); k=$(echo "$t" | grep '^C' | cut -f2-)
    if [ -z "$p" ]; then  # cannot run. A comment is still text an agent may read and follow: REVIEW, never LOW
      [ -n "$k" ] && { echo "[REVIEW] $2: in a code comment (cannot run; an AI agent reading the file may follow it)"; echo "$k" | head -2 | cut -c1-160 | sed 's/^/    /'; }
      [ "$n" -gt 0 ] && { echo "[LOW] $2 (only in non-executable test/fixture data: $n hits)"; echo "$t" | grep '^L' | cut -f2- | head -2 | cut -c1-160 | sed 's/^/    /'; }
      return
    fi
    echo "[HIGH] $2"; echo "$p" | cut -c1-160 | sed 's/^/    /'; m=$(( n + $(echo -n "$k" | grep -c .) )); [ "$m" -gt 0 ] && echo "    (+$m more in comments or non-executable data: REVIEW/LOW)"
    hi=1; return
  fi
  echo "[$1] $2"; echo "$r" | head -4 | cut -c1-160 | sed 's/^/    /'
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
# docs: a phrase right after a quote/backtick = quoted as an example (a scanner's docs). Code/data: no such exemption
# (every JSON/YAML string is quoted, so the exemption would hide injected text there).
INJ='((ignore|disregard)[[:space:]]+(all[[:space:]]+)?(previous|prior|above)[[:space:]]+instructions|(do not|don.t|never)[[:space:]]+(tell|inform|show)[[:space:]]+the[[:space:]]+user|without[[:space:]]+(asking|telling)[[:space:]]+the[[:space:]]+user)'
scan HIGH! "prompt injection in docs: tells Claude to hide things or ignore rules (never downgraded)" "(^|[^\"\`'[:alnum:]])$INJ" "${DOC[@]}"
scan HIGH! "prompt injection in code/data (comments and strings included): tells an agent to hide things or ignore rules (never downgraded)" "(^|[^[:alnum:]])$INJ" "${CODE[@]}"
u=$(LC_ALL=C grep -rnlI --exclude-dir=.git --exclude-dir=node_modules -e $'\xe2\x80[\x8b-\x8f]' -e $'\xe2\x80[\xaa-\xae]' -e $'\xe2\x81[\xa0\xa6-\xa9]' "$D" 2>/dev/null | head -40)
up=$(echo "$u" | grep -v '^$' | sed 's/$/:0:x/' | split | grep '^P' | cut -f2 | sed 's/:0:x$//')
[ -n "$u" ] && [ -z "$up" ] && echo "[LOW] hidden unicode only in non-executable test/fixture data: $(echo "$u" | head -2 | tr '\n' ' ')"
u=$up
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
