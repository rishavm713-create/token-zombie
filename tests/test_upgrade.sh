#!/bin/bash
# upgrade branch: long pasted text is not split into tasks; handoff verify --run-test; bench harbor prints commands
R="$(cd "$(dirname "$0")/.." && pwd)"; P=0; F=0
ck(){ if eval "$2"; then P=$((P+1)); else F=$((F+1)); echo "FAIL $1"; fi; }
long=$(python3 -c "print(('first idea; then second idea is here also third idea goes on\n')*40)")
ck "long paste not split" '[ -z "$(python3 -c "import sys;sys.path.insert(0,\"$R/bin\");import tzsplit;print(tzsplit.detect(sys.argv[1]))" "$long" | grep -v "^\[\]$")" ]'
ck "short list split" 'python3 -c "import sys;sys.path.insert(0,\"$R/bin\");import tzsplit;sys.exit(0 if len(tzsplit.detect(\"1. fix login bug\n2. add export button\"))==2 else 1)"'
ck "detect_test finds suite" '[ "$(python3 -c "import sys;sys.path.insert(0,\"$R/bin\");import tzintegrity;print(tzintegrity.detect_test(\"$R\"))")" = "bash tests/run_all.sh" ]'
T=$(mktemp -d); ck "detect_test empty dir" '[ -z "$(python3 -c "import sys;sys.path.insert(0,\"$R/bin\");import tzintegrity;print(tzintegrity.detect_test(\"$T\"))")" ]'
ck "bench harbor prints or explains" 'python3 "$R/bin/tz" bench harbor 2>&1 | grep -q "harbor"'
ck "69 features" '[ "$(python3 -c "import json;print(len(json.load(open(\"$R/bin/tzfeatures.json\"))))")" = 69 ]'
HELP=$(python3 "$R/bin/tz" help)
ck "every DONE/PARTIAL row names a real tz command" 'python3 - "$R" "$HELP" <<PY
import json,sys,re
rows=json.load(open(sys.argv[1]+"/bin/tzfeatures.json")); h=sys.argv[2]
bad=[r[0] for r in rows if r[3]!="M" and not re.search(r"^\s*"+re.escape(r[4].rstrip("*").split()[0]),h,re.M)]
sys.exit(1 if bad else 0)
PY'
ck "tz features prints board" 'python3 "$R/bin/tz" features | grep -q "69 features"'
ck "tz progress runs" 'cd "$R" && python3 bin/tz progress | grep -q "progress"'
ck "tz standards runs" 'python3 "$R/bin/tz" standards "$R" | grep -q "indent"'
ck "tz pr is read-only" 'cd "$R" && h=$(git rev-parse HEAD) && python3 bin/tz pr >/dev/null && [ "$h" = "$(git rev-parse HEAD)" ]'
ck "tz2: reuse/gaps/api/dbschema/contract/coord/stack exist" 'for c in reuse gaps missing contract api dbschema coord stack; do python3 "$R/bin/tz" help | grep -q "$c" || exit 1; done'
ck "tz2: reuse refuses unlicensed (STUDY) logic" 'python3 -c "import sys;sys.path.insert(0,\"$R/bin\");import tzbuild as t;assert t.verdict(\"none\")[0]==\"STUDY\" and t.verdict(\"mit\")[0]==\"REUSE\" and t.verdict(\"gpl-3.0\")[0]==\"CHECK\""'
ck "tz2: api finds a flask route" 'd=$(mktemp -d); printf "@app.get(\"/a\")\ndef a(): pass\n" > $d/x.py; python3 "$R/bin/tz" api $d | grep -q "/a"'
ck "tz2: safe blocks reset --hard, allows ls" '! python3 "$R/bin/tz" safe "git reset --hard" >/dev/null && python3 "$R/bin/tz" safe "ls -la" | grep -q ok'
ck "tz2: safe allows force-with-lease and echo text" 'python3 "$R/bin/tz" safe "git push --force-with-lease" | grep -q ok && python3 "$R/bin/tz" safe "echo rm -rf /" | grep -q ok'
ck "tz2: impact finds a referencing file" 'python3 "$R/bin/tz" impact tzops | grep -q "bin/tz"'
ck "tz2: run lists 10 stages, dry by default" '[ "$(python3 "$R/bin/tz" run "x" | grep -c "^ *[0-9]")" = 10 ]'
ck "tz2: guard hook denies git reset --hard, passes ls" 'echo "{\"hook_event_name\":\"PreToolUse\",\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"git reset --hard\"},\"session_id\":\"t1\",\"cwd\":\"/tmp\"}" | python3 "$R/bin/tz-guard.py" | grep -q deny && ! (echo "{\"hook_event_name\":\"PreToolUse\",\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"ls\"},\"session_id\":\"t1\",\"cwd\":\"/tmp\"}" | python3 "$R/bin/tz-guard.py" | grep -q deny)'
ck "tz2: scaffold writes a SaaS skeleton whose own tests pass (0 tokens)" 'D=$(mktemp -d); python3 "$R/bin/tz" scaffold "track invoices" --dir $D/x --fields client,amount >/dev/null && cd $D/x && python3 -W ignore -m unittest -q 2>&1 | grep -q "^OK"'
ck "tz3: hw prints memory and a tier" 'python3 "$R/bin/tz" hw | grep -q "ESTIMATE"'
ck "tz3: cli worker add, test, run (no shell, prompt passed as one arg)" 'export TZ_WORKERS_DIR=$(mktemp -d); python3 "$R/bin/tz" worker add echo1 --kind cli --cmd "python3 -c \"import sys;print(sys.argv[1])\" {prompt}" >/dev/null && [ "$(python3 "$R/bin/tz" worker run echo1 "a; b c")" = "a; b c" ] && python3 "$R/bin/tz" worker test echo1 | grep -q "^OK"'
ck "tz3: http worker talks OpenAI-style to a local server" 'export TZ_WORKERS_DIR=$(mktemp -d); python3 - "$R" <<PY
import http.server, threading, json, subprocess, sys
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(s):
        s.rfile.read(int(s.headers["Content-Length"])); b=json.dumps({"choices":[{"message":{"content":"OK from fake"}}]}).encode()
        s.send_response(200); s.send_header("Content-Length",str(len(b))); s.end_headers(); s.wfile.write(b)
    def log_message(*a): pass
