#!/bin/bash
# Publish-readiness checks: required files, hygiene scrub, README vs manifests. Read-only.
Z="$(cd "$(dirname "$0")/.." && pwd)"; pass=0; fail=0; cd "$Z"
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
for f in README.md LICENSE .github/CONTRIBUTING.md .github/SECURITY.md CHANGELOG.md docs/COMPAT.md .github/ISSUE_TEMPLATE/bug_report.md .github/ISSUE_TEMPLATE/feature_request.md .github/ISSUE_TEMPLATE/config.yml .github/workflows/ci.yml; do
  ok "exists $f" '[ -s "$f" ]'; done
ok "LICENSE is MIT" 'grep -q "^MIT License" LICENSE && grep -q "Permission is hereby granted" LICENSE'
ok "CHANGELOG has 0.3.0" 'grep -q "v0.3.0" CHANGELOG.md'
ok "COMPAT says EXPERIMENTAL" 'grep -q EXPERIMENTAL docs/COMPAT.md'
ok "ci runs tests/run_all.sh" 'grep -q "bash tests/run_all.sh" .github/workflows/ci.yml'
ok "ci covers ubuntu + macos, checkout@v4, contents: read" 'grep -q ubuntu-latest .github/workflows/ci.yml && grep -q macos-latest .github/workflows/ci.yml && grep -q "actions/checkout@v4" .github/workflows/ci.yml && grep -q "contents: read" .github/workflows/ci.yml'
# tracked + untracked-not-ignored files
FILES=$(git ls-files --cached --others --exclude-standard 2>/dev/null)
ok "file list non-empty" '[ -n "$FILES" ]'
ok "no .log files" '! echo "$FILES" | grep -q "\.log$"'
SELF=tests/test_repo.sh; TXT=$(echo "$FILES" | grep -v "^$SELF$" | grep -v '\.png$')
scan() { echo "$TXT" | while read -r f; do [ -f "$f" ] && grep -IlE "$1" "$f"; done; }
ok "no /Users/ paths" '[ -z "$(scan "/Users/")" ]'
ok "no /home/<name> paths" '[ -z "$(scan "/home/[a-z]")" ]'
ok "no rishavskillverse" '[ -z "$(scan "rishavskillverse")" ]'
ok "no private keys" '[ -z "$(scan "BEGIN .*PRIVATE KEY")" ]'
# test_status_read.sh holds a synthetic fake key to test log redaction; allowed there only
ok "no gho_/ghp_/sk-ant- tokens" '[ -z "$(scan "gho_[A-Za-z0-9]|ghp_[A-Za-z0-9]|sk-ant-[A-Za-z0-9]" | grep -vx tests/test_status_read.sh)" ]'
# README vs manifests
ok "README install line matches manifests" 'python3 - <<PY
import json,re
p=json.load(open(".claude-plugin/plugin.json")); m=json.load(open(".claude-plugin/marketplace.json")); r=open("README.md").read()
assert p["name"]==m["name"]==m["plugins"][0]["name"]
assert "claude plugin marketplace add rishavm713-create/%s" % m["name"] in r
assert "claude plugin install %s@%s" % (p["name"],m["name"]) in r
PY'
ok "plugin.json license MIT" 'python3 -c "import json;assert json.load(open(\".claude-plugin/plugin.json\"))[\"license\"]==\"MIT\""'
ok "README images exist" 'python3 - <<PY
import re,os
r=open("README.md").read(); imgs=re.findall(r"(?:\]\(|src=\")(docs/img/[^)\"]+\.(?:png|svg))",r)
assert imgs and all(os.path.isfile(i) for i in imgs),imgs
PY'
echo "pass $pass fail $fail"; [ $fail = 0 ]
