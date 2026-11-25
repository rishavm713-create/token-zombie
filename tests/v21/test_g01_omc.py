# tzteam: staged flow, checkpoint recovery, fresh-evidence gate, bounded fix loop (oh-my-claudecode port). Fake executor only.
import contextlib, io, json, os, shutil, subprocess, sys, tempfile, time

TMP = tempfile.mkdtemp(prefix='tzteam-')
os.environ.update(HOME=TMP, USERPROFILE=TMP)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import ok, done, Z
import tzteam as T
T.STATE = os.path.join(TMP, 'state')


def repo(name):
    d = os.path.join(TMP, name)
    os.makedirs(d)
    for a in (['init', '-q'], ['config', 'user.email', 't@example.invalid'], ['config', 'user.name', 't'], ['config', 'commit.gpgsign', 'false']):
        subprocess.run(['git'] + a, cwd=d, check=True, capture_output=True)
    put(d, 'a.txt', 'a\n')
    git(d, 'add', '-A'); git(d, 'commit', '-qm', 'base')
    return d


def git(d, *a):
    return subprocess.run(['git'] + list(a), cwd=d, check=True, capture_output=True, text=True).stdout


def put(d, f, text):
    with open(os.path.join(d, f), 'w') as h:
        h.write(text)


PRD = json.dumps({'tasks': [{'id': 't2', 'title': 'second', 'criteria': ['two works'], 'deps': ['t1']},
                            {'id': 't1', 'title': 'first', 'criteria': ['one works'], 'deps': []}]})
GOOD = json.dumps({'criteria': [{'id': i, 'status': 'VERIFIED', 'evidence': 'check exit 0'} for i in ('t2:1', 't1:1')]})


class Fake:
    """Scripted executor: replies[stage] is a list (last entry repeats) of dicts or callables(ctx)."""
    def __init__(self, **replies):
        self.replies = dict(plan=[{'text': 'the plan'}], prd=[{'text': '```json\n%s\n```' % PRD}], exec=[{'text': 'done'}],
                            verify=[{'text': GOOD}], fix=[{'text': 'fixed'}])
        self.replies.update(replies)
        self.calls, self.ctx = [], []

    def __call__(self, stage, ctx):
        self.calls.append(stage + (':' + ctx['item']['id'] if ctx['item'] else ''))
        self.ctx.append(ctx)
        q = self.replies[stage]
        r = q.pop(0) if len(q) > 1 else q[0]
        return r(ctx) if callable(r) else dict({'tokens': 10}, **r)


class Runner:
    """Fake command runner with scripted exit codes (last one repeats)."""
    def __init__(self, *codes, out='5 passed'):
        self.codes, self.out, self.n = list(codes) or [0], out, 0

    def __call__(self, cmd, cwd):
        self.n += 1
        return (self.codes.pop(0) if len(self.codes) > 1 else self.codes[0]), self.out


R = repo('main')
new = lambda **k: T.new_run('add feature', R, **dict({'test': 'fake-test'}, **k))['rid']

# happy path: order, dependency order, artifacts, billing
f, run = Fake(), Runner(0)
rid = new()
s, stop = T.drive(rid, f, runner=run)
ok('completes', s['phase'] == 'complete' and stop == 'complete')
ok('stage order with deps', f.calls == ['plan', 'prd', 'exec:t1', 'exec:t2', 'verify'])
ok('history', [h['phase'] for h in s['history']] == ['plan', 'prd', 'exec', 'verify', 'complete'])
ok('tokens billed', s['spent'] == 50 and s['iteration'] == 5)
ok('artifacts on disk', all(os.path.isfile(p) for p in s['artifacts'].values()))
ok('checks re-run after review', run.n == 2)
ok('finished run is not re-driven', T.drive(rid, f, runner=run)[1] == 'complete' and len(f.calls) == 5)

