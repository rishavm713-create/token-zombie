#!/usr/bin/env python3
import io, json, os, subprocess, sys, tempfile, contextlib
from harness import ok, done, Z
import tzreplayrank as R

tmp = os.path.realpath(tempfile.mkdtemp())
home = os.path.join(tmp, 'home'); os.makedirs(home)
os.environ['HOME'] = home
os.environ.pop('TZ_SLICE_REVERT', None)


def w(p, s, mode=None):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'wb') as f:
        f.write(s.encode() if isinstance(s, str) else s)
    if mode:
        os.chmod(p, mode)


def rd(p):
    with open(p, 'rb') as f:
        return f.read()


def cli(*a):
    o, e = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
        rc = R.main(list(a))
    return rc, o.getvalue() + e.getvalue()


# parity with the upstream audit rule: a 1 KB file replayed every turn outweighs a 12 KB file read once per session
r = R.rank_items([('big', 'session', 12000), ('small', 'turn', 1000)], 30)
ok('1KB every turn beats 12KB once', r[0]['path'] == 'small' and r[0]['cost'] == 7500 and r[1]['cost'] == 3000)
r = R.rank_items([(t, t, 4000) for t in reversed(R.TIERS)], 30)
ok('tier order', [x['tier'] for x in r] == list(R.TIERS))

proj = os.path.join(tmp, 'proj')
w(os.path.join(home, '.claude', 'CLAUDE.md'), '@RTK.md\nuse `@notimport.md`\n')
w(os.path.join(home, '.claude', 'RTK.md'), 'x' * 400 + ' @CLAUDE.md')
w(os.path.join(home, '.claude', 'notimport.md'), 'no')
w(os.path.join(proj, 'CLAUDE.md'), 'p' * 80)
w(os.path.join(proj, '.claude', 'skills', 's', 'SKILL.md'), '---\nname: s\ndescription: d\n---\n' + 'b' * 4000)
items = R.discover(proj, home)
by = {(os.path.basename(p), t) for p, t, _ in items}
ok('discover imports, project, skill split', {('CLAUDE.md', 'turn'), ('RTK.md', 'turn'), ('SKILL.md [frontmatter]', 'turn'), ('SKILL.md', 'task')} <= by)
ok('code-span is no import, no duplicates', ('notimport.md', 'turn') not in by and len(items) == len({p for p, _, _ in items}))


def a(mid, *blocks, **kw):
    return dict(type='assistant', message=dict(id=mid, content=list(blocks)), **kw)


def use(i, name, **ti):
    return dict(type='tool_use', id=i, name=name, input=ti)


def res(i, text):
    return dict(type='user', message=dict(content=[dict(type='tool_result', tool_use_id=i, content=text)]))


log = os.path.join(tmp, 'l.jsonl')
rows = [a('m1', use('t1', 'Read', file_path='/small')), res('t1', 's' * 400), a('m2'), a('m2'), a('m3'),
        a('side', isSidechain=True), a('m4', use('t2', 'Bash', command='cat big')), res('t2', 'B' * 1000), a('m5'),
        dict(type='system', subtype='compact_boundary'), a('m6'), a('m7')]
w(log, 'garbage\n[1]\n' + ''.join(json.dumps(x) + '\n' for x in rows))
n, got = R.log_rank(log)
ok('requests deduped, sidechain skipped', n == 7)
ok('size x replay beats raw size', got[0]['label'] == 'Read /small' and got[0]['cost'] == 400 and got[1]['cost'] == 250)
ok('replay stops at compaction', got[0]['replays'] == 4 and got[1]['replays'] == 1)
rc, out = cli('rank', '--cwd', proj, '--log', log, '--json')
j = json.loads(out)
ok('rank cli measured', rc == 0 and j['requests'] == 7 and j['basis'] == 'MEASURED from log' and j['results'])
rc, out = cli('rank', '--cwd', proj)
ok('rank cli labels assumption', rc == 0 and 'ASSUMED' in out)
ok('rank bad add', cli('rank', '--add', 'nope=x')[0] == 2 and cli('rank', '--log', os.path.join(tmp, 'none'))[0] == 2)

ok('counts', R.counts('212 passed, 0 failed in 3s') == {'passed': 212, 'failed': 0} and R.counts('pass 3 fail 1') == {'passed': 3, 'failed': 1})
base = dict(rc=0, counts=dict(passed=212, failed=0))
ok('upstream marker case 210/212 fails', not R.matches(base, dict(rc=0, counts=dict(passed=210, failed=2))))
ok('added tests ok, new skip not, exit code matters', R.matches(base, dict(rc=0, counts=dict(passed=214)))
   and not R.matches(base, dict(rc=0, counts=dict(passed=212, skipped=1))) and not R.matches(base, dict(rc=1, counts=base['counts'])))

# verified slice
repo = os.path.join(tmp, 'repo'); os.makedirs(repo)


def git(*x):
    return subprocess.run(['git', '-C', repo, '-c', 'user.email=t@t', '-c', 'user.name=t'] + list(x), capture_output=True, check=True).stdout


git('init', '-q')
w(os.path.join(repo, 'app.txt'), 'ok\n')
w(os.path.join(repo, 'user.txt'), 'v1\n')
w(os.path.join(repo, 'run.sh'), '#!/bin/sh\n', 0o755)
w(os.path.join(repo, 'gone.txt'), 'g\n')
w(os.path.join(repo, 'dir', 'a [1].txt'), 'a\n')
os.symlink('app.txt', os.path.join(repo, 'ln'))
git('add', '-A'); git('commit', '-qm', 'i')
# the user's own uncommitted work, staged and not, and an untracked file
w(os.path.join(repo, 'user.txt'), 'staged\n'); git('add', 'user.txt')
w(os.path.join(repo, 'user.txt'), 'staged\nunstaged\n')
w(os.path.join(repo, 'notes.txt'), b'mine\x00\xff')
os.remove(os.path.join(repo, 'gone.txt'))
index = git('diff', '--cached')
check = [sys.executable, '-c', "import sys;ok=open('app.txt').read()=='ok\\n';print('1 passed' if ok else '1 failed');sys.exit(0 if ok else 1)"]
os.chdir(repo)


