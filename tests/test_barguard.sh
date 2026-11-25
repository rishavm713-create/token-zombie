#!/bin/bash
# HARD RULE guards: (1) panel code and its imports never touch Node globals unguarded (the bar vanished once on process.platform),
# (2) tz-start warns when the plugin folder is off main / panel files edited, (3) measured 24h usage sums exactly from a fixture transcript.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; pass=0; fail=0; mkdir -p "$H/.claude"
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }

# (1) static scan of hooks/panel.tsx and every relative import (closure); typeof guards, .process property access, comments and strings are allowed
cat > "$T/scan.py" <<'PY'
import re, sys, os
root = sys.argv[1]; todo = ['panel.tsx']; seen = set(); bad = []
pat = re.compile(r"(?<![.\w$])(process|require|Buffer|__dirname)\b")
while todo:
    f = todo.pop()
    if f in seen: continue
    seen.add(f)
    p = os.path.join(root, f)
    if not os.path.isfile(p): continue
    for n, line in enumerate(open(p, encoding='utf-8'), 1):
        for m in re.finditer(r"from '(\./[\w./-]+)'", line):
            for ext in ('.ts', '.tsx', ''):
                if os.path.isfile(os.path.join(root, m.group(1)[2:] + ext)): todo.append(m.group(1)[2:] + ext); break
        s = re.sub(r"'[^']*'|\"[^\"]*\"|`[^`]*`", "''", line.split('//')[0])
        for g in set(re.findall(r"typeof\s+(process|require|Buffer|__dirname)\b", s)):  # a typeof guard on the line covers its uses there
            s = re.sub(r"\b" + g + r"\b", "", s)
        if pat.search(s): bad.append(f"{f}:{n}: {line.strip()}")
print('SCANNED', ' '.join(sorted(seen)))
print('\n'.join(bad))
PY
o=$(python3 "$T/scan.py" "$Z/hooks")
ok "scan covers panel.tsx, tools.ts, pycmd.ts" '[[ $o == *panel.tsx* && $o == *tools.ts* && $o == *pycmd.ts* ]]'
ok "no unguarded process/require/Buffer/__dirname in panel closure" '[ "$(echo "$o" | sed 1d)" = "" ]'
[ -n "$(echo "$o" | sed 1d)" ] && echo "$o" | sed 1d
# the scan itself must catch the original bug
mkdir -p "$T/bad" && printf "const win = process.platform === 'win32'\n" > "$T/bad/panel.tsx"
cat > "$T/hit.py" <<'PY'
import re, sys, os
pat = re.compile(r"(?<![.\w$])(process|require|Buffer|__dirname)\b")
for line in open(os.path.join(sys.argv[1], 'panel.tsx')):
    s = re.sub(r"typeof\s+(process|require|Buffer|__dirname)\b", "", re.sub(r"'[^']*'|\"[^\"]*\"|`[^`]*`", "''", line.split('//')[0]))
    if pat.search(s): print('HIT')
PY
b=$(python3 "$T/hit.py" "$T/bad")
ok "scan flags the original unguarded process.platform" '[ "$b" = HIT ]'

# (2) tz-start warning: copy of the plugin in a temp git repo
R="$T/plug"; mkdir -p "$R/hooks" "$R/types"; cp -R "$Z/bin" "$R/bin"; echo x > "$R/hooks/a.ts"
git -C "$R" init -q -b main && git -C "$R" add -A && git -C "$R" -c user.email=t@t -c user.name=t commit -qm i
start() { echo '{"session_id":"g'$RANDOM'","source":"startup","cwd":"'"$T"'"}' | HOME="$H" TZ_FRESH_BG=0 python3 "$R/bin/tz-start.py" 2>&1; }
o=$(start); ok "clean main: no TZ WARNING" '[[ $o != *"TZ WARNING"* ]]'
git -C "$R" checkout -q -b feat; o=$(start); ok "non-main branch warns with the branch name" '[[ $o == *"TZ WARNING"* && $o == *"branch feat"* ]]'
git -C "$R" checkout -q main; echo y >> "$R/hooks/a.ts"; o=$(start); ok "uncommitted hooks/ edit warns" '[[ $o == *"TZ WARNING"* && $o == *"uncommitted"* ]]'

# (3) measured usage: fixture sums exactly; dup line, <synthetic> notice and an older-than-24h reply are not counted
mkdir -p "$H/.claude/projects/p"
python3 - "$H/.claude/projects/p/c.jsonl" <<'PY'
import json, sys, time, datetime as d
now = time.time(); iso = lambda s: d.datetime.fromtimestamp(now - s, d.timezone.utc).isoformat()
rows = [('a', 3600, 10, 20, 300, 4000), ('b', 7200, 1, 2, 30, 400), ('c', 90000, 999, 999, 999, 999)]  # c is 25h old
L = [json.dumps({"timestamp": iso(s), "message": {"id": i, "model": "m", "usage": {"input_tokens": a, "output_tokens": b, "cache_read_input_tokens": c, "cache_creation_input_tokens": e}}}) for i, s, a, b, c, e in rows]
L.append(L[0])  # same reply logged twice
L.append(json.dumps({"timestamp": iso(60), "message": {"id": "s", "model": "<synthetic>", "usage": {"input_tokens": 0, "output_tokens": 0}}}))
open(sys.argv[1], 'w').write('\n'.join(L) + '\n')
PY
o=$(HOME="$H" python3 "$Z/bin/tzusage.py" record)
ok "24h MEASURED sums exactly (in 11, out 22, cr 330, cw 4400, 2 replies)" '[[ $o == *"input 11 output 22 cache_read 330 cache_write 4400 (2 replies)"* ]]'
ok "usage.json written, basis measured" 'python3 -c "import json,sys; d=json.load(open(\"$H/.claude/token-zombie/usage.json\")); assert (d[\"inp\"],d[\"out\"],d[\"cr\"],d[\"cw\"],d[\"turns\"],d[\"basis\"])==(11,22,330,4400,2,\"measured\")"'
rm -rf "$T"; echo "pass $pass fail $fail"; [ $fail = 0 ]