# transition table and guards (parity: team-pipeline transitions)
base = lambda ph: dict(phase=ph, history=[], tasks=[], artifacts={'plan_path': None, 'prd_path': None}, fix={'attempt': 0, 'max': 3, 'last': 'x'})
ok('illegal jump refused', T.transition(base('plan'), 'exec').startswith('illegal'))
ok('terminal has no exit', T.transition(base('complete'), 'plan').startswith('illegal'))
ok('exec needs artifact', 'requires' in T.transition(base('prd'), 'exec'))
b = base('exec'); b['tasks'] = [{'status': 'pending'}]
ok('verify needs all completed', 'requires' in T.transition(b, 'verify') and b['phase'] == 'exec')
ok('verify needs tasks', 'requires' in T.transition(base('exec'), 'verify'))
b = base('verify'); b['fix']['attempt'] = 3
T.transition(b, 'fix')
ok('fix over max fails', b['phase'] == 'failed' and 'fix loop exceeded' in b['history'][-1]['reason'])

# bounded fix loop
f = Fake()
s, _ = T.drive(new(max_fix=2), f, runner=Runner(1))
ok('fix loop bounded', s['phase'] == 'failed' and f.calls.count('fix') == 2 and 'verify' not in f.calls)
f = Fake()
s, _ = T.drive(new(), f, runner=Runner(1, 0))
ok('fix then pass', s['phase'] == 'complete' and f.calls[-2:] == ['fix', 'verify'])
ok('fix gets the failure', 'exit 1' in f.ctx[f.calls.index('fix')]['prompt'])
f = Fake(fix=[{'error': 'boom'}])
s, _ = T.drive(new(max_fix=2), f, runner=Runner(1))
ok('failed fix uses an attempt', s['phase'] == 'failed' and f.calls.count('fix') == 2)

# verify gate: fresh evidence only
ev = [{'check': 'tests', 'rc': 0, 'out': '3 passed', 'epoch': 2, 'tree': 'T', 'at': 1000}]
v = lambda e=ev, req=('tests',), ep=2, tr='T', now=1001: T.verdict(e, list(req), ep, tr, now)[0]
ok('approved when fresh', v() == 'approved')
ok('older than 5 min is stale', v(now=1000 + 301) == 'incomplete')
ok('future stamp is not fresh', v(now=999) == 'incomplete')
ok('old epoch is stale', v(ep=3) == 'incomplete')
ok('changed tree is stale', v(tr='U') == 'incomplete')
ok('missing build evidence', v(req=('tests', 'build')) == 'incomplete')
ok('no command, no proof', v(req=()) == 'incomplete')
ok('non-zero rejected', v([dict(ev[0], rc=1)]) == 'rejected')
ok('zero tests rejected', v([dict(ev[0], out='Ran 0 tests')]) == 'rejected')
ok('10 passing is not 0 passing', v([dict(ev[0], out='  10 passing')]) == 'approved')
s, _ = T.drive(new(), Fake(exec=[{'text': 'all tests pass'}]), runner=Runner(1))
ok('worker claim is not evidence', s['phase'] == 'failed')
s, _ = T.drive(new(test=None), Fake(), runner=Runner(0))
ok('no verify command fails closed', s['phase'] == 'failed' and 'no verification command' in s['history'][-1]['reason'])
fp = T.tree(R); put(R, 'u.txt', '1'); fp2 = T.tree(R); put(R, 'u.txt', '2'); fp3 = T.tree(R)
os.makedirs(os.path.join(R, '__pycache__')); put(R, '__pycache__/x.pyc', 'z')
ok('fingerprint sees untracked content', len({fp, fp2, fp3}) == 3 and T.tree(R) == fp3)
git(R, 'add', 'u.txt')
ok('fingerprint sees staged change', T.tree(R) != fp3)
git(R, 'rm', '-qf', 'u.txt'); shutil.rmtree(os.path.join(R, '__pycache__'))


def edits(ctx):
    put(R, 'a.txt', 'edited by reviewer %f\n' % time.time())
    return {'text': GOOD}