v=http.server.HTTPServer(("127.0.0.1",0),H); threading.Thread(target=v.serve_forever,daemon=True).start()
tz=[sys.executable, sys.argv[1]+"/bin/tz"]
subprocess.run(tz+["worker","add","loc","--kind","http","--url","http://127.0.0.1:%d/v1"%v.server_port],check=True,capture_output=True)
o=subprocess.run(tz+["worker","run","loc","hi"],capture_output=True,text=True).stdout
sys.exit(0 if "OK from fake" in o else 1)
PY'
ck "tz3: unknown worker fails cleanly" 'export TZ_WORKERS_DIR=$(mktemp -d); ! python3 "$R/bin/tz" worker run nope hi 2>/dev/null'
ck "tz3: tzagent runs through a cli worker (EST tokens) and offline fails cleanly" 'd=$(mktemp -d); cd $d; git init -q; export TZ_WORKERS_DIR=$d/w TZ_DEDUPE=0; python3 $R/bin/tzworkers.py worker add echo --kind cli --cmd "python3 -c \"print(1)\" {prompt}" >/dev/null; python3 $R/bin/tzagent.py "make a file" --worker echo 2>&1 | grep -q "EST chars/4" && python3 $R/bin/tzagent.py "x" --worker offline 2>&1 | grep -q "error"'
ck "tz3: gate catches seeded bad inputs (leaked key, out-of-scope file, failing test) and passes a clean change" 'd=$(mktemp -d); cd $d; git init -q; echo a>a.py; git add .; git -c user.email=t@t -c user.name=t commit -qm i; echo "x=1" >a.py; python3 $R/bin/tzgate.py gate t --files a.py --test true | grep -q "status: TESTED" && echo "k=\"AKIA1234567890ABCDEF\"" >>a.py && ! python3 $R/bin/tzgate.py gate t | grep -q "status: TESTED" && git checkout -q a.py && echo y>b.py && python3 $R/bin/tzgate.py gate t --files a.py | grep -q "outside task scope" && python3 $R/bin/tzgate.py gate t --test false | grep -q "tests.*FAIL"'
ck "tz3: tzagent --gate repairs at most 2 rounds then stops" 'd=$(mktemp -d); cd $d; git init -q; echo a>a; git add .; git -c user.email=t@t -c user.name=t commit -qm i; export TZ_WORKERS_DIR=$d.w TZ_DEDUPE=0; python3 $R/bin/tzworkers.py worker add echo --kind cli --cmd "python3 -c \"print(1)\" {prompt}" >/dev/null; python3 $R/bin/tzagent.py "t" --worker echo --gate > $d.out 2>&1; [ "$(grep -c "^debug" $d.out)" = 2 ] && grep -q "^gate .*fail" $d.out'
echo "pass $P fail $F"; [ $F = 0 ]
