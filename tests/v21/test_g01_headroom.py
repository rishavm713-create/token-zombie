# Headroom log compressor port (bin/tzlogc.py): parity cases from the research spec and upstream tests, plus recovery.
import os, re, sys, subprocess, tempfile
from harness import ok, done, Z

HOME = tempfile.mkdtemp()
os.environ['HOME'] = os.environ['USERPROFILE'] = HOME  # before any tz import: never the real ~/.claude
for k in ('TZ_HOME', 'CLAUDE_CONFIG_DIR', 'CLAUDE_PLUGIN_DATA', 'TZ_MODE', 'TZ_FEAT_LOG_COMPRESS'):
    os.environ.pop(k, None)
import tzlogc as L
import tzcrush as C


def txt(r):
    return r['text'] if r else ''


# --- 10,000-line pytest run with 5 failures
body = ['=' * 30 + ' test session starts ' + '=' * 30, 'collected 10000 items']
body += [f'tests/test_mod.py::test_case_{i} PASSED [ {i // 100}%]' for i in range(10000)]
body += ['=' * 35 + ' FAILURES ' + '=' * 35]
for i in range(5):
    body += [f'_____ test_bad_{i} _____', '', f'    def test_bad_{i}():', f'>       assert compute({i}) == -1',
             f'E       assert {i} == -1', '', f'tests/test_bad.py:{10 + i}: AssertionError']
summary = ['=' * 25 + ' short test summary info ' + '=' * 25]
summary += [f'FAILED tests/test_bad.py::test_bad_{i} - assert {i} == -1' for i in range(5)]
summary += ['=' * 20 + ' 5 failed, 10000 passed in 12.34s ' + '=' * 20]
log = '\n'.join(body + summary)
r = L.compress(log)
ok('pytest detected', r and r['format'] == 'pytest')
ok('pytest under 5%', r and r['chars_out'] < 0.05 * len(log))
out = txt(r).split('\n')
ok('every failure-section line kept', all(l in out for l in body[10002:] + summary))
ok('omission marker present', re.search(r'\[tz: \d+ lines omitted\]', txt(r)))
ok('measured sizes are real', r and r['chars_in'] == len(log) and r['chars_out'] == len(r['text']))
ok('passing test named after errors is not a failure', not L.is_error('tests/test_errors.py::test_error_path PASSED [ 3%]'))

ok('error line ending in PASSED stays a failure', L.is_error('ERROR expected state PASSED'))
ok('unittest ok line is a pass', not L.is_error('test_error_path (t.T.test_error_path) ... ok'))

# --- distinct errors stay distinct, every error survives (no caps, unlike upstream)
lines = [f'2026-01-01 INFO step {i} done' for i in range(600)]
errs = ['segfault at 0x1', 'segfault at 0x2'] + [f'ERROR worker {i} crashed' for i in range(60)] + ['ERROR same'] * 3
for n, e in enumerate(errs):
    lines.insert(5 + n * 7, e)
r = L.compress('\n'.join(lines))
ok('generic levelled log', r and r['format'] == 'generic')
ok('all 65 errors kept, order and duplicates intact', [l for l in txt(r).split('\n') if l in errs] == errs)
ok('prefix kept in dedupe key', L.dedupe_key('E0001: line 4') != L.dedupe_key('E0002: line 4'))
ok('suffix numbers normalised', L.dedupe_key('warn: line 4') == L.dedupe_key('warn: line 9'))

# --- 100 identical warnings -> 1 + x100
w = ['npm info start', 'npm info ok'] + ['npm WARN deprecated: pkg@1.0.0'] * 100 + [f'npm info fetch {i}' for i in range(40)]
r = L.compress('\n'.join(w))
ok('warnings deduped', r and txt(r).count('npm WARN deprecated') == 1 and 'x100 similar' in txt(r))

# --- gates: short input, poor ratio, non-logs
ok('under 50 lines unchanged', L.compress('\n'.join(['ERROR x'] + ['INFO y'] * 40)) is None)
ok('ratio >= 0.5 unchanged', L.compress('\n'.join(f'ERROR item {i}' for i in range(200))) is None)
ok('file listing is not a log', L.compress('\n'.join(f'src/pkg/module_{i}.py' for i in range(500))) is None)

# --- traces: python chain with blank lines, js frames, rust diagnostic, go panic, jest block, carriage returns
pad = [f'INFO tick {i}' for i in range(200)]
py = ['Traceback (most recent call last):', '  File "a.py", line 1, in <module>', '    run()', 'KeyError: 1', '',
      'During handling of the above exception, another exception occurred:', '', 'Traceback (most recent call last):',
      '  File "b.py", line 2, in run', '    go()', 'ValueError: two']