s, _ = T.drive(new(), Fake(verify=[edits]), runner=Runner(0))
ok('reviewer edit voids approval', s['phase'] == 'failed' and 'tree changed' in s['history'][-1]['reason'])
git(R, 'checkout', '-q', '--', 'a.txt')
f = Fake(verify=[{'text': 'looks good'}])
s, _ = T.drive(new(), f, runner=Runner(0))
ok('unreadable report retried then fails, no fix', s['phase'] == 'failed' and f.calls.count('verify') == 2 and 'fix' not in f.calls)
hedged = json.dumps({'criteria': [{'id': 't1:1', 'status': 'VERIFIED', 'evidence': 'it should work'}]})
f = Fake(verify=[{'text': hedged}, {'text': GOOD}])
s, _ = T.drive(new(), f, runner=Runner(0))
ok('hedged or missing criterion goes to fix', s['phase'] == 'complete' and f.calls.count('fix') == 1)
want = {'t1:1': 'x'}
rep = lambda **k: T.judge_review({'criteria': [dict({'id': 't1:1', 'status': 'VERIFIED', 'evidence': 'a.py:3'}, **k)]}, want)
ok('verified accepted', rep() == [])
ok('partial rejected', rep(status='PARTIAL') and rep(evidence=''))
ok('quoted test name allowed', rep(evidence="test 'should add' passed") == [])
s, _ = T.drive(new(review=False), Fake(), runner=Runner(0))
ok('no-review still gated by commands', s['phase'] == 'complete' and s['iteration'] == 4)

# prd validation
bad = lambda tasks: T.parse_prd(json.dumps({'tasks': tasks}))[0] is None
t = lambda i='a', **k: dict({'id': i, 'title': 'x', 'criteria': ['c']}, **k)
ok('criteria required', bad([t(criteria=[])]))
ok('path id refused', bad([t('../x')]) and bad([t('..')]))
ok('duplicate ids refused', bad([t('a'), t('A')]))
ok('cycle and unknown dep refused', bad([t('a', deps=['b']), t('b', deps=['a'])]) and bad([t(deps=['zz'])]))
f = Fake(prd=[{'text': 'nope'}])
s, _ = T.drive(new(), f, runner=Runner(0))
ok('bad prd bounded', s['phase'] == 'failed' and f.calls.count('prd') == 2)

# task errors bounded
f = Fake(exec=[{'error': 'boom'}])
s, _ = T.drive(new(), f, runner=Runner(0))
ok('task attempts bounded', s['phase'] == 'failed' and f.calls.count('exec:t1') == 2)

# limits
f = Fake()
rid = new(budget=15)
s, stop = T.drive(rid, f, runner=Runner(0))
ok('budget stop is resumable', stop == 'budget' and s['phase'] == 'exec' and all(x['status'] == 'pending' and not x['token'] for x in s['tasks']))
s, stop = T.drive(rid, f, runner=Runner(0), budget=10000)
ok('resume with bigger budget, no re-billing', s['phase'] == 'complete' and f.calls.count('plan') == 1)
rid = new(); x = T.load(rid); x['max_iterations'] = 2; T.save(x)
s, stop = T.drive(rid, Fake(), runner=Runner(0))
ok('iteration cap', stop == 'max_iterations' and s['phase'] == 'failed')
clock = [1000.0]


def slow(ctx):
    clock[0] += 100
    return {'text': 'plan'}


s, stop = T.drive(new(wall=50), Fake(plan=[slow]), runner=Runner(0), now=lambda: clock[0])
ok('wall limit before next call', stop == 'time' and s['iteration'] == 1)


# killed worker: checkpoint then die, resume
def die(ctx):
    ctx['checkpoint']({'step': 'half'})
    raise KeyboardInterrupt


def killed():
    rid = new()
    try:
        T.drive(rid, Fake(exec=[die]), runner=Runner(0))
    except KeyboardInterrupt:
        pass
    return rid


