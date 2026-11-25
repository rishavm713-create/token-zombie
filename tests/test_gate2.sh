#!/usr/bin/env bash
# Phase 3 hardening: public-API change detection, tests-actually-ran, regression link, project lint/type/audit detection, resume of killed agent runs.
cd "$(dirname "$0")/.." || exit 1
R=$PWD; T=$(mktemp -d); export HOME="$T/home" TZ_DEDUPE=0; mkdir -p "$HOME"; P=0; F=0
ok(){ if eval "$1"; then echo "ok $2"; P=$((P+1)); else echo "FAIL $2"; F=$((F+1)); fi; }
g(){ python3 "$R/bin/tzgate.py" gate "$@"; }
repo(){ d=$(mktemp -d -p "$T"); cd "$d"; git init -q; printf 'def add(a, b):\n    return a + b\n\ndef _helper(x):\n    return x\n' > calc.py
  printf 'import unittest\nfrom calc import add\nclass T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(1, 2), 3)\nif __name__ == "__main__":\n    unittest.main()\n' > test_calc.py
  git add .; git -c user.email=t@t -c user.name=t commit -qm i; }
UT='python3 -m unittest -q'
# --- the regression the task asks for: a worker changes add(a, b) to add(*args); the existing test still passes; the gate must catch it
repo
printf 'def add(*args):\n    return sum(args)\n\ndef _helper(x):\n    return x\n' > calc.py
$UT >/dev/null 2>&1; ok "[ $? = 0 ]" "drift fixture: the existing test still PASSES after add(a,b) -> add(*args)"
O=$(g t --files calc.py --test "$UT"); ok "echo \"\$O\" | grep -q 'api .*FAIL.*positional parameters renamed' && echo \"\$O\" | grep -q 'status: GENERATED'" "gate catches the silent interface change and refuses TESTED"
g t --files calc.py --test "$UT" >/dev/null; ok "[ $? = 1 ]" "gate exits non-zero on API drift"
O=$(g t --files calc.py --test "$UT" --allow-api-change); ok "echo \"\$O\" | grep -q 'status: TESTED'" "--allow-api-change records intent and passes"
# --- through the agent loop with a worker that always drifts: bounded repairs, never green
repo; export TZ_WORKERS_DIR=$T/w
cat > $T/drift.py <<'PY'
open('calc.py','w').write('def add(*args):\n    return sum(args)\n')
print('done')
PY
python3 "$R/bin/tzworkers.py" worker add drift --kind cli --cmd "python3 $T/drift.py {prompt}" >/dev/null
python3 "$R/bin/tzagent.py" "fix add" --worker drift --test "$UT" --gate > $T/drift.out 2>&1
ok "[ \$(grep -c '^debug' $T/drift.out) = 2 ] && grep -q '^gate .*fail' $T/drift.out && ! grep -q 'TESTED' $T/drift.out && g t --files calc.py --test '$UT' | grep -q 'api .*FAIL'" "agent --gate with a drifting worker: 2 repairs, then stops red, api is the failing check"
# --- compatible and incompatible changes
repo; printf 'def add(a, b, c=0):\n    return a + b + c\n\ndef _helper(y):\n    return y\n' > calc.py
ok "g t --files calc.py --test '$UT' | grep -q 'status: TESTED'" "adding an optional parameter and renaming a private param is compatible"
repo; printf 'def plus(a, b):\n    return a + b\n' > calc.py; printf 'import unittest\nfrom calc import plus\nclass T(unittest.TestCase):\n    def test(self):\n        self.assertEqual(plus(1, 2), 3)\n' > test_calc.py
ok "g t --test '$UT' | grep -q 'removed public add'" "removing a public function is caught"
repo; printf 'def add(b, a):\n    return a + b\n' > calc.py
ok "g t --test true | grep -q 'api .*FAIL'" "reordering parameters is caught"
repo; printf 'def add(a, b, c):\n    return a + b + c\n' > calc.py
ok "g t --test true | grep -q 'new required parameter c'" "a new required parameter is caught"
repo; printf 'class K:\n    def run(self, a, b=1):\n        return a\n' > k.py; git add .; git -c user.email=t@t -c user.name=t commit -qm k; printf 'class K:\n    def run(self, a, b):\n        return a\n' > k.py
ok "g t --test true | grep -q 'K.run: default removed for b'" "removing a method default is caught"
# --- exit code is not evidence
repo; echo '# x' >> calc.py
ok "g t --test 'echo Ran 0 tests; exit 0' | grep -q 'tests .*FAIL.*executed no tests'" "test command exiting 0 with zero tests executed fails"
ok "g t --test '$UT' | grep -q 'status: TESTED'" "a real passing test run is TESTED"
printf 'def sub(a, b):\n    return a - b\n' > util.py; git add -N util.py
O=$(g t --test "$UT"); ok "echo \"\$O\" | grep -q 'regression.*FAIL.*util.py' && echo \"\$O\" | grep -q 'status: IMPLEMENTED'" "changed code no test mentions: not TESTED (regression link)"
printf 'from util import sub\nassert sub(3, 1) == 2\n' >> test_calc.py
ok "g t --test '$UT' | grep -q 'regression.*ok'" "same change with a test that references it passes the link"
# --- syntax
repo; printf 'def add(a, b)\n    return a\n' > calc.py
ok "g t | grep -q 'syntax .*FAIL'" "syntax error in a changed file is caught without any tool installed"
# --- project-configured lint / type / audit (stub binaries; real ruff/mypy/pip-audit are not required to run this suite)
S=$T/stub; mkdir -p $S
printf '#!/bin/sh\necho "E501 line too long"; exit 1\n' > $S/ruff; printf '#!/bin/sh\nexit 0\n' > $S/mypy
printf '#!/bin/sh\necho "Connection error: ENOTFOUND pypi.org"; exit 1\n' > $S/pip-audit; chmod +x $S/*
NOTOOLS="/usr/bin:/bin"
case "$(uname -s)" in MINGW*|MSYS*)  # cmd.exe runs only PATHEXT files; python and git live outside /usr/bin
  printf '@echo E501 line too long\r\n@exit /b 1\r\n' > $S/ruff.cmd; printf '@exit /b 0\r\n' > $S/mypy.cmd
  printf '@echo Connection error: ENOTFOUND pypi.org\r\n@exit /b 1\r\n' > $S/pip-audit.cmd
  NOTOOLS="$(dirname "$(command -v python3)"):$(dirname "$(command -v git)"):$NOTOOLS";; esac
repo; echo '# x' >> calc.py; printf '[lint]\n' > ruff.toml; printf '[mypy]\n' > mypy.ini; echo flask >requirements.txt
O=$(PATH="$S:$PATH" g t --test "$UT")
ok "echo \"\$O\" | grep -q 'lint .*FAIL.*ruff check' && echo \"\$O\" | grep -q 'types .*ok' && echo \"\$O\" | grep -q 'audit .*skip.*needs network'" "configured ruff fails the gate, mypy passes, offline pip-audit is reported skipped (not passed)"
O=$(PATH="$NOTOOLS" g t --test "$UT"); ok "echo \"\$O\" | grep -q 'lint .*skip.*not installed'" "configured but uninstalled tool is skipped and said so"
repo; echo '# x' >> calc.py; O=$(PATH="$S:$PATH" g t --test "$UT"); ok "! echo \"\$O\" | grep -qE '^(lint|types|audit)'" "no config means no lint/type/audit check is invented"
# --- resume of a killed agent run
repo; export TZ_WORKERS_DIR=$T/w2; L=$T/calls.log; : > $L
cat > $T/fake <<'PY'
#!/usr/bin/env python3
import json, os, signal, sys
p = sys.argv[sys.argv.index('-p') + 1]; L = os.environ['FAKE_LOG']
ph = 'build' if 'Phase: build' in p else 'plan' if 'Phase: plan' in p else 'other'
open(L, 'a').write(ph + (' RESUMED' if 'RESUMED' in p else '') + '\n')
if ph == 'build' and not os.path.exists(L + '.killed'):
    open(L + '.killed', 'w').write('1'); os.kill(os.getppid(), getattr(signal, 'SIGKILL', signal.SIGTERM)); sys.exit(1)
if ph == 'build': open('out.txt', 'w').write('good')
print(json.dumps({'type': 'assistant', 'message': {'id': 'm1', 'usage': {'input_tokens': 100, 'output_tokens': 1}}}))
print(json.dumps({'type': 'result', 'result': 'done'}))
PY
chmod +x $T/fake; export CLAUDE_BIN=$T/fake FAKE_LOG=$L
python3 "$R/bin/tz" agent "make out" --test 'grep -q good out.txt' >/dev/null 2>&1; K=$?
ok "[ $K != 0 ] && [ \$(grep -c plan $L) = 1 ] && [ \$(grep -c build $L) = 1 ]" "run is killed during build (SIGKILL), plan already done"
ok "grep -q '\"state\": \"running\"' $HOME/.claude/token-zombie/agent/*.json" "killed run left a running checkpoint"
O=$(python3 "$R/bin/tz" agent --resume last 2>&1); ok "echo \"\$O\" | grep -q 'resumed' && [ \$(grep -c '^plan' $L) = 1 ] && grep -q 'build RESUMED' $L && [ -f out.txt ]" "resume skips the finished plan phase, re-runs build with a resume note, completes"
ok "grep -q '\"state\": \"done\"' $HOME/.claude/token-zombie/agent/*.json" "completed resume marks the run done"
ok "python3 \"$R/bin/tz\" agent --resume last 2>&1 | grep -q 'already finished'" "resuming a finished run is a no-op"
ok "! python3 \"$R/bin/tz\" agent --resume nope-123 2>/dev/null" "resuming an unknown run fails cleanly"
echo "pass $P fail $F"; [ $F = 0 ]
