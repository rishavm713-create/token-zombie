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
echo "pass $P fail $F"; [ $F = 0 ]
