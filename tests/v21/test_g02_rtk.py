# rtk per-command filters (bin/tzrtk.py). Parity inputs adapted from rtk-ai/rtk src/cmds tests (Apache-2.0, Copyright 2026 RTK AI Labs).
import os, sys, subprocess, tempfile
from harness import ok, done, Z

HOME = tempfile.mkdtemp()
os.environ.update(HOME=HOME, TZ_FEAT_RTK_FILTERS='1')
import tzrtk as R, tzcrush as C

SS = '=== test session starts ===\nplatform darwin -- Python 3.11.0\n'
P = R.pytest
ok('pytest all pass', P(SS + 'collected 5 items\n\ntests/test_foo.py .....    [100%]\n\n=== 5 passed in 0.50s ===') == 'Pytest: 5 passed in 0.50s')
fail = (SS + 'collected 5 items\n\ntests/test_foo.py ..F..    [100%]\n\n=== FAILURES ===\n___ test_something ___\n\n    def test_something():\n'
        '>       assert False\nE       assert False\n\ntests/test_foo.py:10: AssertionError\n\n=== short test summary info ===\n'
        'FAILED tests/test_foo.py::test_something - assert False\n=== 4 passed, 1 failed in 0.50s ===')
o = P(fail)
ok('pytest failure head', o.startswith('Pytest: 4 passed, 1 failed in 0.50s'))
ok('pytest failure detail', all(x in o for x in ('[FAIL] test_something', 'assert False', 'tests/test_foo.py:10', '::test_something')))
multi = (SS + 'collected 3 items\n\ntests/test_foo.py FFF  [100%]\n\n=== FAILURES ===\n___ test_one ___\nE   AssertionError: expected 5\n\n'
         '___ test_two ___\nE   ValueError: invalid value\n\n=== short test summary info ===\nFAILED tests/test_foo.py::test_three - KeyError\n=== 3 failed in 0.20s ===')
o = P(multi)
ok('pytest multiple', all(x in o for x in ('3 failed', 'test_one', 'test_two', 'expected 5', 'test_three')))
ok('pytest no tests', 'No tests collected' in P(SS + 'collected 0 items\n\n=== no tests ran in 0.00s ==='))
ok('pytest quiet', P('2 passed in 3.04s') == 'Pytest: 2 passed in 3.04s')
ok('pytest long', P('2 passed in 65.12s (0:01:05)') == 'Pytest: 2 passed in 65.12s')
ok('pytest warnings part', P('=== 5 passed, 2 warnings in 65.12s (0:01:05) ===') == 'Pytest: 5 passed in 65.12s')
ok('pytest only skipped', P('=== 3 skipped in 0.10s ===') == 'Pytest: 0 passed, 0 failed, 3 skipped in 0.10s')
ok('pytest quiet mixed', P('5 failed, 1698 passed, 2 skipped in 108.89s') == 'Pytest: 1698 passed, 5 failed, 2 skipped in 108.89s')
ok('pytest no summary -> None', P(SS + 'collected 3 items\ntests/a.py ..') is None)
ok('pytest two runs -> None', P('1 failed in 1.0s\n2 passed in 1.0s') is None)
ok('pytest keeps trailing output', 'DEPLOY BROKE' in P('2 passed in 1.0s\nDEPLOY BROKE'))

st = 'On branch main\n\nChanges not staged for commit:\n  (use "git add <file>..." to update)\n' + ''.join(f'\tmodified:   f{i}.py\n' for i in range(60)) + '\nUntracked files:\n\tnew.py\n'
o = R.git_status(st)
ok('status hints dropped, capped', '(use "git' not in o and '40 more entries' in o and 'new.py' in o and 'On branch main' in o)
ok('status -v left alone', R.git_status(st + 'diff --git a/x b/x\n') is None)
sha = 'a' * 40
log = f'commit {sha} (HEAD -> main)\nAuthor: Ann <a@x.test>\nDate:   Mon Jan 1\n\n    Fix thing\n\n    body 1\n    body 2\n    body 3\n    body 4\n    Signed-off-by: Ann\n'
o = R.git_log(log)
ok('log compact', o.startswith('aaaaaaa (HEAD -> main) Fix thing (Mon Jan 1) <Ann>') and '[+1 lines omitted]' in o and 'Signed-off' not in o)
ok('log cap 50', '10 more commits' in R.git_log(log * 60))
ok('log user count kept', 'more commits' not in R.git_log(log * 60, 'git log -60'))
ok('log patch -> None', R.git_log(log + 'diff --git a/x b/x\n') is None)

cargo = ('   Compiling rtk v0.5.0\n    Finished test target(s) in 2.53s\n\nrunning 3 tests\ntest u::a ... ok\ntest u::b ... FAILED\ntest u::c ... ok\n\n'
         'failures:\n\n---- u::b stdout ----\nthread panicked at assert_eq!(1, 2)\n\ntest result: FAILED. 2 passed; 1 failed\n')
o = R.FILTERS['cargo'](cargo)
ok('cargo keeps failures', all(x in o for x in ('u::b ... FAILED', 'panicked', 'test result: FAILED')) and 'Compiling' not in o and 'u::a' not in o)
npm = '\n> project@1.0.0 build\n> next build\n\nnpm WARN deprecated inflight@1.0.6: no\nnpm notice\n\n   Creating an optimized production build...\n> quoted line\n'
o = R.FILTERS['npm'](npm)
ok('npm noise dropped', 'npm WARN' not in o and 'project@1.0.0' not in o and 'next build' in o and 'Creating' in o and '> quoted line' in o)
o = R.FILTERS['go']('=== RUN   TestA\n--- PASS: TestA (0.00s)\n=== RUN   TestB\n    b_test.go:3: boom\n--- FAIL: TestB (0.00s)\nFAIL\n')
ok('go keeps fail', 'boom' in o and '--- FAIL: TestB' in o and 'TestA' not in o)

