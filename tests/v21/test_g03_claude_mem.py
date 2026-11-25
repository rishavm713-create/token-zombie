# claude-mem integration (bin/tzobs.py): upstream parity (tag stripping, title identity), capture, 3-step recall, injection gates.
import contextlib, io, os, shutil, tempfile, time
from harness import ok, done, Z

HOME = tempfile.mkdtemp()
os.environ['HOME'] = HOME
os.environ['USERPROFILE'] = os.environ['HOME']  # Windows expanduser reads this one
for k in [k for k in os.environ if k.startswith('TZ_')]:
    del os.environ[k]
import tzobs as O

# --- privacy: tests/utils/tag-stripping.test.ts parity ---
for src, want in (('before <private>outer<private>inner</private>secret tail</private> after', 'before  after'),
                  ('<private>a<private>b</private>c</private> KEEP <private>d</private>', 'KEEP'),
                  ('keep <private data-x="a<b>c">SECRET</private> end', 'keep  end'),
                  ('<claude-mem-context prose <private>SECRET</private>', '<claude-mem-context prose'),
                  ('<claude-mem-context note="<private>SECRET</private>">', '<claude-mem-context note="">'),
                  ("<private note=don't>SECRET</private> public ' >", "public ' >")):
    ok(f'strip {src[:40]}', O.strip_tags(src) == want)
for src in ('<claude-mem-context>prose<private>SECRET</private>', '<private><private>x</private> SECRET', 'a <private>SECRET'):
    ok(f'no leak {src[:40]}', 'SECRET' not in O.strip_tags(src))
fake = 'sk-' + 'ant-api03-' + 'a' * 30
for s in (f'curl -H "Authorization: Bearer abcdef1234567890"', 'export AWS_SECRET_ACCESS_KEY=hunter2hunter2', fake,
          'git clone https://bob:hunter2pw@example.com/x.git', 'mysql --password hunter2pw', 'AKIA' + 'B' * 16):
    r = O.redact(s)
    ok(f'redact {s[:25]}', '<redacted>' in r and not any(x in r for x in ('hunter2', 'abcdef1234', 'aaaaaaaa', 'BBBBBBBB')))
ok('redact leaves prose', O.redact('token usage went down') == 'token usage went down')

# --- identity: tests/dedup/normalize.test.ts + tests/sqlite/dedup-code-identifiers.test.ts parity ---
ok('normalize', O.normalize_title('Fixed   the   BUG!!!') == 'fixed the bug')
ok('normalize empty', all(O.normalize_title(x) == '' for x in ('!!!', '...', '\U0001F535', '\U0001F389\U0001F389', None)))
PAIRS = [('C++ parser', 'C parser'), ('C++ parser', 'C# parser'), ('src/config.ts', 'src config ts'), ('user_name', 'user name'),
         ('v1.2', 'v1 2'), ('src/foo-bar', 'src/foo bar'), ('/src/config.ts', 'src/config.ts'), ('source-root/config.ts', 'source root/config.ts'),
         ('C:\\src\\foo-bar', 'C:\\src\\foo bar'), ('.env', 'env'), ('_private', 'private'), ('C++.', 'C.'), ('C#.', 'C.'), ('src/.', 'src/..'),
         ('src\\.', 'src\\..'), ('.', '..'), ('/', '.'), ('C++:', 'C:'), ('C:', 'C'), ('@field', 'field'), ('foo::bar', 'foo bar'),
         ('__init__', 'init'), ('__Updated user_name field__', 'Updated user name field')]
for a, b in PAIRS[:-1]:
    ok(f'distinct {a} / {b}', not O.exact_title_match('Read ' + a, 'Read ' + b))
ok('prose equivalence', O.exact_title_match('Fixed the bug.', 'fixed THE bug') and O.exact_title_match('__Updated the field__', 'Updated the field'))
ok('bold keeps identifiers', not O.exact_title_match(*PAIRS[-1]))
ok('hash parity', O.content_hash('s', 't', 'n') == __import__('hashlib').sha256(b's\0t\0n').hexdigest()[:16]
   and O.content_hash('s', 't\0', 'n').startswith('tuple-'))

# --- store + dedup ---
P = '/p/one'
a = O.add(P, 's1', 'change', 'Changed a.py', files=['a.py'], now=100)
ok('stored', isinstance(a, int))
ok('same title same session merges', O.add(P, 's1', 'change', 'changed a.py', 'more', files=['b.py'], now=200) == a)
r = O.get([a])[0]
ok('merge keeps time, bumps count', r['n'] == 2 and r['t'] == 100 and r['t_last'] == 200 and r['files'] == ['a.py', 'b.py'])
ok('other session separate', O.add(P, 's2', 'change', 'Changed a.py') != a)
ok('identifier titles separate', O.add(P, 's1', 'change', 'Changed a/py') != a)
ok('refused', O.add(P, 's1', 'change', '  ') is None and O.add(P, 's1', 'nope', 'x') is None)
k = O.add(P, 's1', 'change', '!!!')
ok('keyless: exact repeat only', O.add(P, 's1', 'change', '!!!') == k and O.add(P, 's1', 'change', '???') != k)

