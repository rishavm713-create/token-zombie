#!/bin/bash
# Full workflow features: bench compare (recorded logs), worktree add/list/remove, report --implemented, pr check. Fake HOME, no network, no paid runs.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; export HOME="$T/home"; export TZ_DEDUPE=0; mkdir -p "$HOME"; pass=0; fail=0
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
tz() { python3 "$Z/bin/tz" "$@"; }
G() { git -c user.email=t@t -c user.name=t "$@"; }
# --- #16 bench compare from recorded logs
mklog() { python3 - "$1" "$2" "$3" <<'PY'
import json,sys
with open(sys.argv[1],'w') as f:
    for i in range(3):
        f.write(json.dumps({"uuid":"u%d"%i,"message":{"id":"m%d"%i,"model":"x","role":"assistant","content":[],"usage":{"input_tokens":int(sys.argv[2]),"output_tokens":int(sys.argv[3]),"cache_read_input_tokens":0,"cache_creation_input_tokens":0}}})+"\n")
PY
}
mklog "$T/base.jsonl" 1000 500; mklog "$T/opt.jsonl" 400 300
o=$(tz bench compare --baseline "$T/base.jsonl" --optimized "$T/opt.jsonl" --both-passed)
ok "bench compare measures net saving" '[[ $o == *"[MEASURED]"* && $o == *"POSITIVE"* ]]'
o=$(tz bench compare --baseline "$T/base.jsonl" --optimized "$T/opt.jsonl")
ok "bench compare refuses claim without quality check" '[[ $o == *"NOT COMPARABLE"* ]]'
# --- repo
git init -q "$T/repo"; cd "$T/repo"; echo x > a.py; G add .; G commit -qm init
# --- #52 worktree
ok "worktree add creates dir+branch" 'tz worktree add feat1 >/dev/null && [ -d "$T/feat1" ] && git branch | grep -q tz/feat1'
ok "worktree list shows it" 'tz worktree list | grep -q feat1'
ok "worktree is a real git worktree" 'git worktree list | grep -q feat1'
ok "worktree remove deletes it" 'tz worktree remove feat1 >/dev/null && [ ! -d "$T/feat1" ] && ! tz worktree list | grep -q feat1'
# --- #54 report
G checkout -qb feat/x; mkdir -p tests; echo 'echo ok' > tests/test_a.sh; echo y > b.py; G add .; G commit -qm "add b and test"
G branch -qm main 2>/dev/null || G branch -M main 2>/dev/null; G checkout -q feat/x 2>/dev/null
mkdir -p handoffs/tasks; tz next add t1 --title "build feature b" >/dev/null 2>&1
o=$(tz report --implemented)
ok "report lists files, tests, commits" '[[ $o == *"IMPLEMENTED"* && $o == *b.py* && $o == *tests/test_a.sh* && $o == *"add b and test"* ]]'
ok "report lists tasks" '[[ $o == *"tasks:"* ]]'
ok "full report keeps old sections" '[[ $(tz report) == *"== IMPLEMENTED"*"== STATUS"* ]]'
# --- #56 pr check
o=$(tz pr check); rc=$?
ok "pr check NOT READY on missing README/changelog/version" '[ $rc -ne 0 ] && [[ $o == *"NOT READY"* && $o == *README* && $o == *changelog* ]]'
echo "# p" > README.md; echo "# log" > CHANGELOG.md; echo '{"name":"p","version":"1.2.3"}' > package.json
printf '#!/bin/bash\necho "pass 1 fail 0"\n' > tests/run_all.sh; G add .; G commit -qm docs
o=$(tz pr check --run-tests); rc=$?
ok "pr check READY on complete project" '[ $rc -eq 0 ] && [[ $o == *"READY for delivery"* && $o == *"1.2.3"* && $o == *"tests passing"* ]]'
echo dirty >> a.py
ok "dirty tree not ready" '! tz pr check >/dev/null && tz pr check | grep -q "clean tree"'
G checkout -q a.py; echo 'key = "AKIAABCDEFGHIJKLMNOP"' > cfg.py; G add .; G commit -qm cfg
o=$(tz pr check)
ok "secret detected, not ready" '[[ $o == *"possible secret in cfg.py"* && $o == *"NOT READY"* ]]'
printf '#!/bin/bash\nexit 1\n' > tests/run_all.sh; git rm -q cfg.py; G commit -qam fail
ok "failing tests not ready" '! tz pr check --run-tests >/dev/null'
ok "tz pr still read-only body" 'h=$(git rev-parse HEAD); tz pr >/dev/null; [ "$h" = "$(git rev-parse HEAD)" ]'
cd /; rm -rf "$T"; echo "pass $pass fail $fail"; [ $fail -eq 0 ]
