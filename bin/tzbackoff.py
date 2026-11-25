#!/usr/bin/env python3
# `tz sup restart`: restart a crashed `tz agent` run in the same checkpoint, with backoff; give up after too many crashes.
# adapted from 23blocks-OS/ai-maestro lib/crash-restart.ts and services/crash-restart-service.ts
# (MIT, Copyright (c) 2025 Juan Peláez / 23blocks), see NOTICE. Ported to stdlib Python; times are seconds.
# TZ mapping: "agent at a bare shell" = checkpoint state 'running' with the run and its workers dead.
# Automatic passes (from tzsup.tick) need feature crash_restart (default OFF): a restart spends model tokens.
import json, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tzagent, tzworkers
from tzlive import pid_alive

WINDOW = 30 * 60
MAX_RESTARTS = 6
QUIET = 60  # the checkpoint must be untouched this long: someone resuming by hand is never raced
BACKOFF = (0, 30, 60, 120, 240, 300)
MAX_PER_PASS = 3  # one bad host update must not restart every run at once
LOCK_STALE = 120
_kids = []  # restarts spawned by this process; polled so a dead one is not a zombie that looks alive


def crash_action(at_shell, record, restarts, failed, now, last_activity=None):
    """Decide none | wait | restart | fail for one run; pure, no I/O."""
    if not at_shell:
        return {'action': 'none', 'why': 'the run is alive'}
    if failed:
        return {'action': 'none', 'why': 'marked failed; a person starts it'}
    if not record:
        return {'action': 'none', 'why': 'no process ever reported for this run'}
    if record.get('status') == 'ended':
        return {'action': 'none', 'why': 'the run ended or was stopped on purpose'}
    if last_activity is not None and now - last_activity < QUIET:
        return {'action': 'none', 'why': 'the checkpoint changed under %ss ago' % QUIET}
    recent = sorted(t for t in restarts if now - t < WINDOW)
    if len(recent) >= MAX_RESTARTS:
        return {'action': 'fail', 'restarts': recent}
    if recent:
        until = recent[-1] + BACKOFF[min(len(recent), len(BACKOFF) - 1)]
        if now < until:
            return {'action': 'wait', 'until': until}
    return {'action': 'restart', 'restarts': recent + [now]}


def _file(name):
    return os.path.join(tzagent.STATE, name)


def load():
    """Per-run restart history {run: {seen, restarts, failed}}; unreadable -> empty (nothing is restarted unseen)."""
    try:
        d = json.load(open(_file('backoff.json')))
        return {k: v for k, v in d.items() if isinstance(v, dict) and isinstance(v.get('restarts'), list)}
    except Exception:
        return {}


def _save(st):
    f = _file('backoff.json')
    json.dump(st, open(f + '.tmp', 'w'), indent=1)
    os.replace(f + '.tmp', f)