# --- capture from hook events ---
repo = os.path.join(HOME, 'repo'); os.makedirs(os.path.join(repo, '.git'))
wt = os.path.join(HOME, 'wt'); os.makedirs(wt)
open(os.path.join(wt, '.git'), 'w').write(f'gitdir: {repo}/.git/worktrees/wt\n')
ok('worktree belongs to main project', O.locate(wt) == (repo, wt) and O.locate(os.path.join(repo)) == (repo, repo))
big = os.path.join(repo, 'big.py'); open(big, 'w').write('x = 1\n' * 600)
os.utime(big, (time.time() - 1000,) * 2)


def ev(name, tool='', inp=None, sid='A', **kw):
    return dict({'hook_event_name': name, 'tool_name': tool, 'tool_input': inp or {}, 'session_id': sid, 'cwd': repo}, **kw)


ok('off by default', O.hook(ev('PostToolUse', 'Edit', {'file_path': big, 'new_string': 'def z(): pass'})) == '' and not O.search('', repo))
os.environ['TZ_FEAT_OBS_RECORD'] = '1'
O.hook(ev('UserPromptSubmit', prompt='fix the login crash <private>my diary</private> token=abc123secret'))
O.hook(ev('PostToolUse', 'Edit', {'file_path': big, 'new_string': 'def login(user):\n    pass\n'}))
O.hook(ev('PostToolUseFailure', 'Bash', {'command': f'cd {repo} && pytest -q'}, error='Traceback\nAssertionError: bad login'))
O.hook(ev('PostToolUse', 'Bash', {'command': 'git commit -m x'}, tool_response={'stdout': '[main 1a2b3c4d] feat: add retry\n 1 file changed'}))
O.hook(ev('PostToolUse', 'Bash', {'command': 'python3 -m pytest tests'}, tool_response={'stdout': 'ok'}))
O.hook(ev('PostToolUse', 'Bash', {'command': 'ls -la'}, tool_response={'stdout': 'x'}))
O.hook(ev('PostToolUse', 'Read', {'file_path': big}))
O.hook(ev('PostToolUseFailure', 'Bash', {'command': 'sleep 99'}, error='x', is_interrupt=True))
rows = O.search('', repo)
by = {r['title']: r for r in rows}
ok('four observations', len(rows) == 4)
e = by.get('Changed big.py', {})
ok('edit: kind from request, symbol fact', e.get('type') == 'bugfix' and e.get('facts') == ['def login'] and e.get('files') == ['big.py'])
ok('failure with error line', 'AssertionError: bad login' in by.get('Failed: pytest -q', {}).get('narrative', ''))
ok('commit type from prefix', by.get('Commit: feat: add retry', {}).get('type') == 'feature')
ok('test success', 'Test command succeeded: python3 -m pytest tests' in by)
ok('nothing private stored', not any(x in str(rows) + str(O._session('A')) for x in ('diary', 'abc123secret')))
O.hook(ev('UserPromptSubmit', prompt='<private>all hidden</private>', sid='B'))
O.hook(ev('PostToolUse', 'Write', {'file_path': big, 'content': 'x'}, sid='B'))
ok('fully private turn not recorded', len(O.search('', repo)) == 4)
O.hook(ev('PostToolUse', 'Write', {'file_path': os.path.join(repo, '.env'), 'content': 'def leak(): pass'}, sid='C'))
ok('secret file: no content facts', O.search('.env', repo)[0]['facts'] == [])
for env, val, data in (('TZ_OBS_SKIP_TOOLS', ' write ', ev('PostToolUse', 'Write', {'file_path': big}, sid='D')),
                       ('TZ_OBS_SKIP_BASH', '^pytest', ev('PostToolUseFailure', 'Bash', {'command': 'pytest'}, sid='D')),
                       ('TZ_OBS_SKIP_BASH', '(', ev('PostToolUseFailure', 'Bash', {'command': 'make'}, sid='D')),
                       ('TZ_OBS_SKIP_SUBAGENTS', '1', ev('PostToolUse', 'Write', {'file_path': big}, sid='D', agent_id='x')),
                       ('TZ_OBS_SKIP_AGENT_TYPES', 'Explore', ev('PostToolUse', 'Write', {'file_path': big}, sid='D', agent_id='x', agent_type='explore')),
                       ('TZ_OBS_EXCLUDE', '*/repo', ev('PostToolUse', 'Write', {'file_path': big}, sid='D'))):
    os.environ[env] = val
    ok(f'skip {env}={val}', O.observe(data) == [])
    del os.environ[env]

