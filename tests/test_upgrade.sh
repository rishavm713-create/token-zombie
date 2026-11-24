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
echo "pass $P fail $F"; [ $F = 0 ]
