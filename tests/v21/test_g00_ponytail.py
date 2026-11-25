# ponytail integration: tz debt ledger (parity with the upstream ponytail-debt skill) and the lean rules marker line.
import os, subprocess, sys, tempfile
from harness import ok, done, Z
import tzdebt

M = 'short' + 'cut'  # split so scanning TZ itself never reports these fixtures
P = 'pony' + 'tail'
T = tempfile.mkdtemp()


def put(name, text):
    path = os.path.join(T, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)


def cli(*args, cwd=T):
    return subprocess.run([sys.executable, os.path.join(Z, 'bin', 'tzdebt.py'), *args], cwd=cwd,
                          capture_output=True, text=True, encoding='utf-8', timeout=60)


ok('empty tree is clean', cli().stdout.strip() == 'No shortcut debt. Clean ledger.')

put('a.py', f'x = 1\n# {M}: 100 rows max, move to db at 1k\n')
put('src/b.js', f'// {M}: temp\nlet y; /* {P}: global lock, per-account locks if throughput matters */\n')
put('c.py', f'#{M}: regex, not a parser; tree-sitter if the map must be exact\n')
put('prose.md', f'keyboard {M}: ctrl+k\n# keyboard {M}: ctrl+j\nthe {M}: convention\n')
put('url.py', f'u = "https://{M}:s3cret@host"\n')
put('.gitignore', 'dep/\n')
put('dep/d.py', f'# {M}: ignored, never\n')
put('sub/.gitignore', '*.gen\n')
put('sub/e.gen', f'# {M}: ignored, never\n')
put('todo.py', '# TODO: cache it, when slow\n')


def check(label):
    """Same expectations inside and outside a git repo."""
    r = cli()
    out = r.stdout.splitlines()
    ok(label + ' exit 0', r.returncode == 0)
    ok(label + ' ceiling and upgrade', 'a.py:2, ceiling: 100 rows max. upgrade: move to db at 1k.' in out)
    ok(label + ' no-trigger', 'src/b.js:1, ceiling: temp. no-trigger.' in out)
    ok(label + ' old marker, block comment closed',
       'src/b.js:2, ceiling: global lock. upgrade: per-account locks if throughput matters.' in out)
    ok(label + ' semicolon keeps commas in ceiling',
       'c.py:1, ceiling: regex, not a parser. upgrade: tree-sitter if the map must be exact.' in out)
    ok(label + ' counts', out[-1] == '4 markers, 1 with no trigger. [actual]' and len(out) == 5)
    ok(label + ' prose, URL, ignored skipped', not any(w in r.stdout for w in ('prose', 'url.py', 's3cret', 'never')))
    ok(label + ' grouped by file', [x.split(':')[0] for x in out[:-1]] == ['a.py', 'c.py', 'src/b.js', 'src/b.js'])


check('no repo')
git = lambda *a: subprocess.run(['git', '-c', 'user.name=Ann', '-c', 'user.email=a@example.invalid',
                                 '-c', 'commit.gpgsign=false', *a], cwd=T, capture_output=True, check=True)
git('init', '-q')
git('add', 'a.py')
git('commit', '-qm', 'a')
check('repo')
o = cli('--owner').stdout
ok('owner from blame', 'move to db at 1k. owner: Ann.' in o)
ok('untracked row has no owner', 'src/b.js:1, ceiling: temp. no-trigger.\n' in o)
ok('custom marker', cli('--marker', 'TODO').stdout.startswith('todo.py:1, ceiling: cache it. upgrade: when slow.'))
ok('bad marker refused', cli('--marker', 'a|b').returncode == 2)
ok('path argument', cli('src', cwd=T).stdout.splitlines()[-1] == '2 markers, 1 with no trigger. [actual]')
r = cli(os.path.join(T, 'missing'))
ok('bad path is an error, not a clean ledger', r.returncode == 2 and 'Clean' not in r.stdout)
ok('long field capped', len(tzdebt.parse(f'# {M}: ' + 'z' * 5000, tzdebt.MARKERS)[0]) <= tzdebt.WIDTH + 3)
ok('control chars stripped', '\x1b' not in tzdebt.parse(f'# {M}: a\x1b[31m, b', tzdebt.MARKERS)[0])
ok('scan changes nothing', subprocess.run(['git', 'diff', '--quiet'], cwd=T).returncode == 0)

start = os.path.join(Z, 'bin', 'tz-start.py')
src = open(start, encoding='utf-8').read()
env = dict(os.environ, HOME=tempfile.mkdtemp(), TZ_FRESH_BG='0')
env['USERPROFILE'] = env['HOME']
s = subprocess.run([sys.executable, start], input='{"cwd":"%s","source":"startup","session_id":"g"}' % env['HOME'].replace('\\', '/'),
                   capture_output=True, text=True, encoding='utf-8', env=env, timeout=30).stdout
ok('lean rules teach the marker', f'`{M}: <limit>, <when to upgrade>`' in s)
ok('lean rule text not harvested by the scan', tzdebt.parse(src.split('Mark a deliberate')[1].split('\n')[0], tzdebt.MARKERS) is None)
ok('licence saved', 'DietrichGebert' in open(os.path.join(Z, 'third_party', 'ponytail', 'LICENSE'), encoding='utf-8').read())
done()
