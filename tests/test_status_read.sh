#!/bin/bash
# Regression: `tz sup status` renamed a VALID status.json to status.json.corrupt (_r(path, None) checked isinstance(v, NoneType)).
# Also: _r schema checks, tasks.json schema, status numbers from a known transcript, guard diagnostics log. Fake HOME only.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; pass=0; fail=0; mkdir -p "$H/.claude/token-zombie" "$T/proj"
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
tz() { HOME="$H" python3 "$Z/bin/tz" "$@"; }
D="$H/.claude/token-zombie"; BUS="$D/status.json"
py() { HOME="$H" python3 -c "import sys;sys.path.insert(0,'$Z/bin');import tzsup,json,os
$1"; }

# 1. exact bug: valid status.json + `tz sup status` -> printed, kept byte-identical, never quarantined
echo '{"ts": 1, "level": "NORMAL", "ctx_pct": 44, "tokens": {"turns": 10}, "mascot": "HAPPY"}' > "$BUS"; cp "$BUS" "$T/orig"
o=$(tz sup status)
ok "status prints valid file" '[[ $o == *"\"ctx_pct\": 44"* && $o != *"no status yet"* ]]'
ok "valid status.json kept byte-identical" 'cmp -s "$BUS" "$T/orig"'
ok "valid status.json never quarantined" '[ ! -e "$BUS.corrupt" ]'
tz sup status >/dev/null; tz sup status >/dev/null
ok "repeated status runs still keep the file" 'cmp -s "$BUS" "$T/orig" && [ ! -e "$BUS.corrupt" ]'

# 2. missing file: default, nothing created
rm -f "$BUS"; o=$(tz sup status)
ok "missing status: message, no file, no .corrupt" '[[ $o == *"no status yet"* ]] && [ ! -e "$BUS" ] && [ ! -e "$BUS.corrupt" ]'

# 3. malformed JSON: quarantined with evidence kept
printf '{"ts": 1, "lev' > "$BUS"; cp "$BUS" "$T/bad"; o=$(tz sup status)
ok "malformed status: quarantined, evidence kept" '[[ $o == *"no status yet"* ]] && [ ! -e "$BUS" ] && cmp -s "$BUS.corrupt" "$T/bad"'
rm -f "$BUS.corrupt"

# 4. wrong schema (JSON list / string / null): quarantined
for v in '[1, 2]' '"x"' 'null'; do
  echo "$v" > "$BUS"; o=$(tz sup status)
  ok "schema-invalid status ($v) quarantined" '[[ $o == *"no status yet"* ]] && [ -e "$BUS.corrupt" ] && [ ! -e "$BUS" ]'
  rm -f "$BUS.corrupt"
done

# 5. _r unit checks: every default type and the ok= validator
ok "_r: dict default keeps valid dict" 'py "p=\"$T/a.json\";open(p,\"w\").write(\"{\\\"k\\\": 1}\");assert tzsup._r(p,{})=={\"k\":1} and os.path.exists(p) and not os.path.exists(p+\".corrupt\")"'
ok "_r: None default keeps valid dict" 'py "p=\"$T/b.json\";open(p,\"w\").write(\"{\\\"k\\\": 2}\");assert tzsup._r(p,None)=={\"k\":2} and os.path.exists(p) and not os.path.exists(p+\".corrupt\")"'
ok "_r: missing file returns default, no files made" 'py "p=\"$T/none.json\";assert tzsup._r(p,None) is None and tzsup._r(p,{\"x\":1})=={\"x\":1} and not os.path.exists(p+\".corrupt\")"'
ok "_r: validator rejects -> quarantine" 'py "p=\"$T/c.json\";open(p,\"w\").write(\"{}\");assert tzsup._r(p,{},lambda v:\"k\" in v)=={} and os.path.exists(p+\".corrupt\")"'
ok "_r: validator that raises -> quarantine, no crash" 'py "p=\"$T/e.json\";open(p,\"w\").write(\"{}\");assert tzsup._r(p,{},lambda v:v[\"nope\"])=={} and os.path.exists(p+\".corrupt\")"'
ok "_r: unreadable (directory) -> default, no crash" 'mkdir -p "$T/dir.json" && py "assert tzsup._r(\"$T/dir.json\",{})=={}"'

# 6. tasks.json schema
TJ="$D/tasks.json"
echo '{"tasks": [{"id": "t1", "status": "open"}]}' > "$TJ"; cp "$TJ" "$T/tj"
ok "valid tasks.json kept, never quarantined" 'tz sup task >/dev/null && cmp -s "$TJ" "$T/tj" && [ ! -e "$TJ.corrupt" ]'
echo '{"tasks": "oops"}' > "$TJ"
ok "tasks.json wrong schema quarantined, tick does not crash" 'tz sup tick --transcript /nonexistent --cwd "$T/proj" >/dev/null && [ -e "$TJ.corrupt" ]'
rm -f "$TJ" "$TJ.corrupt"

# 7. status numbers from a known transcript (dedupe repeated reply id)
python3 - "$T/known.jsonl" <<'PY'
import json,sys
L=[("m1",1000,0,0,"2026-11-20T10:00:00+00:00"),("m2",1000,99000,0,"2026-11-20T10:01:00+00:00"),("m2",1000,99000,0,"2026-11-20T10:01:00+00:00")]
open(sys.argv[1],'w').write(''.join(json.dumps({"type":"assistant","timestamp":ts,"message":{"id":i,"usage":{"input_tokens":a,"output_tokens":5,"cache_read_input_tokens":b,"cache_creation_input_tokens":c}}})+'\n' for i,a,b,c,ts in L))
PY
rm -f "$BUS"; tz sup tick --transcript "$T/known.jsonl" --cwd "$T/proj" >/dev/null
ok "known transcript: 2 replies (dup id counted once), last 100000, ctx 50% of 200k" 'python3 -c "import json;s=json.load(open(\"$BUS\"));t=s[\"tokens\"];assert (t[\"turns\"],t[\"last\"],t[\"inp\"],t[\"cr\"],s[\"ctx_pct\"])==(2,100000,2000,99000,50),(t,s[\"ctx_pct\"])"'
ok "tick output survives a following status read" 'cp "$BUS" "$T/s2" && tz sup status >/dev/null && cmp -s "$BUS" "$T/s2" && [ ! -e "$BUS.corrupt" ]'
# first-prompt case (live zero explained): log with a user line only, no assistant usage yet -> 0 replies, 0%
echo '{"type":"user","message":{"content":"hi"}}' > "$T/first.jsonl"
tz sup tick --transcript "$T/first.jsonl" --cwd "$T/proj" >/dev/null
ok "no assistant reply yet -> turns 0, ctx 0 (expected, not a bug)" 'python3 -c "import json;s=json.load(open(\"$BUS\"));assert s[\"tokens\"][\"turns\"]==0 and s[\"ctx_pct\"]==0"'

# 8. guard diagnostics: supervisor failure logged locally, no transcript text, hook still exits 0
LOG="$D/errors.log"; rm -f "$LOG"
echo '{"secret":"TOPSECRET-123"}' > "$T/tx.jsonl"
mkdir -p "$T/badbin"; cp "$Z"/bin/*.py "$T/badbin/"; printf 'def on_event(d):\n    raise RuntimeError("boom")\n' > "$T/badbin/tzsup.py"
ev='{"hook_event_name":"Stop","session_id":"s","cwd":"'$T/proj'","transcript_path":"'$T/tx.jsonl'"}'
echo "$ev" | HOME="$H" python3 "$T/badbin/tz-guard.py" >/dev/null 2>&1; rc=$?
ok "guard exits 0 when supervisor raises" '[ $rc = 0 ]'
ok "supervisor error logged with type, event, frames" 'grep -q "supervisor ev=Stop RuntimeError: boom @ tzsup.py:2:on_event" "$LOG"'
ok "log holds no transcript content" '! grep -q TOPSECRET "$LOG"'
echo 'not json' | HOME="$H" python3 "$Z/bin/tz-guard.py" >/dev/null 2>&1; rc=$?
ok "bad stdin: guard exits 0, logs guard error" '[ $rc = 0 ] && grep -q "guard ev=? JSONDecodeError" "$LOG"'
python3 -c "open('$LOG','w').write('x'*70000+'\n')"; echo 'not json' | HOME="$H" python3 "$Z/bin/tz-guard.py" >/dev/null 2>&1
ok "log stays bounded" '[ $(wc -c <"$LOG") -lt 40000 ] && tail -1 "$LOG" | grep -q JSONDecodeError'
rm -f "$LOG"; printf 'def on_event(d):\n    raise ValueError("key sk-ant-abcdefghijklmnopqrstuvwxyz0123 line %%r" %% open(d["transcript_path"]).read())\n' > "$T/badbin/tzsup.py"
echo "$ev" | HOME="$H" python3 "$T/badbin/tz-guard.py" >/dev/null 2>&1
ok "secret-bearing message redacted: no key, no transcript text, type kept" 'grep -q "ValueError: key <redacted> line" "$LOG" && ! grep -q -E "TOPSECRET|sk-ant|abcdefghij" "$LOG"'
rm -f "$LOG"; for e in UserPromptSubmit PreToolUse PostToolUse Stop PreCompact SessionEnd; do
  echo '{"hook_event_name":"'$e'","session_id":"s","cwd":"'$T/proj'","transcript_path":"'$T/known.jsonl'","tool_input":{}}' | HOME="$H" python3 "$Z/bin/tz-guard.py" >/dev/null 2>&1; done
ok "healthy hooks (6 events) write no errors.log" '[ ! -e "$LOG" ]'

# 9. quarantine never overwrites earlier evidence: 3 corrupt events in a row -> 3 distinct files, contents kept
rm -f "$BUS"*; for i in 1 2 3; do printf "bad$i{" > "$BUS"; tz sup status >/dev/null; done
ok "3 corrupt events -> .corrupt, .corrupt.1, .corrupt.2" '[ "$(cat "$BUS.corrupt")" = "bad1{" ] && [ "$(cat "$BUS.corrupt.1")" = "bad2{" ] && [ "$(cat "$BUS.corrupt.2")" = "bad3{" ] && [ ! -e "$BUS" ]'
ok "no placeholder or tmp left behind" '[ $(ls "$D" | grep -c "status.json") = 3 ]'
echo '{"ok": 1}' > "$BUS"; tz sup status >/dev/null
ok "valid file after corrupt ones: kept, no new quarantine" '[ -e "$BUS" ] && [ ! -e "$BUS.corrupt.3" ]'
ok "_quarantine on vanished source leaves no empty claim" 'py "tzsup._quarantine(\"$T/gone.json\");assert not any(f.startswith(\"gone.json\") for f in os.listdir(\"$T\"))"'

# 10. CLI reachable through a symlink (the PATH setup in docs/INSTALL.md)
mkdir -p "$T/pathbin"; ln -s "$Z/bin/tz" "$T/pathbin/tz"
ok "tz works via symlink on PATH" 'HOME="$H" PATH="$T/pathbin:$PATH" command tz sup status >/dev/null 2>&1; [ $? = 0 ]'

rm -rf "$T"; echo "pass $pass fail $fail"; [ $fail = 0 ]
