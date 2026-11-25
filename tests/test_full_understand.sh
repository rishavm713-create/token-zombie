#!/bin/bash
# understand group: tz map (folders + import edges), tz find (notes, ranked fallback, code), tz state (facts surfaced + injected at start). Fake HOME, no network.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; P="$T/proj"; pass=0; fail=0
mkdir -p "$H" "$P/src/lib" "$P/handoffs"; export TZ_DEDUPE=0
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
tz() { HOME="$H" python3 "$Z/bin/tz" "$@"; }
printf 'import b\nfrom lib import c\ndef a(): pass\n' > "$P/src/a.py"; echo 'def b(): pass' > "$P/src/b.py"; echo 'def c(): pass' > "$P/src/lib/c.py"
printf "import {x} from './util';\nexport function y(){}\n" > "$P/src/main.js"; echo 'export const x = () => 1' > "$P/src/util.js"
echo 'def invoice_totals(): pass' > "$P/src/billing.py"
M=$(tz map "$P" 2>/dev/null)
ok "map: py defs kept" '[[ $M == *"src/a.py: a"* ]]'
ok "map: py import edges" '[[ $M == *"src/a.py -> src/b.py src/lib/c.py"* ]]'
ok "map: js import edge" '[[ $M == *"src/main.js -> src/util.js"* ]]'
ok "map: folder structure" '[[ $M == *"src/lib/: 1"* ]]'
printf '# Decision log\n- chose sqlite for the cache layer\n- retries use exponential backoff\n' > "$P/handoffs/2026-01-01.md"
cd "$P"
o=$(tz find sqlite cache 2>&1); ok "find: all-words hit" '[[ $o == *"sqlite for the cache"* ]]'
o=$(tz find sqlite backoff invoice 2>&1); ok "find: ranked fallback surfaces partial note hits" '[[ $o == *"~1/3"* && $o == *"sqlite"* ]]'
ok "find: fallback names code file" '[[ $o == *"code: src/billing.py"* ]]'
o=$(tz state 2>&1); ok "state: prints known facts" '[[ $o == *"## Master"* && $o == *"## Current work"* ]]'
ok "state: STATE.md written" '[ -f handoffs/STATE.md ]'
s=$(echo "{\"session_id\":\"s1\",\"cwd\":\"$P\",\"source\":\"startup\",\"hook_event_name\":\"SessionStart\"}" | HOME="$H" TZ_FRESH_BG=0 python3 "$Z/bin/tz-start.py")
ok "start hook injects STATE.md facts" '[[ $s == *"known facts"* && $s == *"Current work"* ]]'
echo "pass $pass fail $fail"; rm -rf "$T"
