#!/bin/bash
# Dashboard v0.3: four headline metrics, SVG mascot states, honesty labels, no scripts/external refs. Fake HOME only.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; pass=0; fail=0; S="$H/.claude/token-zombie"; mkdir -p "$S" "$H/.claude/skills/a" "$H/.claude/skills/b"
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
tz() { HOME="$H" python3 "$Z/bin/tz" "$@"; }
touch "$H/.claude/skills/a/SKILL.md" "$H/.claude/skills/b/SKILL.md"
NOW=$(date +%s)

tz dash --out "$T/d.html" >/dev/null
for m in "AGENTS RUNNING" "SKILLS IN USE" "TOKENS SAVED" "OPTIMIZATIONS EXECUTED"; do ok "metric tile: $m" "grep -q '$m' '$T/d.html'"; done
ok "no data: agents UNKNOWN, not a number" 'grep -A2 "AGENTS RUNNING" "$T/d.html" | grep -q "—"'
ok "no data: mascot sleeps" 'grep -q "tz-zombie tz-sleep" "$T/d.html"'
ok "skills counted from disk (2)" 'grep -A1 "SKILLS IN USE" "$T/d.html" | grep -q "class=\"val\">2<"'
ok "tokens saved labelled EST + no-baseline note" 'grep -q "t-est\">EST" "$T/d.html" && grep -q "no A/B baseline" "$T/d.html"'
ok "self-contained: no script, no external src/href" '! grep -qiE "<script|src=.?http|href=.?http|url\(.?http" "$T/d.html"'
ok "reduced-motion respected" 'grep -q "prefers-reduced-motion" "$T/d.html"'

# measured inputs
printf '{"running":3,"total":4,"ts":%s}' "$NOW" >"$S/agents.json"
printf '[{"t":%s,"kind":"filter","tok":500,"basis":"measured"},{"t":1,"kind":"dup-read-flagged","tok":900,"basis":"est"},{"t":1,"kind":"overhead-hook","tok":20,"basis":"measured"}]' "$NOW" >"$S/ledger.json"
printf '{"ts":%s,"level":"NORMAL","activity":"idle","cwd":"x"}' "$NOW" >"$S/status.json"
tz dash --out "$T/m.html" >/dev/null
ok "agents running from fresh agents.json (3, MEASURED)" 'grep -A2 "AGENTS RUNNING" "$T/m.html" | grep -q "class=\"val\">3<"'
ok "optimizations = measured non-overhead entries (1)" 'grep -A1 "OPTIMIZATIONS EXECUTED" "$T/m.html" | grep -q "class=\"val\">1<"'
ok "tokens saved = measured minus overhead (480), est flags excluded" 'grep -A1 "TOKENS SAVED" "$T/m.html" | grep -q "class=\"val\">480<"'
ok "recent measured saving => excited mascot" 'grep -q "tz-zombie tz-excited" "$T/m.html"'
printf '{"running":3,"ts":1}' >"$S/agents.json"; tz dash --out "$T/s.html" >/dev/null
ok "stale agents.json => UNKNOWN" 'grep -A2 "AGENTS RUNNING" "$T/s.html" | grep -q "—"'
echo 'not json' >"$S/agents.json"; echo '{"x":1}' >"$S/ledger.json"
ok "corrupt agents/ledger files: dash survives" 'tz dash --out "$T/c.html" >/dev/null && grep -q "TOKENS SAVED" "$T/c.html"'

# visual state mapping (pure function)
vs() { HOME="$H" python3 -c "import sys,time;sys.path.insert(0,'$Z/bin');import tzzombie as z;print(z.visual_state($1))"; }
ok "ALERT beats everything" '[ "$(vs "{\"ts\":time.time()},\"ALERT\",5,True")" = alert ]'
ok "celebrate => excited" '[ "$(vs "{\"ts\":time.time()},\"CELEBRATE\"")" = excited ]'
ok "agents running => working" '[ "$(vs "{\"ts\":time.time()},\"HAPPY\",2")" = working ]'
ok "chomp => working" '[ "$(vs "{\"ts\":time.time()},\"CHOMP\"")" = working ]'
ok "idle 31 min => sleep" '[ "$(vs "{\"ts\":time.time()-1860},\"HAPPY\"")" = sleep ]'
ok "fresh + happy => idle" '[ "$(vs "{\"ts\":time.time()},\"HAPPY\"")" = idle ]'
for v in idle working excited alert sleep; do
  ok "svg state $v renders, has both hands + legs" "HOME='$H' python3 -c \"import sys;sys.path.insert(0,'$Z/bin');import tzzombie as z;s=z.svg_zombie('$v');assert s.count('tz-hand')==2 and s.count('tz-leg ')==2 and 'tz-$v' in s\""
done
ok "unknown state falls back to idle" "HOME='$H' python3 -c \"import sys;sys.path.insert(0,'$Z/bin');import tzzombie as z;assert 'tz-idle' in z.svg_zombie('nope')\""
ok "mascot override env for previews" 'TZ_MASCOT_STATE=alert tz dash --out "$T/a.html" >/dev/null && grep -q "tz-zombie tz-alert" "$T/a.html"'
echo "dash2: pass $pass fail $fail"; rm -rf "$T"; [ $fail = 0 ]