js = ['TypeError: x is undefined', '    at foo (/app/a.js:1:2)', '    at bar (/app/b.js:3:4)']
rs = ['error[E0382]: borrow of moved value', '  --> src/main.rs:4:5', '   |', '4  |     use(x);', '   |         ^ here']
go = ['panic: boom', '', 'goroutine 1 [running]:', 'main.main()', '\t/tmp/m.go:5 +0x1d', 'exit status 2']
for name, block in (('python chain', py), ('js frames', js), ('rust diagnostic', rs), ('go panic', go)):
    o = txt(L.compress('\n'.join(pad + block + pad))).split('\n')
    at = o.index(block[0]) if block[0] in o else -1
    ok(f'{name} kept whole', at >= 0 and o[at:at + len(block) - (name == 'go panic')] == block[:len(block) - (name == 'go panic')])
jest = ['PASS src/a.test.js'] * 80 + ['FAIL src/b.test.js', '  ● adds', '', '    Expected: 2', '    Received: 3', '',
        '      at Object.<anonymous> (src/b.test.js:4:1)', '', 'Test Suites: 1 failed, 80 passed']
o = txt(L.compress('\n'.join(jest)))
ok('jest failure block kept', all(l in o.split('\n') for l in jest[80:]))
frames = ['java.lang.IllegalStateException: bad'] + [f'    at java.base.Thing.run{i}(Thing.java:{i})' for i in range(30)] \
    + ['    at com.me.App.main(App.java:3)', 'Caused by: java.io.IOException: disk']
o = txt(L.compress('\n'.join(pad + frames + pad)))
ok('runtime frames collapsed, app frame and cause kept', 'run25(' not in o and 'com.me.App.main' in o and frames[-1] in o)
cr = '\n'.join(pad + ['step\rERROR lost?\r100% done'] + pad)
ok('carriage-return redraw keeps the error segment', 'ERROR lost?' in txt(L.compress(cr)))
ok('compiler flags are not failures', not L.is_error('gcc -Werror -c main.c') and L.is_error('gcc: error: no input files'))

# --- tzcrush routing: off until the feature is on
os.environ['TZ_FEAT_LOG_COMPRESS'] = '0'
ok('feature off keeps old crusher', C.crush(log)[1] != 'buildlog')
os.environ['TZ_FEAT_LOG_COMPRESS'] = '1'
new, kd = C.crush(log)
ok('feature on routes build logs', kd == 'buildlog' and new == L.compress(log)['text'])
ok('hunk text inside test output still a build log', C.crush(log.replace('E       assert 0 == -1', '@@ -1 +1 @@'))[1] == 'buildlog')
ok('json still json', C.crush('[' + ','.join('{"id": %d}' % i for i in range(60)) + ']')[1] == 'json')
ok('real git diff still diff', C.crush('diff --git a/f b/f\n@@ -1 +1 @@\n' + ' c\n' * 80 + '-a\n+b')[1] == 'diff')

# --- through the existing output hook (tzout.cut): original spilled, failures on the wire
import tzout
kept, hidden = tzout.cut(log, tzout.OTHER_MAX, False)
rid = tzout.spill(log)
ok('hook path marks recall id', 'crushed buildlog' in kept and f'tz recall {rid}' in kept and hidden > 0)
ok('hook path keeps failures', all(l in kept for l in summary))
ok('hook path stored the original', open(os.path.join(tzout.RECALL, rid + '.txt'), encoding='utf-8').read() == log)
ok('state stays in the temp home', tzout.RECALL.startswith(HOME))

# --- CLI: full text recoverable, byte for byte
env = dict(os.environ)
tool = os.path.join(Z, 'bin', 'tzlogc.py')
f = os.path.join(HOME, 'run.log')
open(f, 'w', encoding='utf-8', newline='').write(log)
p = subprocess.run([sys.executable, tool, f], capture_output=True, text=True, encoding='utf-8', env=env)
m = re.search(r'full: tz recall (\w+)\]', p.stdout)
ok('cli prints recall marker', p.returncode == 0 and m)
ok('cli labels measured chars', f'[MEASURED] pytest log: {len(log)} -> {len(p.stdout.rstrip(chr(10)))} chars' in p.stderr)
back = subprocess.run([sys.executable, os.path.join(Z, 'bin', 'tzout.py'), 'recall', m.group(1) if m else 'x'],
                      capture_output=True, text=True, encoding='utf-8', env=env)
ok('recall returns the full original', back.stdout == log + '\n')
raw = b'\xff\xfe bad bytes\n' * 80
p = subprocess.run([sys.executable, tool], input=raw, capture_output=True, env=env)
ok('undecodable input passes through unchanged', p.stdout == raw)
p = subprocess.run([sys.executable, tool], input=b'short\n', capture_output=True, env=env)
ok('short input passes through unchanged', p.stdout == b'short\n')
blocked = tempfile.mkdtemp()
open(os.path.join(blocked, '.claude'), 'w').close()  # state dir cannot be created: storing the original fails
p = subprocess.run([sys.executable, tool, f], capture_output=True, env=dict(env, HOME=blocked, USERPROFILE=blocked))
ok('store failure prints the original, no marker', p.stdout.replace(b'\r\n', b'\n') == log.encode() and b'tz recall' not in p.stdout)
done()
