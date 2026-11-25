#!/bin/bash
# Quality group: standards --check (#31/#32), rework --tests (#36), security code scan (#39), next results (#64). Fake HOME, no network.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; export HOME="$T/home"; mkdir -p "$HOME"; export TZ_DEDUPE=0; pass=0; fail=0
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
tz() { python3 "$Z/bin/tz" "$@"; }
P="$T/proj"; mkdir -p "$P/src/models" "$P/src/services" "$P/tests"
printf 'def get_a():\n    return "x"\n\ndef get_b():\n    return "y"\n' > "$P/src/services/ok_one.py"
printf 'def get_c():\n    return "x"\n' > "$P/src/services/ok_two.py"
printf 'from services.ok_one import get_a\ndef make_thing():\n  return "a"\n' > "$P/src/models/user_model.py"
printf 'def doThing():\n    return "a"\n' > "$P/src/services/doThing.py"
printf 'def m():\n    pass\n' > "$P/loose.py"
printf 'def test_y():\n    pass\n' > "$P/tests/test_ok.py"
printf 'def test_x():\n    pass\n' > "$P/src/test_misplaced.py"
O=$(tz standards --check "$P"); 
ok "standards: indent violation per file" '[[ $O == *"src/models/user_model.py: indent"* ]]'
ok "standards: naming violation (file+function)" '[[ $O == *"doThing.py: naming: file name is camel"* && $O == *"function doThing is camel"* ]]'
ok "standards: layer violation (#32)" '[[ $O == *"layer violation"* && $O == *"user_model.py"* ]]'
ok "standards: root file vs src layout (#32)" '[[ $O == *"loose.py: architecture: source file at project root"* ]]'
ok "standards: misplaced test file (#32)" '[[ $O == *"src/test_misplaced.py: architecture: test file outside tests/"* ]]'
ok "standards: clean file not flagged" '[[ $O != *"ok_one.py:"* ]]'
ok "standards: violations -> exit 1" '! tz standards --check "$P" >/dev/null'
ok "standards: plain still works" 'tz standards "$P" | grep -q "indent: 4-space"'
# rework --tests
R="$T/rw"; mkdir -p "$R"; printf '#!/bin/bash\necho "FAIL: test_alpha"\necho "pass 3 fail 1"\nexit 1\n' > "$R/t.sh"
O=$(tz rework --tests "$R" --cmd "bash t.sh"); rc=$?
ok "rework --tests: reports failure + name" '[ $rc = 1 ] && [[ $O == *FAILURES* && $O == *"failing: test_alpha"* ]]'
O=$(tz rework --tests "$R" --cmd "true"); ok "rework --tests: passing run" '[ $? = 0 ] && [[ $O == *"all passed"* ]]'
printf 'FAILED tests/test_x.py::test_a - assert 1\n2 failed, 5 passed\nTraceback (most recent call last):\n' > "$T/log.txt"
O=$(tz rework --tests --log "$T/log.txt"); ok "rework --tests: parses saved log" '[[ $O == *"2 failed"* && $O == *"tests/test_x.py::test_a"* ]]'
# security
S="$T/sec"; mkdir -p "$S"; printf 'import os\nKEY="AKIAIOSFODNN7EXAMPLE"\neval(input())\nos.chmod("f",0o777)\n' > "$S/a.py"
O=$(tz security "$S"); rc=$?
ok "security: hardcoded secret -> RED with file:line" '[ $rc = 1 ] && [[ $O == RED* && $O == *"a.py:2: hardcoded secret"* ]]'
ok "security: eval + chmod 777 flagged" '[[ $O == *"a.py:3: dangerous call"* && $O == *"a.py:4: risky permission"* ]]'
S2="$T/sec2"; mkdir -p "$S2"; printf 'x = 1\n' > "$S2/b.py"; ok "security: clean dir GREEN" 'tz security "$S2" | grep -q "^GREEN"'
S3="$T/sec3"; mkdir -p "$S3"; printf 'import subprocess\nsubprocess.run(c, shell=True)\n' > "$S3/c.py"; ok "security: shell=True -> YELLOW" 'tz security "$S3" | grep -q "^YELLOW"'
# next results
N="$T/nx"; mkdir -p "$N"
tz next add T-1 --title "first" --cwd "$N" >/dev/null; tz next add T-2 --title "second" --cwd "$N" >/dev/null
printf '#!/bin/bash\necho "pass 4 fail 0"\n' > "$N/ok.sh"; printf '#!/bin/bash\necho "pass 1 fail 2"\nexit 1\n' > "$N/bad.sh"
tz next start T-1 --cwd "$N" >/dev/null; tz next done T-1 --test "bash ok.sh" --yes --cwd "$N" >/dev/null
tz next start T-2 --cwd "$N" >/dev/null; tz next done T-2 --test "bash bad.sh" --yes --cwd "$N" >/dev/null
O=$(cd "$N" && tz next results --cwd "$N")
ok "next results: per-task pass/fail counts" '[[ $O == *"PASS T-1"*"pass 4 fail 0"* && $O == *"FAIL T-2"*"pass 1 fail 2"* ]]'
ok "next results: totals" '[[ $O == *"TOTAL pass 5 fail 2"* ]]'
ok "next list shows TESTS line" 'tz next list --cwd "$N" | grep -q "^TESTS: pass 5 fail 2"'
echo "pass $pass fail $fail"; [ $fail = 0 ]