def damage():
    for f, s in (('app.txt', 'broken\n'), ('user.txt', 'clobber\n'), ('notes.txt', 'clobber'), ('gone.txt', 'back\n'),
                 ('new/deep/x.txt', 'x'), ('dir/a [1].txt', 'changed'), ('run.sh', 'changed')):
        w(os.path.join(repo, f), s)
    os.chmod('run.sh', 0o644)
    os.remove('ln'); w(os.path.join(repo, 'ln'), 'not a link')


def pristine():
    return (rd('app.txt') == b'ok\n' and rd('user.txt') == b'staged\nunstaged\n' and rd('notes.txt') == b'mine\x00\xff'
            and not os.path.exists('gone.txt') and not os.path.exists('new') and rd('dir/a [1].txt') == b'a\n'
            and rd('run.sh') == b'#!/bin/sh\n' and os.stat('run.sh').st_mode & 0o111 and os.path.islink('ln')
            and os.readlink('ln') == 'app.txt' and git('diff', '--cached') == index)


rc, out = cli('slice', 'start', 'R1', '--', *check)
ok('start records baseline', rc == 0 and 'exit 0, 1 passed' in out)
ok('second start refused', cli('slice', 'start', 'R1', '--', *check)[0] == 3)
ok('list open', cli('slice', 'list')[1].strip() == 'R1')
w(os.path.join(repo, 'extra.txt'), 'good change')
rc, out = cli('slice', 'verify', 'R1')
ok('pass keeps change and clears snapshot', rc == 0 and 'Verified R1' in out and os.path.exists('extra.txt') and cli('slice', 'verify', 'R1')[0] == 3)
os.remove('extra.txt')

cli('slice', 'start', 'R2', '--', *check)
damage()
rc, out = cli('slice', 'verify', 'R2')
ok('fail reverts', rc == 1 and 'Reverted R2' in out)
ok('byte-for-byte, user edits and index survive', pristine())
dd = out.strip().rsplit('discarded versions: ', 1)[1]
saved = json.load(open(os.path.join(dd, 'meta.json')))
ok('discarded work recoverable', rd(os.path.join(dd, saved['user.txt']['blob'])) == b'clobber\n')

cli('slice', 'start', 'R3', '--', *check)
w(os.path.join(repo, 'app.txt'), 'broken\n')
rc, out = cli('slice', 'verify', 'R3', '--no-revert')
ok('no-revert switch', rc == 1 and rd('app.txt') == b'broken\n')
os.environ['TZ_SLICE_REVERT'] = '0'
ok('env off switch', cli('slice', 'verify', 'R3')[0] == 1 and rd('app.txt') == b'broken\n')
del os.environ['TZ_SLICE_REVERT']
ok('manual restore', cli('slice', 'restore', 'R3')[0] == 0 and pristine())

cli('slice', 'start', 'R4', '--', *check)
git('stash', 'list')
w(os.path.join(repo, 'app.txt'), 'broken\n')
git('commit', '-qm', 'human', '--allow-empty', '--only')
rc, out = cli('slice', 'verify', 'R4')
ok('HEAD moved: no forced restore', rc == 3 and 'HEAD moved' in out and rd('app.txt') == b'broken\n')
ok('drop', cli('slice', 'drop', 'R4')[0] == 0)
rc, out = cli('slice', 'start', 'R5', '--', *check)
ok('red baseline blocks', rc == 3 and 'red baseline' in out)
ok('red baseline allowed with flag', cli('slice', 'start', 'R5', '--allow-red', '--', *check)[0] == 0)
rc, out = cli('slice', 'verify', 'R5')
ok('red baseline makes no preservation claim', rc == 0 and 'no behaviour-preserved claim' in out)
w(os.path.join(repo, 'app.txt'), 'ok\n')

# a file turned into a directory, and a directory turned into a file
cli('slice', 'start', 'S', '--', *check)
os.remove('app.txt'); w(os.path.join(repo, 'app.txt', 'x'), 'x')
os.remove('dir/a [1].txt'); os.rmdir('dir'); w(os.path.join(repo, 'dir'), 'now a file')
rc, out = cli('slice', 'verify', 'S')
ok('file/dir swaps restored', rc == 1 and 'Reverted S' in out and pristine())

flaky = [sys.executable, '-c', "import os,sys;n=int(open(sys.argv[1]).read() or 0) if os.path.exists(sys.argv[1]) else 0;open(sys.argv[1],'w').write(str(n+1));sys.exit(1 if n==1 else 0)",
         os.path.join(tmp, 'counter')]
cli('slice', 'start', 'F', '--', *flaky)
rc, out = cli('slice', 'verify', 'F')
ok('fail then pass = unstable, kept', rc == 4 and 'Unstable' in out and cli('slice', 'list')[1].strip() == 'F')
ok('bad id, missing command, no command', cli('slice', 'start', '../x', '--', *check)[0] == 3 and cli('slice', 'start', 'Z')[0] == 3
   and cli('slice', 'start', 'Z', '--', 'no-such-cmd-xyz')[0] == 3)
ok('usage', cli()[0] == 2 and cli('slice', 'bogus')[0] == 2)
ok('licence shipped', 'Joseph Kim' in rd(os.path.join(Z, 'third_party', 'karpathy', 'LICENSE')).decode())
os.chdir(tmp)
done()
