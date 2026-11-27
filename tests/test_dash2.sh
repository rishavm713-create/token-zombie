#!/bin/bash
# Dashboard v0.3: four headline metrics, SVG mascot states, honesty labels, no scripts/external refs. Fake HOME only.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; pass=0; fail=0; S="$H/.claude/token-zombie"; mkdir -p "$S" "$H/.claude/skills/a" "$H/.claude/skills/b"
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
tz() { HOME="$H" python3 "$Z/bin/tz" "$@"; }
touch "$H/.claude/skills/a/SKILL.md" "$H/.claude/skills/b/SKILL.md"
NOW=$(date +%s)

tz dash --out "$T/d.html" >/dev/null
for m in "AGENTS RUNNING" "SKILLS ENABLED" "TOKENS SAVED" "OPTIMIZATIONS EXECUTED"; do ok "metric tile: $m" "grep -q '$m' '$T/d.html'"; done
ok "no data: agents UNKNOWN, not a number" 'grep -A2 "AGENTS RUNNING" "$T/d.html" | grep -q "—"'
ok "no data: mascot sleeps" 'grep -q "tz-zombie tz-sleep" "$T/d.html"'
ok "skills counted from disk (2)" 'grep -A1 "SKILLS ENABLED" "$T/d.html" | grep -q "class=\"val\">2<"'
ok "tokens saved labelled EST + no-baseline note" 'grep -q "t-est\">EST" "$T/d.html" && grep -q "no A/B baseline" "$T/d.html"'
ok "self-contained: no script, no external src/href" '! grep -qiE "<script|src=.?http|href=.?http|url\(.?http" "$T/d.html"'
ok "reduced-motion respected" 'grep -q "prefers-reduced-motion" "$T/d.html"'

# measured inputs
printf '{"running":3,"total":4,"ts":%s}' "$NOW" >"$S/agents.json"
printf '[{"t":%s,"kind":"filter","tok":500,"basis":"measured"},{"t":%s,"kind":"dup-read-flagged","tok":900,"basis":"est"},{"t":%s,"kind":"overhead-hook","tok":20,"basis":"measured"}]' "$NOW" "$NOW" "$NOW" >"$S/ledger.json"
printf '{"ts":%s,"level":"NORMAL","activity":"idle","cwd":"x"}' "$NOW" >"$S/status.json"
tz dash --out "$T/m.html" >/dev/null
ok "agents running from fresh agents.json (3, MEASURED)" 'grep -A2 "AGENTS RUNNING" "$T/m.html" | grep -q "class=\"val\">3<"'
ok "optimizations = measured non-overhead entries (1)" 'grep -A1 "OPTIMIZATIONS EXECUTED" "$T/m.html" | grep -q "class=\"val\">1<"'
ok "tokens saved = measured minus overhead (480), est flags excluded" 'grep -A1 "TOKENS SAVED" "$T/m.html" | grep -q "class=\"val\">480<"'
ok "recent measured saving => excited mascot" 'grep -q "tz-zombie tz-excited" "$T/m.html"'
chip() { grep -o 'mascot <b>[A-Z]*</b></span>' "$1" | sed 's/.*<b>//;s/<.*//'; }
ok "mascot chip = animated state, one state only (EXCITED)" '[ "$(chip "$T/m.html")" = EXCITED ] && ! grep -q "mascot <b>[A-Z]*</b> ·" "$T/m.html"'
ok "mascot chip = animated state with no data (SLEEP)" '[ "$(chip "$T/d.html")" = SLEEP ] && grep -q "tz-zombie tz-sleep" "$T/d.html"'
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
# slim bar default view (v0.3.1): one bar is the <summary>, full detail behind <details>, one mascot inside the bar
ok "bar: details collapsed by default, bar is its summary" 'grep -q "<details class=tzx><summary class=tzbar" "$T/m.html" && ! grep -q "class=tzx open" "$T/m.html"'
ok "bar: mascot sits inside the bar, drawn once" 'grep -q "<span class=bz><svg class=\"tz-zombie" "$T/m.html" && [ "$(grep -o "<svg class=\"tz-zombie" "$T/m.html" | wc -l | tr -d " ")" = 1 ]'
for l in AGENTS "SKILLS USED" "TOKENS SAVED" OPTIMIZATIONS; do ok "bar label: $l" "grep -q 'class=bl>$l' '$T/m.html'"; done
ok "bar: saved is green, no EST tag on the bar (480)" 'grep -q "<span class=\"bm g\"><b class=bn>480</b><span class=bl>TOKENS SAVED</span>" "$T/m.html"'
ok "bar: agents 3, opts 1" 'grep -q "<b class=bn>3</b><span class=bl>AGENTS" "$T/m.html" && grep -q "<b class=bn>1</b><span class=bl>OPTIMIZATIONS" "$T/m.html"'
ok "bar: mode pill + status dot + chevron" 'grep -q "class=\"pill\">FULL<" "$T/m.html" && grep -q "class=\"dot " "$T/m.html" && grep -q "class=chev" "$T/m.html"'
ok "bar: no description/notes/feed in the summary" '! sed -n "/<summary class=tzbar/,/<\/summary>/p" "$T/m.html" | grep -qE "class=note|class=tile|<table|Ledger"'
ok "bar: big numbers abbreviated (12345 -> 12K)" 'printf "[{\"t\":$NOW,\"kind\":\"filter\",\"tok\":12345,\"basis\":\"measured\"}]" >"$S/ledger.json" && tz dash --out "$T/k.html" >/dev/null && grep -q "<b class=bn>12K</b>" "$T/k.html"'
printf '{"mode":"off"}' >"$S/config.json"
ok "bar: mode off => dim pill + Off state" 'tz dash --out "$T/o.html" >/dev/null && grep -q "class=\"pill off\">OFF<" "$T/o.html" && grep -q "class=\"dot off\"" "$T/o.html"'
rm -f "$S/config.json"
ok "Mod mascot assets match bin/tzzombie.py (regen: python3 bin/tzzombie.py assets)" 'python3 "$Z/bin/tzzombie.py" "$T/as" && diff -r "$T/as" "$Z/assets" >/dev/null && grep -q "<style>" "$Z/assets/zombie-idle.svg" && [ $(wc -c <"$Z/assets/zombie-excited.svg") -lt 131072 ]'
ok "mascot click: scratch pose (raised hand) + groan sound wired in the panel" 'grep -q tz-scratchhand "$Z/assets/zombie-scratch.svg" && [ -s "$Z/sounds/groan.wav" ] && grep -q "sounds/groan.wav" "$Z/hooks/panel.tsx" && grep -q "pose = clickAt" "$Z/hooks/panel.tsx" && ! python3 -c "import sys;sys.path.insert(0,\"$Z/bin\");import tzzombie as z;sys.exit(0 if z.visual_state({},\"IDLE\")==\"scratch\" else 1)"'
ok "mascot override env for previews" 'TZ_MASCOT_STATE=alert tz dash --out "$T/a.html" >/dev/null && grep -q "tz-zombie tz-alert" "$T/a.html"'
echo "dash2: pass $pass fail $fail"; rm -rf "$T"; [ $fail = 0 ]
