#!/bin/bash
# tz worktree add/claim/remove: one worktree per task, overlapping file refused, remove releases, no git -> ownership only.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; pass=0; fail=0
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
export HOME="$T/home"; S="$HOME/.claude/token-zombie/worktrees.json"
git init -q "$T/repo" && cd "$T/repo" && echo x > a.py && echo y > b.py && git add . && git -c user.email=t@t -c user.name=t commit -qm init
tw() { python3 "$Z/bin/tz" worktree "$@"; }
ok "task A created with worktree" 'tw add "task A" --files a.py >/dev/null && [ -d "$T/task-a" ] && git branch | grep -q tz/task-a'
ok "task B on other file ok" 'tw add "task B" --files b.py >/dev/null && [ -d "$T/task-b" ]'
ok "B claiming a.py refused" '! tw claim "task B" a.py | grep -q owns && tw claim "task B" a.py | grep -q "a.py owned by task-a"'
ok "new task C overlapping refused, no worktree" '! tw add "task C" --files ./a.py >/dev/null && [ ! -d "$T/task-c" ]'
ok "map has A and B only" 'python3 -c "import json;m=json.load(open(\"$S\"));assert sorted(m)==[\"task-a\",\"task-b\"],m"'
ok "remove A releases a.py" 'tw remove "task A" | grep -q "released 1" && [ ! -d "$T/task-a" ] && tw claim "task B" a.py | grep -q "owns 2"'
ok "dirty worktree kept without --force" 'echo z >> "$T/task-b/b.py"; ! tw remove "task B" >/dev/null && [ -d "$T/task-b" ] && tw remove "task B" --force >/dev/null && [ ! -d "$T/task-b" ]'
ok "no git: ownership only, overlap still refused" 'PATH=/nonexistent /usr/bin/python3 "$Z/bin/tz" worktree add "task D" --files c.py | grep -q "git missing" && ! PATH=/nonexistent /usr/bin/python3 "$Z/bin/tz" worktree add "task E" --files c.py >/dev/null'
ok "advice form unchanged" 'tw "some task" | grep -q "git worktree add ../some-task"'
rm -rf "$T"; echo "worktree_own: pass $pass fail $fail"; [ $fail -eq 0 ]