def snap(rid):
    with open(os.path.join(T.run_dir(rid), 'state.json')) as h:
        return h.read()


rid = killed()
k = T.load(rid); t1 = [x for x in k['tasks'] if x['id'] == 't1'][0]
ok('killed task stays claimed', t1['status'] == 'in_progress' and t1['token'])
for name, state, err in (('unknown is never dead', 'unknown', 'worker_liveness_unknown'), ('alive refused', 'alive', 'already_running')):
    before, f = snap(rid), Fake()
    ok(name, T.drive(rid, f, runner=Runner(0), live=lambda p: state)[1] == err and snap(rid) == before and not f.calls)
f = Fake()
s, _ = T.drive(rid, f, runner=Runner(0), live=lambda p: 'dead')
c = f.ctx[0]
ok('dead worker resumed from checkpoint', s['phase'] == 'complete' and c['resume'] == {'step': 'half'} and 'RESUMED' in c['prompt'])
ok('finished stages not repeated', f.calls == ['exec:t1', 'exec:t2', 'verify'])
rid = killed()
ok('expired lease covers pid reuse', T.recover(T.load(rid), live=lambda p: 'alive', now=lambda: time.time() + T.LEASE + 1) == '')
x = T.load(rid)
ok('recover replay is a no-op', T.recover(x, live=lambda p: 'unknown') == '' and x['tasks'][1]['resume'] == {'step': 'half'})
T.claim(x, x['tasks'][1], time.time())
T.recover(x, live=lambda p: 'dead')
ok('second kill keeps older progress', x['tasks'][1]['resume'] == {'step': 'half'})

# checkpoint integrity: fail closed before any write
rid = killed(); k = T.load(rid); t1 = k['tasks'][1]
d = T._ckdir(rid, 't1', t1['token'])
ok('replay identical', T.publish(rid, t1, 2, {'step': 'half'}) == 'replayed')
ok('conflicting replay', T.publish(rid, t1, 2, {'step': 'other'}) == 'conflict')
ok('oversize refused', T.publish(rid, t1, 3, {'x': 'y' * T.MAX_CKPT}) == 'invalid')
ok('latest selected', T.select(rid, t1)[0]['seq'] == 2)
ok('stale version', T.select(rid, dict(t1, version=99))[1] == 'stale')
with open(os.path.join(d, '2.json')) as h:
    raw = h.read()
put(d, '2.json', raw.replace('half', 'hacked'))
before = snap(rid)
ok('tamper fails closed', T.drive(rid, Fake(), runner=Runner(0), live=lambda p: 'dead')[1] == 'checkpoint_malformed:t1' and snap(rid) == before)
shutil.rmtree(d)
ok('missing checkpoint', T.recover(k, live=lambda p: 'dead') == 'checkpoint_missing:t1')
ok('unknown pids', all(T.liveness(p) == 'unknown' for p in (None, 0, -1, 'x', True)) and T.liveness(os.getpid()) == 'alive')
q = subprocess.Popen([sys.executable, '-c', '']); q.wait()
ok('exited pid is dead', T.liveness(q.pid) == 'dead')

# lease and claim token
x = dict(rid=new(), tasks=[dict(id='a', status='pending', deps=[], version=0, criteria=['c'])])
x = dict(T.load(x['rid']), tasks=x['tasks'])
a = x['tasks'][0]
clock[0] = 5000.0
T.claim(x, a, clock[0]); put_ck = T.checkpointer(x, a, lambda: clock[0])
ok('double claim refused', not T.claim(x, a, clock[0]))
clock[0] += T.LEASE - 60; put_ck({'n': 1})
ok('checkpoint renews lease, keeps version', a['until'] == clock[0] + T.LEASE and a['version'] == 1)
clock[0] += T.LEASE + 1


def raises(fn, word):
    try:
        fn()
    except ValueError as e:
        return word in str(e)
    return False


