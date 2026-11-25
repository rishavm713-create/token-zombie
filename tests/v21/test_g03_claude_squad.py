# tz squad (bin/tzsquad.py): behaviour parity with claude-squad's documented lifecycle. Temp git repos and temp HOME only.
import os, subprocess, sys, tempfile, shutil
from harness import ok, done, Z
import tzmore, tzsquad as sq

T = os.path.realpath(tempfile.mkdtemp(prefix='tz-g03-'))
os.environ.update(HOME=T, USERPROFILE=T, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                  GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@example.invalid', GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@example.invalid')
for k in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE'):
    os.environ.pop(k, None)
R, S = os.path.join(T, 'repo'), os.path.join(T, 'state')


def g(*a, cwd=R):
    return subprocess.run(['git', '-C', cwd, *a], capture_output=True, text=True).stdout.strip()


def put(p, text='x\n'):
    with open(p, 'w') as f:
        f.write(text)


def row(task):
    return next((r for r in sq.sessions(S, R)[1] if r['task'] == task), None)


def wt(task):
    return os.path.join(T, task)


os.mkdir(R)
g('init', '-q')
put(os.path.join(R, 'a.txt'), 'one\n')
put(os.path.join(R, '.gitignore'), '.env\nbuild/\n')
g('add', '-A'); g('commit', '-qm', 'init')
base = g('rev-parse', 'HEAD')

# pause commits dirty work on the session branch, removes the worktree, keeps branch + claims; resume brings it back
ok('add', tzmore.wt_add(S, 'feat', ['a.txt'], repo=R)[0])
ok('base recorded by git', sq.base_of(R, 'tz/feat') == base)
put(os.path.join(wt('feat'), 'a.txt'), 'two\n'); put(os.path.join(wt('feat'), 'new.txt'))
ok('list active + dirty', (row('feat')['status'], row('feat')['dirty'], row('feat')['ahead']) == ('active', 2, 0))
d = sq.diff(S, 'feat', R)[1]
ok('diff shows tracked + untracked', 'a.txt' in d and 'untracked: new.txt' in d)
ok('diff patch', '+two' in sq.diff(S, 'feat', R, patch=True)[1])
r = sq.pause(S, 'feat', R)
ok('pause', r[0] and not os.path.exists(wt('feat')))
ok('branch kept with commit', g('log', '-1', '--format=%s', 'tz/feat').startswith('tz squad: paused feat'))
ok('main branch untouched', g('rev-parse', 'HEAD') == base and not g('status', '--porcelain'))
ok('list paused', (row('feat')['status'], row('feat')['ahead']) == ('paused', 1))
ok('paused diff', 'new.txt' in sq.diff(S, 'feat', R)[1])
ok('pause twice refused', not sq.pause(S, 'feat', R)[0])
tzmore._own(S, lambda m: None)
ok('paused survives tz worktree pruning', row('feat')['status'] == 'paused')
ok('paused keeps claims', not tzmore.wt_add(S, 'other', ['a.txt'], repo=R)[0])
ok('resume', sq.resume(S, 'feat', R)[0] and os.path.isfile(os.path.join(wt('feat'), 'new.txt')))
ok('resume active refused', not sq.resume(S, 'feat', R)[0])
head = g('rev-parse', 'tz/feat')
ok('clean pause makes no commit', sq.pause(S, 'feat', R)[0] and g('rev-parse', 'tz/feat') == head)

# resume never overwrites a directory that appeared at the old path
os.mkdir(wt('feat')); put(os.path.join(wt('feat'), 'mine'))
r = sq.resume(S, 'feat', R)
ok('resume uses a new path', r[0] and row('feat')['path'] != wt('feat') and os.listdir(wt('feat')) == ['mine'])

# kill: dirty is kept; unmerged branch kept without force; force deletes
p = row('feat')['path']; put(os.path.join(p, 'dirty'))
ok('kill dirty refused', not sq.kill(S, 'feat', R)[0] and os.path.exists(os.path.join(p, 'dirty')))
os.remove(os.path.join(p, 'dirty'))
r = sq.kill(S, 'feat', R)
ok('kill keeps unmerged branch', r[0] and 'not merged' in r[1] and g('rev-parse', 'tz/feat') == head)
ok('killed entry gone', row('feat') is None)
tzmore.wt_add(S, 'gone', repo=R); put(os.path.join(wt('gone'), 'z')); sq.pause(S, 'gone', R)
ok('force kill deletes branch', sq.kill(S, 'gone', R, force=True)[0] and not g('branch', '--list', 'tz/gone'))
tzmore.wt_add(S, 'empty', repo=R)
ok('kill merged branch', sq.kill(S, 'empty', R)[0] and not g('branch', '--list', 'tz/empty'))

