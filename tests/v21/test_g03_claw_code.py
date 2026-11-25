# tzclaw: stale-branch check before full test runs (behaviour from claw-code docs; no upstream code).
import os, tempfile, subprocess, io, contextlib, json
T = tempfile.mkdtemp()
os.environ.update(HOME=T, USERPROFILE=T, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1',
                  GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@example.invalid', GIT_COMMITTER_NAME='t',
                  GIT_COMMITTER_EMAIL='t@example.invalid')
for k in [k for k in os.environ if k.startswith('TZ_')]:
    del os.environ[k]
from harness import ok, done, Z
import tzclaw

R = os.path.join(T, 'repo')
os.mkdir(R)


def git(*a, cwd=R):
    return subprocess.run(['git', '-C', cwd, *a], capture_output=True, text=True)


def commit(name, msg):
    open(os.path.join(R, name), 'w').write(msg)
    git('add', name)
    git('commit', '-qm', msg)


for cmd in ('pytest', 'pytest -q tests/', 'python3 -m pytest -n 4 -x', 'rtk pytest', 'FOO=1 timeout 60 pytest 2>&1 | tail -5',
            'python -m unittest', 'python -m unittest discover -s tests', 'cargo test', 'cargo test --workspace -- --nocapture',
            'go test ./...', 'npm test', 'pnpm run test', 'make test', 'bash tests/run_all.sh', 'npx vitest run', 'tox',
            'git status && pytest > log.txt', 'poetry run pytest .'):
    ok('broad: ' + cmd, tzclaw.broad_test_dir(cmd, R) == R)
for cmd in ('pytest tests/test_a.py', 'pytest tests/test_a.py::test_x', 'pytest -k name', 'pytest tests/unit', 'pytest --lf',
            'pytest --version', 'python -m unittest tests.test_a', 'cargo test -p runtime', 'cargo test my_case',
            'cargo test -- my_case', 'go test', 'go test ./pkg/...', 'npm test -- a.test.js', 'make test-unit',
            'jest src/a.test.js', 'echo "pytest"', 'git commit -m "run pytest; make test"', 'grep -r pytest .', 'pytest "', ''):
    ok('targeted/other: ' + cmd, tzclaw.broad_test_dir(cmd, R) is None)
ok('cd followed', tzclaw.broad_test_dir('cd sub && pytest', R) == os.path.join(R, 'sub'))

ok('no repo is unknown', tzclaw.check(T)['state'] == 'unknown')
git('init', '-q')
git('symbolic-ref', 'HEAD', 'refs/heads/main')
commit('a', 'first')
git('checkout', '-qb', 'feat')
ok('same commit fresh', tzclaw.check(R)['state'] == 'fresh')
commit('b', 'feature work')
r = tzclaw.check(R)
ok('ahead only stays fresh', r['state'] == 'fresh' and r['ahead'] == 1)
git('checkout', '-q', 'main')
commit('c', 'fix flaky parser')
git('checkout', '-q', 'feat')
r = tzclaw.check(R)
ok('diverged', r['state'] == 'diverged' and r['behind'] == 1 and r['ahead'] == 1)
ok('missing fix named', r['missing'] == ['fix flaky parser'])
git('checkout', '-qb', 'old', 'main~1')
r = tzclaw.check(R)
ok('stale', r['state'] == 'stale' and r['behind'] == 1 and r['ahead'] == 0)
ok('bad base is unknown', tzclaw.check(R, 'nope')['state'] == 'unknown')
ok('option-like base is unknown', tzclaw.check(R, '--all')['state'] == 'unknown')

ev = lambda cmd, s='s1': {'tool_name': 'Bash', 'tool_input': {'command': cmd}, 'cwd': R, 'session_id': s}
os.environ.update(TZ_FEAT_STALE_WARN='0', TZ_FEAT_STALE_BLOCK='0')
ok('features off: silent', tzclaw.hook(ev('pytest')) == ('', ''))
os.environ['TZ_FEAT_STALE_WARN'] = '1'
ok('targeted skips preflight', tzclaw.hook(ev('pytest tests/test_a.py')) == ('', ''))
k, why = tzclaw.hook(ev('pytest'))
ok('warns on full run', k == 'warn' and '1 commit(s) [actual] behind main' in why and 'fix flaky parser' in why)
ok('warns once', tzclaw.hook(ev('pytest')) == ('', ''))
os.environ['TZ_FEAT_STALE_BLOCK'] = '1'
k, why = tzclaw.hook(ev('cargo test', 's2'))
ok('blocks full run behind main', k == 'deny' and 'Blocked once' in why)
ok('rerun passes', tzclaw.hook(ev('cargo test', 's2')) == ('', ''))
ok('non-Bash ignored', tzclaw.hook({'tool_name': 'Read', 'cwd': R}) == ('', ''))

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = tzclaw.main(['--dir', R, '--json'])
ok('cli stale exit 1', rc == 1 and json.loads(buf.getvalue())['state'] == 'stale')
with contextlib.redirect_stdout(io.StringIO()):
    ok('cli unknown exit 2', tzclaw.main(['--dir', T]) == 2)
    git('checkout', '-q', 'main')
    ok('cli fresh exit 0', tzclaw.main(['--dir', R]) == 0)
ok('fresh: hook silent', tzclaw.hook(ev('pytest', 's3')) == ('', ''))

# remote-tracking main further on than the local copy
git('update-ref', 'refs/remotes/origin/main', 'main')
git('reset', '-q', '--hard', 'main~1')
r = tzclaw.check(R)
ok('origin/main wins when local main is old', r['state'] == 'stale' and r['base'] == 'origin/main')
os.mkdir(os.path.join(R, '.git', 'rebase-merge'))
ok('mid-rebase is unknown', tzclaw.check(R)['state'] == 'unknown')
done()