t = R.tsc("src/a.ts(3,5): error TS2322: Type 'string' is not assignable.\n  extra detail\nsrc/b.ts:9:1 - error TS2304: Cannot find name 'x'.\n\n9 x\n  ~\nFound 2 errors.\n")
ok('tsc grouped', all(x in t for x in ('2 errors in 2 files', 'L3 TS2322', 'extra detail', 'L9 TS2304', 'Top codes')))
ok('tsc never false green', R.tsc('error: tool missing') is None)
m = R.mypy('a.py:12: error: Bad type  [arg-type]\na.py:12: note: hint here\nb.py:1:2: error: Nope  [name-defined]\nFound 2 errors in 2 files\n')
ok('mypy grouped with note', all(x in m for x in ('2 errors in 2 files', 'L12 [arg-type] Bad type', 'note: hint here', 'b.py')))
ok('mypy clean -> None', R.mypy('Success: no issues found in 3 source files') is None)
rf = R.ruff('F401 [*] `os` imported but unused\n --> a.py:1:8\n  |\n1 | import os\n  |\nb.py:2:1: E501 Line too long\nFound 2 errors.\n')
ok('ruff text', all(x in rf for x in ('2 issues in 2 files', 'a.py:1:8 F401', 'b.py:2:1 E501', 'Found 2 errors.')))
rj = R.ruff('[{"code":"F401","filename":"a.py","location":{"row":1,"column":8},"message":"unused"}]')
ok('ruff json', 'a.py:1:8 F401 unused' in rj)

ok('detect cmd', R.detect('', 'cd /x && FOO=1 python3 -m pytest -q') == 'pytest' and R.detect('', 'rtk git -C /r status') == 'git_status')
ok('detect pipe falls back', R.detect('hello', 'git log | grep x') is None)
ok('detect strict content', R.detect('notes\n=== test session starts ===\n') is None and R.detect(SS) == 'pytest')

big = SS + 'collected 900 items\n\n' + ''.join(f'tests/test_{i}.py ....  [ {i % 100}%]\n' for i in range(900)) + '\n=== 3600 passed in 9.00s ==='
new, kd = C.crush(big)
ok('crush uses rtk filter', kd == 'rtk:pytest' and new == 'Pytest: 3600 passed in 9.00s')
ok('crush takes cmd', C.crush('\n'.join(['   Compiling a v1'] * 30 + ['error[E1]: x']), 'cargo build')[1] == 'rtk:cargo')
hunk = 'diff --git a/n b/n\n@@ -0,0 +1,300 @@\n' + '\n'.join(f'+l{i}' for i in range(300))
new, kd = C.crush(hunk)
ok('crush caps hunks', kd == 'diff' and '200 more lines in this hunk' in new)
os.environ['TZ_FEAT_RTK_FILTERS'] = '0'
ok('feature off', C.crush(big)[1] != 'rtk:pytest' and C.crush(hunk)[0] is None)
os.environ['TZ_FEAT_RTK_FILTERS'] = '1'

CLI = [sys.executable, os.path.join(Z, 'bin', 'tzrtk.py')]


def cli(args, inp='', **env):
    return subprocess.run(CLI + args, input=inp, capture_output=True, text=True, env=dict(os.environ, **env), timeout=30)


r = cli(['filter'], big)
rid = r.stdout.split('tz recall ')[-1].strip(' ]\n')
orig = os.path.join(HOME, '.claude', 'token-zombie', 'recall', rid + '.txt')
ok('cli filter spills original', r.returncode == 0 and '[actual]' in r.stdout and os.path.exists(orig) and open(orig).read() == big)
ok('cli passthrough unchanged', cli(['filter'], 'plain\n').stdout == 'plain\n')
r = cli(['run', '--', sys.executable, '-c', 'import sys;print("boom");sys.exit(3)'])
ok('cli run keeps exit code', r.returncode == 3 and 'boom' in r.stdout)
ok('cli missing command', cli(['run', '--', 'tz-no-such-cmd']).returncode == 127)
bin_ = tempfile.mkdtemp()
for n, body in (('rtk', 'echo "fake-rtk $@"; exit 4'), ('git', 'echo real-git')):
    with open(os.path.join(bin_, n), 'w') as fh:
        fh.write(f'#!/bin/sh\n{body}\n')
    os.chmod(os.path.join(bin_, n), 0o755)
if os.name != 'nt':
    path = bin_ + os.pathsep + os.environ['PATH']
    r = cli(['run', '--', 'git', 'status'], PATH=path)
    ok('delegates to installed rtk', r.stdout.strip() == 'fake-rtk git status' and r.returncode == 4)
    ok('TZ_RTK=0 uses built-in', 'real-git' in cli(['run', '--', 'git', 'status'], PATH=path, TZ_RTK='0').stdout)
    ok('unfiltered command not delegated', 'real-git' in cli(['run', '--', 'git', 'push'], PATH=path).stdout)
ok('cli status/usage', 'pytest' in cli(['status']).stdout and cli(['bogus']).returncode == 2)
done()