ok('expired lease not renewed', raises(lambda: put_ck({'n': 2}), 'lease_expired'))
a['token'] = 'other'
ok('old holder refused', raises(lambda: put_ck({'n': 3}), 'claim_conflict'))

# run lock, cancel, corrupt state, bad id
rid = new()
h = T.hold(rid)
ok('second driver refused', T.drive(rid, Fake(), runner=Runner(0))[1] == 'already_running')
h.close()


def cancels(ctx):
    T.cancel(ctx['cwd_rid'] if 'cwd_rid' in ctx else RID)
    return {'text': 'ok'}


RID = new()
f = Fake(exec=[cancels, {'text': 'ok'}])
s, stop = T.drive(RID, f, runner=Runner(0))
ok('cancel stops before next call', stop == 'cancelled' and f.calls == ['plan', 'prd', 'exec:t1'])
s, _ = T.drive(RID, f, runner=Runner(0))
ok('preserved run resumes', s['phase'] == 'complete' and f.calls[3] == 'exec:t2')
rid = new(); T.cancel(rid, preserve=False)
f = Fake()
ok('unpreserved cancel stays', T.drive(rid, f, runner=Runner(0))[1] == 'cancelled' and not f.calls)
rid = new(); put(T.run_dir(rid), 'state.json', '{bad')
ok('corrupt state quarantined', T.load(rid) is None and os.path.exists(os.path.join(T.run_dir(rid), 'state.json.corrupt')))
ok('traversal id refused', raises(lambda: T.run_dir('../x'), 'bad run id'))

s, _ = T.drive(new(), Fake(plan=[{'text': 'p', 'tokens': 1, 'measured': False}]), runner=Runner(0))
ok('estimated tokens labelled', '[est]' in T.report(s) and '[actual]' in T.report(T.load(RID)))

# real shell runner
s, _ = T.drive(new(test='"%s" -c "print(\'3 passed\')"' % sys.executable, review=False), Fake())
ok('real command evidence', s['phase'] == 'complete' and s['evidence'][0]['rc'] == 0)

# worktree safety
W = repo('wt')
w = T.safe_worktree(W, 'My Task')
ok('worktree created', os.path.isdir(w['path']) and w['branch'] == 'tz/my-task' and not w['reused'])
ok('clean tree reused', T.safe_worktree(W, 'My Task')['reused'])
put(w['path'], 'keep.txt', 'k')
ok('dirty kept', raises(lambda: T.safe_worktree(W, 'My Task'), 'worktree_dirty') and os.path.exists(os.path.join(w['path'], 'keep.txt')))
os.remove(os.path.join(w['path'], 'keep.txt')); git(w['path'], 'checkout', '-qb', 'elsewhere')
ok('wrong branch', raises(lambda: T.safe_worktree(W, 'My Task'), 'worktree_mismatch'))
put(W, 'dirty.txt', 'd')
ok('dirty leader', raises(lambda: T.safe_worktree(W, 'other'), 'leader_worktree_dirty'))


# CLI never calls a model without --go
def cli(*a):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        rc = T.main(list(a))
    return rc, out.getvalue()


n = len(os.listdir(os.path.join(T.STATE, 'team')))
rc, out = cli('team', 'do x', '--test', 'true')
ok('dry run writes nothing', rc == 0 and 'dry run' in out and len(os.listdir(os.path.join(T.STATE, 'team'))) == n)
ok('test command required', cli('do x', '--go')[0] == 2)
ok('unknown flag refused', cli('do x', '--test', 'true', '--yolo')[0] == 2 and cli('do x', '--budget')[0] == 2)
ok('status', cli('status', RID)[0] == 0 and 'complete' in cli('status', RID)[1])
ok('script entry', subprocess.run([sys.executable, os.path.join(Z, 'bin', 'tzteam.py')], capture_output=True).returncode == 2)

shutil.rmtree(TMP, ignore_errors=True)
done()
