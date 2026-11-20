#!/bin/bash
# Plugin packaging tests: manifests, commands, hooks vs install.sh, skill refs, --statusline-only. Fake HOME only.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; pass=0; fail=0; mkdir -p "$H/.claude"
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
py() { python3 -c "$@"; }
P="$Z/.claude-plugin/plugin.json"; M="$Z/.claude-plugin/marketplace.json"
ok "plugin.json valid, name+version+description+author" 'py "import json,sys;d=json.load(open(sys.argv[1]));assert d[\"name\"]==\"token-zombie\" and d[\"version\"] and d[\"description\"] and d[\"author\"][\"name\"]" "$P"'
ok "marketplace.json valid, name+owner+plugin entry matches plugin.json" 'py "import json,sys;m=json.load(open(sys.argv[1]));p=json.load(open(sys.argv[2]));e=m[\"plugins\"][0];assert m[\"name\"]==p[\"name\"]==e[\"name\"] and m[\"owner\"][\"name\"]" "$M" "$P"'
ok "marketplace source resolves to a dir holding plugin.json" 'py "import json,sys,os;m=json.load(open(sys.argv[1]));s=m[\"plugins\"][0][\"source\"];assert os.path.isfile(os.path.join(sys.argv[2],s,\".claude-plugin\",\"plugin.json\"))" "$M" "$Z"'
# commands
TZSUBS=$(python3 "$Z/bin/tz" help | awk 'NR>1{print $1}' | sort -u)
for c in tz optimize audit review compact board supervisor benchmark; do
  f="$Z/commands/$c.md"
  ok "command $c: file + description frontmatter" '[ -f "$f" ] && [ "$(sed -n 1p "$f")" = --- ] && sed -n 2,4p "$f" | grep -q "^description: "'
  sub=$(grep -o '"\${CLAUDE_PLUGIN_ROOT}/bin/tz" [a-z-]*' "$f" | head -1 | awk '{print $2}')
  case "$c" in tz) sub=status;; supervisor) sub=sup;; esac
  ok "command $c names real tz subcommand ($sub)" '[ -n "$sub" ] && echo "$TZSUBS" | grep -qx "$sub"'
done
ok "compact command admits it cannot run /compact" 'grep -q "cannot run /compact" "$Z/commands/compact.md"'
# hooks vs install.sh
ok "hooks.json modules + 7 events + scripts exist, same events as install.sh" 'py "
import json,sys,re,os
z=sys.argv[1]; h=json.load(open(z+\"/hooks/hooks.json\"))
assert h[\"modules\"]==[\"./panel.tsx\"] and os.path.exists(z+\"/hooks/panel.tsx\")
ev=set(h[\"hooks\"]); ins=set(re.search(r\"EVENTS = \((.*?)\)\",open(z+\"/install.sh\").read()).group(1).replace(\"\x27\",\"\").replace(\" \",\"\").split(\",\"))
assert ev==ins,(ev,ins)
for e,gs in h[\"hooks\"].items():
  for g in gs:
    for x in g[\"hooks\"]:
      m=re.fullmatch(r\"python3 \\\"\\\${CLAUDE_PLUGIN_ROOT}/bin/([\w.-]+)\\\"\",x[\"command\"]); assert m,x
      assert os.path.isfile(z+\"/bin/\"+m.group(1)) and x[\"timeout\"]==5
" "$Z"'
ok "hook plan matches install.sh (matchers, scripts)" 'py "
import json,sys,re
z=sys.argv[1]; h=json.load(open(z+\"/hooks/hooks.json\"))[\"hooks\"]
plan=re.search(r\"plan = \((.*?)\)\n    for ev\",open(z+\"/install.sh\").read(),re.S).group(1)
want=re.findall(r\"\(\x27(\w+)\x27, (None|\x27\x27|\x27\w+\x27), (\w+)\)\",plan); assert len(want)==8
nm={\"guard\":\"tz-guard.py\",\"start\":\"tz-start.py\",\"compact\":\"tz-compact.py\"}
got=[]
for e,gs in h.items():
  for g in gs: got.append((e,g.get(\"matcher\"),re.search(r\"bin/([\w.-]+)\",g[\"hooks\"][0][\"command\"]).group(1)))
exp=sorted((e,None if m==\"None\" else m.strip(chr(39)),nm[s]) for e,m,s in want)
assert sorted(got,key=str)==sorted(exp,key=str),(got,exp)
" "$Z"'
ok "every \${CLAUDE_PLUGIN_ROOT} is double-quoted" '! grep -rhoE "[^\"]\\\$\{CLAUDE_PLUGIN_ROOT\}[^\"]*" "$Z/hooks/hooks.json" "$Z/commands" | grep -v "^.\\\${CLAUDE_PLUGIN_ROOT}/bin/tz\" " | grep -q .'
# skill
S="$Z/skills/token-zombie/SKILL.md"
ok "SKILL.md frontmatter name+description" '[ "$(sed -n 1p "$S")" = --- ] && sed -n 2p "$S" | grep -q "^name: token-zombie$" && sed -n 3p "$S" | grep -q "^description: ." && [ "$(sed -n 4p "$S")" = --- ]'
ok "SKILL.md lean (<= 90 lines)" '[ "$(wc -l < "$S")" -le 90 ]'
ok "SKILL.md references/ links resolve (12)" 'L=$(grep -oE "\]\(references/[a-z-]+\.md\)" "$S" | tr -d "]()" | sort -u); [ $(echo "$L" | wc -l) -eq 12 ] && for r in $L; do [ -s "$Z/skills/token-zombie/$r" ] || false; done'
ok "no root SKILL.md left" '[ ! -e "$Z/SKILL.md" ]'
# statusline-only
S2="$H/.claude/settings.json"; echo '{"model":"sonnet","statusLine":{"type":"command","command":"echo prev"}}' > "$S2"
i() { HOME="$H" bash "$Z/install.sh" "$@"; }
i --statusline-only >/dev/null; cp "$S2" "$T/a"
ok "statusline-only sets statusLine, no hooks, keeps model" 'grep -q tz-status "$S2" && ! grep -q tz-guard "$S2" && grep -q sonnet "$S2"'
i --statusline-only >/dev/null
ok "statusline-only idempotent (same file, prev kept)" 'cmp -s "$S2" "$T/a" && grep -q "echo prev" "$H/.claude/token-zombie/config.json"'
i --uninstall >/dev/null
ok "uninstall removes it and restores previous statusline" '! grep -q tz-status "$S2" && grep -q "echo prev" "$S2"'
# validator
if command -v claude >/dev/null; then
  HOME="$H" claude plugin validate "$Z" >"$T/v.out" 2>&1; rc=$?; ok "claude plugin validate exits 0" '[ $rc = 0 ]'
else echo "SKIP: claude not installed"; fi
echo "plugin: pass $pass fail $fail"; [ $fail = 0 ]