def _lock():
    """True if this process owns the pass; two hooks firing together must not spawn the same run twice."""
    f = _file('backoff.lock')
    os.makedirs(tzagent.STATE, exist_ok=True)
    for _ in range(2):
        try:
            os.close(os.open(f, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return True
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(f) < LOCK_STALE:
                    return False
                os.remove(f)
            except OSError:
                return False
    return False


def runs():
    """(run id, checkpoint, mtime) for every readable agent checkpoint."""
    d = _file('agent')
    for x in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if not x.endswith('.json'):
            continue
        try:
            f = os.path.join(d, x)
            cp = json.load(open(f))
            if isinstance(cp['meta'], dict) and isinstance(cp['rows'], list):
                yield x[:-5], cp, os.path.getmtime(f)
        except Exception:
            continue


def _returned(cp):
    """True when tz agent returned on its own but left state 'running' (failed plan/build or a limit): not a crash."""
    m, rows = cp['meta'], cp['rows']
    if m.get('wall'):  # a resume restarts the wall clock, and a wall stop cannot be told from a crash
        return True
    if m.get('budget') and cp.get('spent', 0) >= m['budget']:
        return True
    errors = sum(1 for r in rows if r.get('status') == 'error')
    if rows and rows[-1].get('status') == 'error':
        return not m.get('max_errors') or errors >= m['max_errors']
    return False


def record(cp, mtime):
    """Upstream's 'last hook record': None, or {status: running|ended, at}."""
    pid = cp['meta'].get('pid')
    if not pid:
        return None
    ended = cp.get('state') != 'running' or tzworkers.quit_marked(pid) or _returned(cp)
    return {'status': 'ended' if ended else 'running', 'at': mtime}


def running(cp):
    """The run process or one of its worker process groups is still alive (an orphan may still be editing files)."""
    pid = cp['meta'].get('pid')
    return bool(pid) and (pid_alive(pid) or bool(tzworkers.children_alive(pid)))


def spawn(rid, cwd):
    """Detached `tz agent --resume RID`; output goes to <run>.restart.log."""
    kw = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
    with open(os.path.join(_file('agent'), rid + '.restart.log'), 'a') as log:
        _kids.append(subprocess.Popen([sys.executable, os.path.abspath(tzagent.__file__), '--resume', rid], cwd=cwd,
                                      stdin=subprocess.DEVNULL, stdout=log, stderr=log, **kw))


def _one(rid, cp, mtime, st, now, start, dry):
    """Handle one run inside a pass; returns 'restarted' | 'restart-failed' | 'failed' | None."""
    if cp.get('state') != 'running':
        st.pop(rid, None)
        return None
    e = st.get(rid)
    if running(cp):  # seen alive; a person starting a failed run again clears the failure
        st[rid] = {'seen': True, 'restarts': e['restarts'] if e else [], 'failed': None}
        return None
    # only a run an earlier pass saw alive: one that crashed days ago is left as it is
    if not e or not e.get('seen') or not os.path.isdir(cp['meta'].get('cwd') or ''):
        return None
    a = crash_action(True, record(cp, mtime), e['restarts'], bool(e.get('failed')), now, mtime)
    if a['action'] == 'fail':
        e.update(failed=now, restarts=a['restarts'])
        return 'failed'
    if a['action'] != 'restart':
        return None
    e.update(seen=False, restarts=a['restarts'])  # seen again once the restarted run is alive
    if dry:
        return 'restarted'
    _save(st)  # history first: a crash during the launch must still count
    try:
        start(rid, cp['meta']['cwd'])
        return 'restarted'
    except OSError:
        return 'restart-failed'


def check(now=None, start=None, dry=False):
    """One pass over all runs. Returns [{run, did}]; dry reports without launching or saving."""
    _kids[:] = [p for p in _kids if p.poll() is None]
    if not dry and not _lock():
        return []
    done = []
    try:
        st = load()
        for rid, cp, mtime in runs():
            if sum(1 for d in done if d['did'] != 'failed') >= MAX_PER_PASS:
                break
            did = _one(rid, cp, mtime, st, time.time() if now is None else now, start or spawn, dry)
            if did:
                done.append({'run': rid, 'did': did})
        if not dry:
            _save(st)
    finally:
        if not dry:
            try:
                os.remove(_file('backoff.lock'))
            except OSError:
                pass
    return done


def failed():
    """Run ids given up on, until a person resumes them."""
    return sorted(k for k, v in load().items() if v.get('failed'))


def _show(now):
    """Print each unfinished run with its restart count."""
    st = load()
    rows = [(rid, cp) for rid, cp, _ in runs() if cp.get('state') == 'running']
    for rid, cp in rows:
        e = st.get(rid) or {'restarts': []}
        n = sum(1 for t in e['restarts'] if now - t < WINDOW)
        state = 'alive' if running(cp) else 'FAILED (tz agent --resume %s)' % rid if e.get('failed') else 'not running'
        print('%s: %s, %d restart(s) in %d min [actual]' % (rid, state, n, WINDOW // 60))
    if not rows:
        print('no unfinished agent runs')


def main(argv):
    """tz sup restart [check [--dry] | list | watch [--every S]]."""
    argv = argv[1:] if argv and argv[0] == 'restart' else argv
    cmd = argv[0] if argv and not argv[0].startswith('--') else 'check'
    if cmd == 'list':
        _show(time.time())
        return 0
    every = 60
    if '--every' in argv:
        v = argv[argv.index('--every') + 1:][:1]
        if not v or not v[0].isdigit() or int(v[0]) < 1:
            cmd = None
        else:
            every = int(v[0])
    if cmd not in ('check', 'watch'):
        print('usage: tz sup restart [check [--dry] | list | watch [--every SECONDS]]', file=sys.stderr)
        return 2
    try:
        while True:
            done = check(dry='--dry' in argv)
            for d in done:
                print('%s%s: %s' % ('(dry) ' if '--dry' in argv else '', d['run'], d['did']))
            if cmd == 'check':
                if not done:
                    print('nothing to restart (only runs an earlier pass saw alive are restarted)')
                return 0
            sys.stdout.flush()
            time.sleep(every)
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
