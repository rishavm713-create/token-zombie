#!/bin/bash
# v0.1 task continuity tests. Fake HOME + temp git repo; nothing outside the temp dir is touched.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; P="$T/proj"; pass=0; fail=0
mkdir -p "$H/.claude" "$P"
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
hf() { HOME="$H" python3 "$Z/bin/tzhandoff.py" "$@"; }
G="git -C $P -c user.email=t@t -c user.name=t"
$G init -q . && echo a > "$P/a.txt" && echo 'exit 0' > "$P/t.sh" && $G add . && $G commit -qm init
echo b >> "$P/a.txt"; echo new > "$P/n.txt"          # work: 1 edited, 1 new file

o=$(hf handoff --cwd "$P" --task demo --done "edit a" --left "docs" --next "write docs" --test "bash t.sh" --yes --remember "use bash t.sh to test")
ok "handoff md has next action + verified + git" '[[ $o == *"NEXT ACTION: write docs"* && $o == *"verified by test"* && $o == *"2 uncommitted"* ]]'
ok "handoff files written" '[ -f "$P/handoffs/tasks/demo.json" ] && ls "$P"/handoffs/*-tz.md >/dev/null && grep -q "bash t.sh" "$P/handoffs/MASTER.md"'
ok "handoff <= 30 lines" '[ $(wc -l < "$P"/handoffs/*-tz.md) -le 30 ]'
o=$(hf handoff --cwd "$P" --task demo --done x --test "false" --yes); ok "failed test => UNVERIFIED + FAILED" '[[ $o == *UNVERIFIED* && $o == *"tests FAILED"* ]]'
o=$(hf handoff --cwd "$P" --task demo --done x); ok "no test => tests not run, UNVERIFIED" '[[ $o == *"tests not run"* && $o == *UNVERIFIED* ]]'
hf handoff --cwd "$P" --task demo --done "edit a" --next "write docs" --test "bash t.sh" --yes >/dev/null