# a pre-existing branch can be attached and is never deleted
g('branch', 'tz/old')
ok('attach existing branch', sq.resume(S, 'old', R)[0] and os.path.isdir(wt('old')))
r = sq.kill(S, 'old', R, force=True)
ok('existing branch never deleted', r[0] and g('branch', '--list', 'tz/old') != '')

# worktree made outside the registry (tz agent --worktree) is discovered
g('worktree', 'add', '-q', wt('agent'), '-b', 'tz/agent')
ok('discovered', row('agent')['status'] == 'active')
put(os.path.join(wt('agent'), 'w'))
ok('discovered pause', sq.pause(S, 'agent', wt('agent'))[0] and not os.path.exists(wt('agent')))
ok('discovered resume from main', sq.resume(S, 'agent', R)[0])

# orphan: directory vanished, or lost its .git
tzmore.wt_add(S, 'orph', repo=R); shutil.rmtree(wt('orph'))
ok('orphan listed', row('orph')['status'] == 'orphaned')
ok('orphan pause', sq.pause(S, 'orph', R)[0] and row('orph')['status'] == 'paused')
ok('orphan resume', sq.resume(S, 'orph', R)[0])
os.remove(os.path.join(wt('orph'), '.git')); put(os.path.join(wt('orph'), 'keep'))
ok('broken dir kept', sq.pause(S, 'orph', R)[0] and os.path.isfile(os.path.join(wt('orph'), 'keep')))

# safety: failed commit, secrets, wrong branch, merge in progress, main checkout
tzmore.wt_add(S, 'safe', repo=R); W = wt('safe'); put(os.path.join(W, 'a.txt'), 'edit\n')
hook = os.path.join(R, '.git', 'hooks', 'pre-commit'); put(hook, '#!/bin/sh\nexit 1\n'); os.chmod(hook, 0o755)
before = g('status', '--porcelain', cwd=W)
r = sq.pause(S, 'safe', R)
ok('failed commit keeps worktree and staging', not r[0] and os.path.isdir(W) and g('status', '--porcelain', cwd=W) == before)
os.remove(hook)
put(os.path.join(W, 'id_rsa'))
ok('untracked secret not committed', not sq.pause(S, 'safe', R)[0] and g('rev-parse', 'tz/safe') == base)
os.remove(os.path.join(W, 'id_rsa')); put(os.path.join(W, '.env'))
ok('ignored secret protected', not sq.pause(S, 'safe', R)[0] and not sq.kill(S, 'safe', R)[0] and os.path.isfile(os.path.join(W, '.env')))
g('checkout', '-q', '-b', 'elsewhere', cwd=W)
ok('wrong branch refused', not sq.pause(S, 'safe', R)[0] and os.path.isdir(W))
g('checkout', '-q', 'tz/safe', cwd=W)
ok('drop ignored', sq.pause(S, 'safe', R, drop_ignored=True)[0] and not os.path.exists(W))
tzmore.wt_add(S, 'mrg', repo=R); W = wt('mrg'); put(os.path.join(W, 'a.txt'), 'theirs\n')
g('merge', 'tz/safe', cwd=W); g('commit', '-qam', 'm', cwd=W); g('merge', 'tz/safe', cwd=W)
ok('merge in progress refused', not sq.pause(S, 'mrg', R)[0] and os.path.isdir(W))
tzmore._own(S, lambda m: m.__setitem__('main', dict(path=R, branch=g('branch', '--show-current'), repo=R, files=[])))
ok('main checkout refused', not sq.pause(S, 'main', R)[0] and not sq.kill(S, 'main', R, force=True)[0] and os.path.isdir(R))

g('branch', 'tz/claim'); tzmore.wt_add(S, 'claim', ['c.txt'], repo=R)
ok('ownership-only entry attaches branch, keeps claims', sq.resume(S, 'claim', R)[0] and not tzmore.wt_add(S, 'rival', ['c.txt'], repo=R)[0])

# open prints commands only; unknown task; corrupt registry; CLI
r = sq.open_cmd(S, 'agent', R, program='aider --model x')
ok('open prints tmux', r[0] and "tmux new-session -d -s tz-agent" in r[1] and "'aider --model x'" in r[1])
ok('unknown task', not sq.pause(S, 'nope', R)[0])
bad = os.path.join(T, 'bad'); os.mkdir(bad); put(os.path.join(bad, 'worktrees.json'), '{')
ok('corrupt registry untouched', not sq.pause(bad, 'agent', R)[0] and open(os.path.join(bad, 'worktrees.json')).read() == '{')
cli = lambda *a: subprocess.run([sys.executable, os.path.join(Z, 'bin', 'tzsquad.py'), *a], cwd=R, capture_output=True, text=True)
c = cli('list')
ok('cli list', c.returncode == 0 and 'agent  active' in c.stdout)
ok('cli usage', cli('pause').returncode == 2 and cli('bogus').returncode == 2)
ok('cli unknown exits 1', cli('resume', 'nope').returncode == 1)

shutil.rmtree(T, ignore_errors=True)
done()
