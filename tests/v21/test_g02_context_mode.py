# tz sandbox (context-mode behaviour, rebuilt): only printed output returns, big output is stored and searchable.
# Parity cases come from the upstream README's described behaviour (batch + query, timeout, preload env, data file).
import os, re, subprocess, sys, tempfile, time
from harness import ok, done, Z

HOME = tempfile.mkdtemp()
WORK = tempfile.mkdtemp()
ENV = dict(os.environ, HOME=HOME, USERPROFILE=HOME, NODE_OPTIONS='--x', BASH_ENV='/nonexistent')
PY = ['--lang', 'py']
RECALL = os.path.join(HOME, '.claude', 'token-zombie', 'recall')


def run(*args, inp=None, mod='tzsandbox.py'):
    r = subprocess.run([sys.executable, os.path.join(Z, 'bin', mod), *args], input=inp, capture_output=True,
                       text=True, env=ENV, cwd=WORK, timeout=60)
    return r.returncode, r.stdout + r.stderr


def stored():
    return os.listdir(RECALL) if os.path.isdir(RECALL) else []


c, o = run(*PY, '-c', 'data = "x" * 100000\nprint(len(data))')
ok('only printed output returns', c == 0 and o == '100000\n')
ok('small output is not stored', not stored())

c, o = run(*PY, '-c', '-', inp='print("from stdin")')
ok('code from stdin', o.strip() == 'from stdin')

c, o = run(*PY, '-c', 'import sys\nprint("boom", file=sys.stderr)\nsys.exit(7)')
ok('stderr and exit code kept', c == 7 and 'boom' in o and '[exit 7]' in o)

c, o = run(*PY, '-c', 'import os\nprint(os.environ.get("NODE_OPTIONS"), os.environ.get("BASH_ENV"), os.getcwd())')
ok('preload variables removed', o.startswith('None None '))
ok('runs in the current folder', os.path.basename(WORK) in o)

with open(os.path.join(WORK, 'data.csv'), 'w') as fh:
    fh.write('a\n' * 500)
c, o = run(*PY, '--file', 'data.csv', '-c', 'import os\nprint(sum(1 for _ in open(os.environ["TZ_FILE"])))')
ok('data file passed as TZ_FILE', o.strip() == '500')
ok('missing data file is an error', run('--file', 'nope', '-c', 'true')[0] == 2)

big = 'for i in range(4000): print("line", i, "ordinary filler text")\nprint("ERROR cache miss on package zlib")\n' \
      'for i in range(4000): print("more", i, "ordinary filler text")'
c, o = run(*PY, '--max', '2000', '-c', big)
rid = re.search(r'tz recall ([0-9a-f]{10})', o)
ok('big output bounded', c == 0 and len(o) < 2600 and '[actual]' in o)
ok('big output stored', bool(rid) and len(stored()) == 1)
c, o = run('recall', rid.group(1) if rid else '', '--grep', 'cache miss', mod='tzout.py')
ok('full text reachable by recall', 'ERROR cache miss on package zlib' in o)

c, o = run(*PY, '--max', '3000', '-c', big, '--find', 'cache miss')
ok('find returns the matching part', 'ERROR cache miss on package zlib' in o and len(o) < 3600)
c, o = run(*PY, '--max', '3000', '-c', big, '--find', 'qqqnothing')
ok('find says when nothing matches', 'no match for "qqqnothing"' in o and 'tz recall' in o)

batch_a = 'for i in range(1500): print("npm install step", i)\nprint("npm warn deprecated leftpad")'
batch_b = 'for i in range(1500): print("commit", i, "chore")\nprint("commit feat sandbox runner")'
c, o = run(*PY, '--max', '4000', '-c', batch_a, '-c', batch_b, '--find', 'deprecated leftpad', '--find', 'feat sandbox')
ok('batch: both queries answered', 'npm warn deprecated leftpad' in o and 'commit feat sandbox runner' in o)
ok('batch: labelled and bounded', '== [1]' in o and '== [2]' in o and len(o) < 5000)
c, o = run(*PY, '-c', 'print("one")', '-c', 'raise SystemExit(4)', '-c', 'print("three")')
ok('batch: all run, first failure code', c == 4 and 'one' in o and 'three' in o and '(exit 4)' in o)

c, o = run(*PY, '--max', '2000', '-c', 'print("[" + "0," * 200000 + "NEEDLE" + ",0" * 200000 + "]")', '--find', 'needle')
ok('one huge line: window around the hit', 'NEEDLE' in o and len(o) < 2600)

t = time.time()
c, o = run(*PY, '--timeout', '1', '-c', 'import subprocess,sys,time\nprint("started", flush=True)\n'
           'subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])\ntime.sleep(30)')
ok('timeout stops the run, keeps partial output', c == 124 and 'started' in o and 'timeout' in o and time.time() - t < 15)

c, o = run('--', sys.executable, '-c', 'import sys; print(sys.argv[1])', 'a b; echo no')
ok('command form uses an argument list, no shell', o == 'a b; echo no\n')
ok('unknown command is 127', run('--', 'tz-no-such-binary')[0] == 127)

if os.name != 'nt':
    c, o = run('-c', 'echo $((6*7))')
    ok('shell is the default language', o.strip() == '42')
    c, o = run('-c', 'touch ran-first', '-c', 'echo x\ngit reset --hard')
    ok('destructive shell refused, nothing run', c == 3 and 'refused' in o and not os.path.exists(os.path.join(WORK, 'ran-first')))
c, o = run('--', 'git', 'reset', '--hard')
ok('destructive command form refused', c == 3 and 'refused' in o)

with open(os.path.join(WORK, 'doc.md'), 'w') as fh:
    fh.write('# Title\n' + 'filler words here\n' * 600 + 'the retry budget is five\n')
c, o = run('--index', 'doc.md')
ok('index stores without printing content', c == 0 and 'retry budget' not in o and 'tz recall' in o)
c, o = run('recall', '--search', 'retry budget', mod='tzout.py')
ok('indexed file found by recall --search', 'retry' in o and 'no match' not in o)
c, o = run('--index', 'doc.md', '--find', 'retry budget')
ok('index with find', 'the retry budget is five' in o)

ok('usage on nothing', run()[0] == 2)
ok('code and command together rejected', run('-c', 'true', '--', 'true')[0] == 2)
ok('bad limits rejected', run('--max', '5', '-c', 'true')[0] == 2)

import tzmem, tzsandbox
tzmem.USE_FTS = False
ok('BM25 fallback without FTS5', 'zebra' in tzsandbox.find([('0' * 10, 'plain\n' * 900 + 'zebra crossing\n')], ['zebra'], 3000))
ok('upstream licence kept', 'Elastic License 2.0' in open(os.path.join(Z, 'third_party', 'context-mode', 'LICENSE')).read())
done()
