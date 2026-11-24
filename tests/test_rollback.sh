#!/usr/bin/env bash
# tz rollback: a failed run's changes are undone; passing run keeps changes; pre-existing dirty files and untouched files are safe
cd "$(dirname "$0")/.." || exit 1
R=$PWD; T=$(mktemp -d); export HOME="$T" TZ_DEDUPE=0 GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t; P=0; F=0
ok(){ if eval "$1"; then echo "ok $2"; P=$((P+1)); else echo "FAIL $2"; F=$((F+1)); fi; }
cat > "$T/fake" <<'PY'
#!/usr/bin/env python3
import json, os, sys
p = sys.argv[sys.argv.index('-p') + 1]
if 'Phase: build' in p:
    open('a.txt', 'w').write('changed'); open('new.txt', 'w').write('new')
print(json.dumps({'type': 'assistant', 'message': {'id': 'm1', 'usage': {'input_tokens': 10, 'output_tokens': 1}}}))
print(json.dumps({'type': 'result', 'result': 'done'}))
PY
chmod +x "$T/fake"; export CLAUDE_BIN="$T/fake"
mkdir -p "$T/w"; cd "$T/w" && git init -q && echo orig > a.txt && echo keep > b.txt && git add . && git commit -q -m i && echo pre-dirty >> b.txt
python3 "$R/bin/tz" agent "break it" --test 'false' --rollback >/dev/null 2>&1
ok "[ \"\$(cat a.txt)\" = orig ]" tracked-file-restored
ok "[ ! -e new.txt ]" new-file-removed
ok "grep -q pre-dirty b.txt" preexisting-dirty-kept
python3 "$R/bin/tz" agent "good" --test 'true' --rollback >/dev/null 2>&1
ok "[ \"\$(cat a.txt)\" = changed ] && [ -e new.txt ]" pass-keeps-changes
echo "pass $P fail $F"; [ $F = 0 ]
