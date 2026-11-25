# Crash-restart backoff (ai-maestro, MIT). Parity cases from upstream tests/crash-restart.test.ts plus TZ checkpoint cases.
import os, sys, json, time, shutil, subprocess, tempfile
T = tempfile.mkdtemp()
os.environ.update(HOME=T, USERPROFILE=T, TZ_WORKERS_DIR=os.path.join(T, 'w'))  # before the tz imports read them
for k in ('TZ_FEAT_CRASH_RESTART', 'TZ_WORKER', 'TZ_SUP'):
    os.environ.pop(k, None)
from harness import ok, done, Z
import tzagent, tzworkers, tzbackoff as B, tzsup

NOW = time.time()
base = dict(at_shell=True, record={'status': 'running', 'at': NOW - 600}, restarts=[], failed=False, now=NOW, last_activity=NOW - 600)
act = lambda **k: B.crash_action(**dict(base, **k))['action']
# upstream: decision
ok('restarts a crashed run', act() == 'restart')
ok('running program left alone', act(at_shell=False) == 'none')
ok('quit on purpose left alone', act(record={'status': 'ended', 'at': NOW}) == 'none')
ok('never reported left alone', act(record=None) == 'none')
ok('failed left alone', act(failed=True) == 'none')
ok('busy is not interrupted', act(last_activity=NOW - B.QUIET + 1) == 'none')
ok('backoff waits', act(restarts=[NOW - 10]) == 'wait')
ok('backoff over', act(restarts=[NOW - 40]) == 'restart')
ok('second step is 60 s', act(restarts=[NOW - 100, NOW - 50]) == 'wait' and act(restarts=[NOW - 100, NOW - 61]) == 'restart')
six = [NOW - (i + 1) * 240 for i in range(B.MAX_RESTARTS)]
ok('six in window fail', act(restarts=six) == 'fail')
ok('old restarts do not count', act(restarts=[NOW - 31 * 60] * 6) == 'restart')


def dead_pid():
    p = subprocess.Popen([sys.executable, '-c', ''])
    p.wait()
    return p.pid


def run(rid, pid, state='running', rows=None, spent=0, age=600, **meta):
    """Write one agent checkpoint and age it."""
    m = dict(dict(task=rid, cwd=T, pid=pid, budget=1000), **meta)
    tzagent.checkpoint(rid, rows or [], m, spent, state)
    f = os.path.join(tzagent.STATE, 'agent', rid + '.json')
    os.utime(f, (time.time() - age,) * 2)


def reset():
    shutil.rmtree(tzagent.STATE, ignore_errors=True)
    os.makedirs(tzagent.STATE)


launched = []
go = lambda rid, cwd: launched.append(rid)
me = os.getpid()
gone = dead_pid()
# upstream: one watcher pass
reset(); run('old', gone)
ok('never seen alive: left alone', B.check(start=go) == [] and B.check(start=go) == [] and not launched)
reset()
for n in range(1, 6):
    run('a%d' % n, me)
B.check(start=go)
for n in range(1, 6):
    run('a%d' % n, gone)
dry = B.check(start=go, dry=True)
ok('dry reports without launching or saving', len(dry) == 3 and not launched and all(v['seen'] for v in B.load().values()))
first = B.check(start=go)
ok('3 per pass', len(first) == 3 and len(launched) == 3)
ok('then the other 2', len(B.check(start=go)) == 2 and len(launched) == 5)
ok('not relaunched until seen again', B.check(start=go) == [])
ok('restart recorded', len(B.load()['a1']['restarts']) == 1 and not B.load()['a1']['seen'])

reset(); run('x', me); B.check(start=go)
st = B.load(); st['x']['restarts'] = [time.time() - (i + 1) * 60 for i in range(B.MAX_RESTARTS)]; B._save(st)
run('x', gone); del launched[:]
ok('too many crashes: failed, no launch', B.check(start=go) == [{'run': 'x', 'did': 'failed'}] and not launched)
ok('stays down, told once', B.check(start=go) == [] and B.failed() == ['x'])
run('x', me); B.check(start=go)
ok('a person starting it clears the failure', B.failed() == [] and len(B.load()['x']['restarts']) == 6)
run('x', me, state='done'); B.check(start=go)
ok('finished run forgotten', 'x' not in B.load())

reset(); run('e', me); B.check(start=go); run('e', gone)
def boom(rid, cwd):
    raise OSError('no exec')