for cmd, resp in (('grep -r pytest .', 'x'), ('pytest -q | tail -3', '1 failed'), ('cat test_a.py', 'x')):
    ok(f'no test claim: {cmd}', O.observe(ev('PostToolUse', 'Bash', {'command': cmd}, tool_response={'stdout': resp})) == [])

# --- progressive disclosure ---
hit = O.search('login assertion', repo, k=2)
ok('search ranks failure first', hit and hit[0]['title'] == 'Failed: pytest -q' and len(hit) <= 2)
ok('type + project filter', [r['type'] for r in O.search('', repo, 'feature')] == ['feature'] and not O.search('login', P))
ln = O.line(e)
ok('index row compact, no detail', ln.startswith(f"#{e['id']} ") and 'Request:' not in ln and ln.endswith('t') and len(ln) < 160)
T = '/p/tie'
ids = [O.add(T, 's', 'change', f'item {i}', now=(500 if 3 <= i <= 5 else i * 100)) for i in range(1, 10)]
order = [r['id'] for r in O._rows('WHERE project=? ORDER BY t, id', (T,))]
for mid in (ids[2], ids[3], ids[4]):  # tied times: exactly N neighbours each side
    at = order.index(mid)
    ok(f'timeline ties {mid}', [r['id'] for r in O.timeline(mid, 2, 2)] == order[at - 2:at + 3])
ok('timeline bounds', len(O.timeline(ids[0], 3, 0)) == 1 and O.timeline(999999) == [] and O.get([]) == [])


def cli(*a):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = O.main(list(a))
    return rc, buf.getvalue()


os.chdir(repo)
rc, out = cli('search', 'login', '--all')  # --all: macOS temp dirs are symlinked, so the cwd project name can differ
ok('cli search', rc == 0 and 'tz obs get ID' in out and 'Request:' not in out)
rc, out = cli('get', f"#{e['id']}")
ok('cli get full detail', rc == 0 and 'Request: fix the login crash' in out and 'facts: def login' in out)
rc, out = cli('timeline', str(e['id']), '-B', '1', '-A', '1')
ok('cli timeline marks anchor', rc == 0 and f"> #{e['id']} " in out)
ok('cli usage and miss', cli()[0] == 2 and cli('search', '-k', 'z')[0] == 2 and cli('search', 'zzzznothing')[0] == 1)
rc, out = cli('add', 'decision', 'No vector database', 'stdlib only')
new = int(out.split('#')[1])
ok('cli add + forget', rc == 0 and cli('forget', str(new))[0] == 0 and not O.get([new]) and cli('add', 'bad', 't')[0] == 2)

# --- summaries, injection, file context ---
s = O.sessions(repo, 5)
sa = next(x for x in s if ' A ' in x)
ok('session summary', all(x in sa for x in ('fix the login crash', 'changed: big.py', 'commits: feat: add retry', 'failed commands: 1')))
ok('inject off by default', O.hook(ev('SessionStart')) == '')
os.environ['TZ_FEAT_OBS_INJECT'] = '1'
c = O.hook(ev('SessionStart'))
ok('injected index', c.startswith('tz memory') and 'Changed big.py' in c and 'Last session' in c and len(c) <= O.CTX_CAP)
small = O.context(repo, 320)
ok('cap keeps whole rows', 0 < len(small) <= 320 and all(x.endswith('t') for x in small.split('\n')[1:] if x.startswith('#')))
ok('empty project injects nothing', O.context('/p/none') == '')
read = ev('PreToolUse', 'Read', {'file_path': big}, sid='Z')
ok('file context off by default', O.hook(read) == '')
os.environ['TZ_FEAT_OBS_FILE_CONTEXT'] = '1'
ok('own session excluded', O.hook(dict(read, session_id='A')) == '')
f = O.hook(read)
ok('file context shown', 'earlier work on big.py' in f and 'Changed big.py' in f)
ok('once per session', O.hook(read) == '')
os.utime(big, (time.time() + 100,) * 2)
ok('stale after file change', O.hook(dict(read, session_id='Y')) == '')
tiny = os.path.join(repo, 'tiny.py'); open(tiny, 'w').write('x')
O.add(repo, 'old', 'change', 'Changed tiny.py', files=['tiny.py'])
ok('small file skipped', O.hook(dict(read, session_id='Y', tool_input={'file_path': tiny})) == '')
ok('hook never raises', O.hook({'hook_event_name': 'PostToolUse', 'tool_name': 'Bash', 'tool_input': 'bad'}) == '')
dbp = os.path.join(HOME, '.claude', 'token-zombie', 'tz.db')
for x in (dbp, dbp + '-journal'):
    if os.path.exists(x):
        os.remove(x)
open(dbp, 'w').write('not a database' * 100)
ok('broken db fails open', O.search('x') == [] and O.add(P, 's', 'change', 't') is None and O.hook(read) == '')
os.chdir(Z); shutil.rmtree(HOME, ignore_errors=True)
done()