# new session: clean resume
o=$(hf resume --cwd "$P"); ok "resume clean" '[[ $o == *"CLEAN"* && $o == *"NEXT ACTION: write docs"* ]]'
ok "resume prints memory" '[[ $o == *"use bash t.sh to test"* ]]'
ok "resume small (<=2k tokens ~ 8k chars)" '[ ${#o} -le 8000 ]'
# drift: edit, new commit, test now fails
echo c >> "$P/a.txt"; o=$(hf resume --cwd "$P"); ok "drift: edited file" '[[ $o == *DRIFT* && $o == *"edited since handoff: a.txt"* ]]'
$G add . && $G commit -qm more; o=$(hf resume --cwd "$P"); ok "drift: new commit + committed files" '[[ $o == *"new commits"* && $o == *"no longer changed"* ]]'
echo 'exit 1' > "$P/t.sh"; o=$(hf resume --cwd "$P" --run-test --yes); ok "resume reruns test, flags change" '[[ $o == *"test result changed"* ]]'
ok "resume never modified tree" '[ "$(cat $P/n.txt)" = new ] && [ "$(grep -c . $P/a.txt)" = 3 ]'
# failure handling
o=$(hf resume --cwd "$T/nope" 2>&1); ok "resume missing dir => error" '[[ $o == *"not a directory"* ]]'
mkdir "$T/empty"; o=$(hf resume --cwd "$T/empty"); r=$?; ok "no state => message, exit 1" '[ $r = 1 ] && [[ $o == *"no valid task state"* ]]'
for f in "$P"/handoffs/tasks/*.json; do echo '{bad' > "$f"; done; o=$(hf resume --cwd "$P"); ok "corrupt state => message, no crash" '[[ $o == *"no valid task state"* ]]'
mkdir "$T/ng"; hf handoff --cwd "$T/ng" --task x --next y >/dev/null; o=$(hf resume --cwd "$T/ng"); ok "non-git dir works" '[[ $o == *CLEAN* ]]'
# memory dedupe
hf handoff --cwd "$P" --remember "fact1" --remember "fact1" >/dev/null; ok "memory dedupe" '[ $(grep -c "fact1" "$P/handoffs/MASTER.md") = 1 ]'
# tz-start still reads the handoff dir (back-compat)
o=$(echo "{\"cwd\":\"$P\"}" | HOME="$H" python3 "$Z/bin/tz-start.py"); ok "tz-start injects tz handoff" '[[ $o == *"NEXT ACTION"* ]]'
# task-wrap / checkpoint / DAILY / MASTER lifecycle
W="$T/w"; mkdir -p "$W"; echo 'exit 0' > "$W/t.sh"; git -C "$W" init -q; echo x > "$W/f"
hf handoff --cwd "$W" --task life --next "finish" >/dev/null
echo y >> "$W/f"; o=$(hf checkpoint --cwd "$W"); ok "checkpoint saves, no commands run" '[[ $o == *saved* ]] && grep -q checkpoint "$W/handoffs/DAILY.md"'
o=$(hf resume --cwd "$W"); ok "resume after checkpoint is clean" '[[ $o == *CLEAN* ]]'
o=$(hf task-wrap --cwd "$W" 2>&1); r=$?; ok "wrap without passing test stays open" '[ $r = 1 ] && [[ $o == *"not closed"* ]]'
o=$(hf task-wrap --cwd "$W" --test "false" --yes 2>&1); r=$?; ok "wrap with failing test stays open" '[ $r = 1 ]'
o=$(hf task-wrap --cwd "$W" --test "bash t.sh" --yes --summary "all good" --remember "decision: use json state"); r=$?
ok "wrap with passing test closes, logs DAILY, MASTER, never commits" '[ $r = 0 ] && [[ $o == *"done"* ]] && grep -q "DONE: life - all good" "$W/handoffs/DAILY.md" && grep -q "use json state" "$W/handoffs/MASTER.md" && [ -z "$(git -C $W log --oneline 2>/dev/null)" ]'
o=$(hf task-wrap --cwd "$W" --force --task x 2>&1); ok "force => done-unverified" '[[ $o == *done-unverified* ]]'
mkdir "$T/nw"; hf task-wrap --cwd "$T/nw" >/dev/null 2>&1; ok "wrap with no state => exit 1" '[ $? = 1 ]'
hf checkpoint --cwd "$T/nw" >/dev/null; ok "checkpoint with no state => exit 1" '[ $? = 1 ]'
echo '{"cwd":"'$W'","session_id":"zz","trigger":"auto"}' | HOME="$H" python3 "$Z/bin/tz-compact.py"; ok "compact hook refreshes checkpoint" 'grep -c checkpoint "$W/handoffs/DAILY.md" | grep -qv "^1$"'
# consent gate for user-supplied test commands
C="$T/c"; mkdir -p "$C"; git -C "$C" init -q
o=$(hf handoff --cwd "$C" --task g --test "touch $T/RAN" </dev/null 2>&1); r=$?
ok "handoff --test without --yes refused, command NOT run" '[ $r = 2 ] && [[ $o == *"without consent"* ]] && [ ! -e "$T/RAN" ]'
o=$(hf task-wrap --cwd "$C" --test "touch $T/RAN" </dev/null 2>&1); r=$?; ok "task-wrap --test without --yes refused" '[ $r = 2 ] && [ ! -e "$T/RAN" ]'
hf handoff --cwd "$C" --task g --test "touch $T/RAN" --yes >/dev/null; ok "--yes runs it" '[ -e "$T/RAN" ]'
rm -f "$T/RAN"; o=$(hf resume --cwd "$C" --run-test </dev/null 2>&1); r=$?; ok "resume --run-test without --yes refused" '[ $r = 2 ] && [ ! -e "$T/RAN" ]'
o=$(hf handoff --cwd "$C" --task g --next n </dev/null); ok "no --test needs no consent" '[[ $o == *"NEXT ACTION"* ]]'
echo "continuity: pass $pass fail $fail"; [ $fail = 0 ]