ok('launch error reported and counted', B.check(start=boom) == [{'run': 'e', 'did': 'restart-failed'}] and len(B.load()['e']['restarts']) == 1)
reset(); run('q', me); B.check(start=go); run('q', gone, age=5)
ok('fresh checkpoint waits', B.check(start=go) == [])
run('q', gone, cwd=os.path.join(T, 'nope'))
ok('missing work dir left alone', B.check(start=go) == [])
run('q', gone)
open(B._file('backoff.lock'), 'w').close()
ok('locked pass does nothing', B.check(start=go) == [])
os.utime(B._file('backoff.lock'), (time.time() - 999,) * 2)
ok('stale lock taken over', len(B.check(start=go)) == 1 and not os.path.exists(B._file('backoff.lock')))

# TZ: tz agent returned on its own but left 'running'
cases = {'phase error': dict(rows=[{'status': 'error'}]), 'budget spent': dict(spent=1000), 'wall limit set': dict(wall=60),
         'error limit': dict(rows=[{'status': 'error'}, {'status': 'error'}], max_errors=2), 'stopped state': dict(state='stopped')}
for name, kw in cases.items():
    reset(); run('r', me); B.check(start=go); run('r', gone, **kw)
    ok(name + ' is not a crash', B.check(start=go) == [])
reset(); run('r', me); B.check(start=go); run('r', gone, rows=[{'status': 'error'}], max_errors=3)
ok('crash while retrying under the error limit restarts', len(B.check(start=go)) == 1)

# worker bookkeeping
pg = os.path.join(tzworkers.STATE, 'pg')
r = tzworkers.run_pg([sys.executable, '-c', 'print(1)'], None, 20)
ok('run_pg output unchanged, marker removed', r.stdout.strip() == '1' and os.listdir(pg) == [])
kw = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
orphan = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], **kw)
reset(); run('o', me); B.check(start=go); run('o', gone)
tzworkers._mark('%d-%d' % (gone, orphan.pid))
ok('live orphan worker blocks restart', B.check(start=go) == [] and tzworkers.children_alive(gone) == [orphan.pid])
orphan.kill(); orphan.wait()
run('o', gone)
ok('restarts once the orphan is dead', len(B.check(start=go)) == 1 and os.listdir(pg) == [])

real, seen_pid = subprocess.Popen.communicate, []
def interrupted(self, *a, **k):
    if not seen_pid:
        seen_pid.append(self)
        raise KeyboardInterrupt
    return real(self, *a, **k)
subprocess.Popen.communicate = interrupted
try:
    tzworkers.run_pg([sys.executable, '-c', 'import time; time.sleep(30)'], None, 20)
    got = False
except KeyboardInterrupt:
    got = True
finally:
    subprocess.Popen.communicate = real
ok('Ctrl-C re-raised and worker killed', got and seen_pid[0].poll() is not None)
ok('Ctrl-C marked as quit', tzworkers.quit_marked(me))
ok('quit run is ended', B.record({'meta': {'pid': me}, 'rows': [], 'state': 'running'}, NOW)['status'] == 'ended')
tzworkers.run_pg([sys.executable, '-c', ''], None, 20)
ok('next call clears a stale quit mark', not tzworkers.quit_marked(me))

# real restart: detached tz agent resumes the checkpoint with a fake host
fake = os.path.join(T, 'fake.py')
open(fake, 'w').write('#!%s\nimport json\nprint(json.dumps({"type": "result", "result": "ok", "usage": {"input_tokens": 1, "output_tokens": 1}}))\n' % sys.executable)
os.chmod(fake, 0o755)
os.environ['CLAUDE_BIN'] = fake
reset(); run('real', me, budget=100000, turns=2, timeout=30); B.check()
run('real', gone, budget=100000, turns=2, timeout=30)
got = B.check()
for p in B._kids:
    p.wait(60)
cp = tzagent.load_run('real')[1]
ok('real restart resumes to done', got == [{'run': 'real', 'did': 'restarted'}] and cp['state'] == 'done' and cp['meta']['pid'] != gone)

# supervisor wiring: off by default, on with the feature
reset(); run('s', me)
tzsup.tick(None, T)
ok('default off: no pass', not os.path.exists(B._file('backoff.json')))
os.environ['TZ_FEAT_CRASH_RESTART'] = '1'
s = tzsup.tick(None, T)
ok('feature on: tick runs a pass', B.load().get('s', {}).get('seen') is True and s['crash_failed'] == [])
cli = lambda *a: subprocess.run([sys.executable, os.path.join(Z, 'bin', 'tzsup.py'), 'restart', *a], capture_output=True, text=True, timeout=30)
r = cli('list')
ok('tz sup restart list', r.returncode == 0 and '0 restart(s)' in r.stdout and '[actual]' in r.stdout)
ok('tz sup restart check --dry', cli('check', '--dry').returncode == 0)
ok('bad --every is usage', cli('watch', '--every', 'x').returncode == 2)
shutil.rmtree(T, ignore_errors=True)
done()
