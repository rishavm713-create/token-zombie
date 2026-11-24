#!/bin/bash
# Repo intelligence + workflow: tz sym (defs + impact), tz exists (find existing impl), near-duplicate task refused, tree-sitter optional with fallback.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; pass=0; fail=0
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
mkdir -p "$T/r/src" "$T/r/tests" "$T/home/.claude" && cd "$T/r"
printf 'def parse_config(p):\n    return p\n\nclass ConfigLoader:\n    pass\n' > src/cfg.py
printf 'from cfg import parse_config\nx = parse_config(1)\n' > src/app.py
printf 'import parse_config\n' > tests/test_cfg.py
printf 'export async function loadUserProfile(id) {\n  return id;\n}\n' > src/user.ts
tz() { HOME="$T/home" python3 "$Z/bin/tz" "$@"; }
o=$(tz sym parse_config); ok "sym: definition file:line" '[[ $o == *"src/cfg.py:1"* ]]'
ok "sym: impact lists users + tests" '[[ $o == *src/app.py* && $o == *"tests among them: tests/test_cfg.py"* ]]'
o=$(tz sym loadUserProfile); ok "sym: ts definition" '[[ $o == *"src/user.ts:1"* ]]'
o=$(tz exists config loader); ok "exists: finds ConfigLoader first" '[[ $(echo "$o" | head -1) == *ConfigLoader* ]]'
o=$(tz exists zebra); ok "exists: nothing similar" '[[ $o == *"nothing similar"* ]]'
n() { HOME="$T/home" python3 "$Z/bin/tznext.py" --cwd "$T/r" "$@"; }
n add a --title "Add login page with OAuth" >/dev/null
o=$(n add b --title "add OAuth login page"); r=$?; ok "near-duplicate task refused" '[[ $o == *"duplicate work? a"* && $r = 1 ]]'
o=$(n add b --title "add OAuth login page" --force); ok "--force overrides" '[[ $o == added ]]'
o=$(n add c --title "Write billing report"); ok "unrelated task added" '[[ $o == added ]]'
printf 'function a(x) { return x + 1; }\nfunction b() { let y = 2; }\n' > f.ts
o=$(tz compress f.ts); ok "no tree-sitter: scanner fallback works" '[[ $o == *"{ ... }"* && $o != *"x + 1"* ]]'
o=$(PYTHONPATH="$Z/tests/fake/ts" tz compress f.ts); ok "tree-sitter (stub) path cuts bodies" '[[ $o == *"function a(x) { ... }"* && $o != *"y = 2"* ]]'
ok "stub tree-sitter really used" '[[ $(cd "$Z/bin" && PYTHONPATH="$Z/tests/fake/ts" python3 -c "import tzcompress as t; print(t.ts_skeleton(\"function a() { 1 }\"))") == *True* ]]'
printf 'function a(x) { return x; } // @@\n' > g.ts
o=$(PYTHONPATH="$Z/tests/fake/ts" tz compress g.ts); ok "tree-sitter parse error falls back" '[[ $o == *"{ ... }"* ]]'
printf 'from cfg import parse_config\ny = parse_config(2)\n' > src/more.py
TP="${TZ_TS_PYTHON:-python3}"
if "$TP" -c "import tree_sitter, tree_sitter_typescript" 2>/dev/null; then
  ok "REAL tree-sitter package cuts TS bodies" '[[ $(cd "$Z/bin" && "$TP" -c "import tzcompress as t; r=t.ts_skeleton(\"export function a(x: number): number { const y = 2; return x + y }\"); print(r)") == *"{ ... }"*True* ]]'
else echo "SKIP: real tree-sitter not installed (set TZ_TS_PYTHON to a python that has tree_sitter + tree_sitter_typescript)"; fi
o=$(tz rank --n 3); ok "rank: most-referenced def first" '[[ $(echo "$o" | head -1) == *"src/cfg.py: parse_config"* ]]'
o=$(tz rank --focus src/user.ts); ok "rank: focus file excluded, still ranks" '[[ $o != *user.ts* && $o == *parse_config* ]]'
cd /; rm -rf "$T"; echo "repo_intel: pass $pass fail $fail"; [ $fail -eq 0 ]
