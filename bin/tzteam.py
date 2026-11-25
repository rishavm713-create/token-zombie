#!/usr/bin/env python3
# `tz team`: staged flow plan>prd>exec>verify>fix with killed-run recovery and a fresh-evidence verify gate.
# adapted from Yeachan-Heo/oh-my-claudecode src/hooks/team-pipeline/{transitions,state}.ts, src/team/task-recovery-checkpoint.ts,
# src/team/recovery-saga.ts, src/team/state/tasks.ts, src/team/git-worktree.ts, src/features/verification/index.ts, agents/verifier.md
# (MIT, Copyright (c) 2025 Yeachan Heo), see NOTICE. Ported to stdlib Python; no tmux, tasks run one at a time.
import hashlib, json, os, re, subprocess, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STATE = os.path.expanduser('~/.claude/token-zombie')
LEASE = 15 * 60  # task claim lease; renewed by every checkpoint
MAX_AGE = 5 * 60  # command evidence older than this proves nothing
MAX_CKPT = 64 * 1024
MAX_ITER = 25  # hard cap on stage calls per run, so kill/resume cycles cannot loop forever
ALLOWED = {'plan': ('prd', 'failed'), 'prd': ('exec', 'failed'), 'exec': ('verify', 'failed'),
           'verify': ('complete', 'fix', 'failed'), 'fix': ('fix', 'verify', 'failed'),
           'complete': (), 'failed': (), 'cancelled': ('plan', 'exec')}
TERMINAL = ('complete', 'failed', 'cancelled')
ID = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,39}')
HEDGE = re.compile(r'\b(should|probably|seems?|likely|presumably)\b', re.I)
NOISE = re.compile(r'(^|/)(__pycache__|\.pytest_cache|node_modules|\.git)(/|$)|\.pyc$')


class Stop(Exception):
    """The drive loop must end now; the run stays resumable unless its phase is terminal."""


def _write(path, data):
    """Atomic JSON write."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = '%s.%d.tmp' % (path, os.getpid())
    with open(tmp, 'w') as h:
        json.dump(data, h)
    os.replace(tmp, path)


def run_dir(rid):
    """State folder of one run; rejects ids that could leave the state root."""
    if not ID.fullmatch(rid or ''):
        raise ValueError('bad run id')
    return os.path.join(STATE, 'team', rid)


def save(s):
    _write(os.path.join(run_dir(s['rid']), 'state.json'), s)


def load(rid):
    """State dict or None; a corrupt file is moved aside, never silently reused."""
    if rid == 'last':
        d = os.path.join(STATE, 'team')
        have = [x for x in (os.listdir(d) if os.path.isdir(d) else []) if os.path.isfile(os.path.join(d, x, 'state.json'))]
        if not have:
            return None
        rid = max(have, key=lambda x: os.path.getmtime(os.path.join(d, x, 'state.json')))
    p = os.path.join(run_dir(rid), 'state.json')
    try:
        with open(p) as h:
            s = json.load(h)
        if s['rid'] != rid or s['phase'] not in ALLOWED or not isinstance(s['tasks'], list):
            raise KeyError('state')
        return s
    except FileNotFoundError:
        return None
    except (ValueError, KeyError, TypeError):
        os.replace(p, p + '.corrupt')
        return None


def transition(s, to, reason=''):
    """Guarded phase change. Returns '' on success, else why it is refused (state untouched)."""
    if to == s['phase'] and to != 'fix':
        return ''
    if to not in ALLOWED[s['phase']]:
        return 'illegal transition: %s -> %s' % (s['phase'], to)
    if to == 'exec' and not (s['artifacts'].get('plan_path') or s['artifacts'].get('prd_path')):
        return 'exec requires a plan or prd artifact'
    if to == 'verify' and (not s['tasks'] or any(t['status'] != 'completed' for t in s['tasks'])):
        return 'verify requires at least one task and all tasks completed'
    if to == 'fix':
        s['fix']['attempt'] += 1
        if s['fix']['attempt'] > s['fix']['max']:
            to, reason = 'failed', 'fix loop exceeded %d attempt(s): %s' % (s['fix']['max'], s['fix']['last'])
    s['phase'] = to
    s['history'].append({'phase': to, 'at': time.time(), 'reason': reason[:400]})
    return ''


# ---- checkpoints (immutable per sequence, hashed, fail closed) ----

def _canon(v):
    return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def _sha(text):
    return hashlib.sha256(text.encode('utf-8', 'surrogatepass')).hexdigest()


def _ckdir(rid, tid, token):
    if not ID.fullmatch(tid):
        raise ValueError('bad task id')
    return os.path.join(run_dir(rid), 'checkpoints', tid, _sha(token)[:32])


def publish(rid, task, seq, payload):
    """Write checkpoint `seq` once. Returns 'created', 'replayed', 'conflict' or 'invalid'."""
    try:
        body = _canon(payload)
    except (TypeError, ValueError):
        return 'invalid'
    if len(body.encode('utf-8', 'surrogatepass')) > MAX_CKPT or not isinstance(seq, int) or seq < 1 or not task.get('token'):
        return 'invalid'
    d = _ckdir(rid, task['id'], task['token'])
    path = os.path.join(d, '%d.json' % seq)
    new = dict(schema=1, task=task['id'], seq=seq, version=task['version'], token=task['token'], payload=payload, sha=_sha(body))
    tmp = os.path.join(d, uuid.uuid4().hex + '.tmp')
    _write(tmp, new)
    try:
        try:
            os.link(tmp, path)  # atomic and never overwrites
            return 'created'
        except FileExistsError:
            pass
        except OSError:  # filesystem without hard links
            if not os.path.exists(path):
                os.replace(tmp, path)
                return 'created'
        old = _read_ck(path)
        return 'replayed' if old and all(old[k] == new[k] for k in ('task', 'seq', 'version', 'token', 'sha')) else 'conflict'
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _read_ck(path):
    """Parsed checkpoint, or None when malformed or its payload hash does not match."""
    try:
        with open(path) as h:
            c = json.load(h)
        ok = c['schema'] == 1 and isinstance(c['seq'], int) and c['seq'] > 0 and c['sha'] == _sha(_canon(c['payload']))
        return c if ok and os.path.basename(path) == '%d.json' % c['seq'] and {'task', 'version', 'token'} <= set(c) else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def select(rid, task):
    """Latest valid checkpoint of a claimed task: (checkpoint, '') or (None, 'stale'|'missing'|'malformed'). One bad file fails all."""
    if not task.get('token'):
        return None, 'stale'
    d = _ckdir(rid, task['id'], task['token'])
    names = [n for n in (os.listdir(d) if os.path.isdir(d) else []) if re.fullmatch(r'\d+\.json', n)]
    if not names:
        return None, 'missing'
    all_ = [_read_ck(os.path.join(d, n)) for n in names]
    if any(c is None for c in all_):
        return None, 'malformed'
    mine = [c for c in all_ if (c['task'], c['version'], c['token']) == (task['id'], task['version'], task['token'])]
    return (max(mine, key=lambda c: c['seq']), '') if mine else (None, 'stale')


# ---- claims and recovery ----

def liveness(pid):
    """'alive' | 'dead' | 'unknown'. A missing pid is unknown, and unknown is never treated as dead."""
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return 'unknown'
    from tzlive import pid_alive
    return 'alive' if pid_alive(pid) else 'dead'


def claim_ready(s, task):
    """Pending with every dependency completed."""
    done = {t['id'] for t in s['tasks'] if t['status'] == 'completed'}
    return task['status'] == 'pending' and set(task['deps']) <= done


def claim(s, task, now):
    """pending -> in_progress under a fresh token. The first checkpoint is on disk before the state names the claim."""
    if not claim_ready(s, task):
        return False
    task.update(status='in_progress', token=uuid.uuid4().hex, version=task['version'] + 1, pid=os.getpid(), until=now + LEASE, seq=1)
    if publish(s['rid'], task, 1, {'tz_claim': True, 'previous': task.get('resume')}) != 'created':
        raise OSError('cannot write the first checkpoint of task ' + task['id'])
    save(s)
    return True


def saved(payload):
    """Resume data of a checkpoint: a bare claim marker stands for the data saved before it."""
    return payload.get('previous') if isinstance(payload, dict) and payload.get('tz_claim') else payload


def checkpointer(s, task, now):
    """Callback handed to the executor: persists resume data and renews the lease. Dead claims are refused."""
    token = task['token']

    def put(payload):
        if task['status'] != 'in_progress' or task.get('token') != token:
            raise ValueError('claim_conflict')
        if task['until'] <= now():
            raise ValueError('lease_expired')
        if len(_canon(payload).encode('utf-8', 'surrogatepass')) > MAX_CKPT - 128:  # room for the next claim marker
            raise ValueError('invalid_checkpoint')
        r = publish(s['rid'], task, task['seq'] + 1, payload)
        if r not in ('created', 'replayed'):
            raise ValueError(r + '_checkpoint')
        task['seq'] += 1
        task['until'] = now() + LEASE
        save(s)
    return put


def recover(s, live=liveness, now=time.time):
    """Requeue tasks orphaned by a killed run. Order: liveness, validate ALL checkpoints, then one atomic write.
    Returns '' or an error code; on any error nothing is written."""
    owned = [t for t in s['tasks'] if t['status'] == 'in_progress']
    for t in owned:
        state = live(t.get('pid'))
        if state == 'unknown':
            return 'worker_liveness_unknown'
        if state == 'alive' and (t.get('until') or 0) > now():  # an expired lease covers pid reuse
            return 'already_running'
    picked = []
    for t in owned:
        c, err = select(s['rid'], t)
        if err:
            return 'checkpoint_%s:%s' % (err, t['id'])
        picked.append((t, c['payload']))
    for t, payload in picked:
        t.update(status='pending', token=None, pid=None, until=0, version=t['version'] + 1, resume=saved(payload), recovered=True)
    if picked:
        save(s)
    return ''


def hold(rid):
    """Exclusive per-run OS lock (freed by the kernel when the holder dies). None when another process drives the run."""
    os.makedirs(run_dir(rid), exist_ok=True)
    h = open(os.path.join(run_dir(rid), 'lock'), 'a+')
    try:
        if os.name == 'nt':
            import msvcrt
            h.seek(0); msvcrt.locking(h.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(h, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        h.close()
        return None
    return h


# ---- verify gate ----

def tree(cwd):
    """Fingerprint of the working tree: evidence is only valid for the tree it was produced on."""
    h = hashlib.sha256()
    git = lambda *a: subprocess.run(['git'] + list(a), cwd=cwd, capture_output=True)
    if git('rev-parse', '--git-dir').returncode == 0:
        h.update(git('rev-parse', 'HEAD').stdout + git('ls-files', '-s').stdout + git('diff', '--binary').stdout)
        names = git('ls-files', '-o', '-z', '--exclude-standard').stdout.decode('utf-8', 'surrogateescape').split('\0')
    else:
        names = [os.path.relpath(os.path.join(r, f), cwd) for r, _, fs in os.walk(cwd) for f in fs]
    for n in sorted(x for x in names if x and not NOISE.search(x.replace(os.sep, '/'))):
        h.update(n.encode('utf-8', 'surrogateescape') + b'\0')
        try:
            with open(os.path.join(cwd, n), 'rb') as f:
                for block in iter(lambda: f.read(1 << 20), b''):
                    h.update(block)
        except OSError:
            h.update(b'?')
    return h.hexdigest()


def shell(cmd, cwd, timeout=600):
    """Run one verification command: (exit code, output)."""
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, errors='replace', timeout=timeout)
        return p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        return 124, 'timed out after %ss' % timeout


def verdict(evidence, required, epoch, fingerprint, now, max_age=MAX_AGE):
    """('approved'|'rejected'|'incomplete', problems). Only current-epoch, same-tree, recent evidence counts."""
    if not required:
        return 'incomplete', ['no verification command']
    gaps, fails = [], []
    for name in required:
        e = next((x for x in reversed(evidence) if x.get('check') == name), None)
        if not e:
            gaps.append(name + ': missing evidence')
        elif e.get('epoch') != epoch or e.get('tree') != fingerprint or not 0 <= now - e.get('at', 0) <= max_age:
            gaps.append(name + ': stale evidence')
        elif e.get('rc') != 0:
            fails.append('%s: exit %s: %s' % (name, e.get('rc'), e.get('out', '')[-800:]))
        elif name == 'tests':
            from tzgate import NOTESTS
            out = e.get('out', '')  # a match right after a digit is "10 passing", not "0 passing"
            m = next((m for m in NOTESTS.finditer(out) if not out[:m.start()][-1:].isdigit()), None)
            if m:
                fails.append('tests: exit 0 but executed no tests: ' + m.group(0))
    return ('incomplete', gaps + fails) if gaps else ('rejected', fails) if fails else ('approved', [])


def criteria(s):
    """{criterion id: text} across all tasks."""
    return {'%s:%d' % (t['id'], i + 1): c for t in s['tasks'] for i, c in enumerate(t['criteria'])}


def judge_review(report, want):
    """Problems in a verifier report: every criterion needs VERIFIED plus concrete, unhedged evidence."""
    rows = {str(r.get('id')): r for r in report.get('criteria', []) if isinstance(r, dict)}
    out = []
    for cid, text in want.items():
        r = rows.get(cid)
        ev = str((r or {}).get('evidence') or '').strip()
        if not r or str(r.get('status')).upper() != 'VERIFIED':
            out.append('%s %s: %s %s' % (cid, text, r.get('status') if r else 'MISSING', ev[:200]))
        elif not ev or HEDGE.search(re.sub(r'(["\'`]).*?\1', '', ev)):  # quoted test names may say "should"
            out.append('%s %s: no firm evidence' % (cid, text))
    return out


def json_block(text):
    """First JSON object in a model reply (fenced or bare), or None."""
    dec = json.JSONDecoder()
    for m in re.finditer(r'\{', text or ''):
        try:
            v = dec.raw_decode(text[m.start():])[0]
        except ValueError:
            continue
        if isinstance(v, dict) and ('tasks' in v or 'criteria' in v):
            return v
    return None


def parse_prd(text):
    """(tasks, '') or (None, why). Every task needs acceptance criteria; ids unique; dependencies known and acyclic."""
    raw = (json_block(text) or {}).get('tasks')
    if not isinstance(raw, list) or not raw:
        return None, 'no tasks list'
    out = []
    for t in raw:
        if not isinstance(t, dict) or not ID.fullmatch(str(t.get('id', ''))) or not str(t.get('title', '')).strip():
            return None, 'task needs a safe id and a title'
        crit, deps = t.get('criteria'), t.get('deps') or []
        if not isinstance(crit, list) or not crit or not all(isinstance(c, str) and c.strip() for c in crit):
            return None, 'task %s has no acceptance criteria' % t['id']
        if not isinstance(deps, list):
            return None, 'task %s deps must be a list' % t['id']
        out.append(dict(id=str(t['id']), title=str(t['title']), criteria=crit, deps=[str(d) for d in deps],
                        status='pending', token=None, version=0, attempts=0, resume=None))
    ids = [t['id'] for t in out]
    if len(set(x.lower() for x in ids)) != len(ids):  # ids name folders; macOS and Windows ignore case
        return None, 'duplicate task id'
    done = set()
    while len(done) < len(ids):
        ready = {t['id'] for t in out if t['id'] not in done and set(t['deps']) <= done}
        if not ready:
            return None, 'unknown or cyclic dependency'
        done |= ready
    return out, ''


# ---- drive ----

PROMPTS = {
    'plan': 'Plan this task: smallest set of steps, files to touch, risks. Do not edit files.',
    'prd': 'Turn the plan into tasks. Reply with ONLY JSON: {"tasks":[{"id":"t1","title":"..","criteria":["testable statement"],"deps":[]}]}. Do not edit files.',
    'exec': 'Implement only this task and meet its acceptance criteria. Do not widen scope.',
    'verify': 'You are an independent verifier; you did not write this change. Do not edit files. Check every criterion against the fresh output below and the code. '
              'Reply with ONLY JSON: {"criteria":[{"id":"t1:1","status":"VERIFIED|PARTIAL|MISSING","evidence":"command output or file:line"}]}.',
    'fix': 'The independent check failed. Fix only the problems listed below.'}


def _cancelled(s, flag):
    """Record a requested cancel in the state."""
    try:
        with open(flag) as h:
            s['preserve'] = bool(json.load(h).get('preserve', True))
    except (OSError, ValueError, AttributeError):
        s['preserve'] = True
    if s['phase'] != 'cancelled':
        s['phase'] = 'cancelled'
        s['history'].append({'phase': 'cancelled', 'at': time.time(), 'reason': 'cancel requested'})


def _call(s, env, stage, prompt, **extra):
    """One bounded executor call. Limits are checked first; the call is counted and saved before it runs."""
    flag = os.path.join(run_dir(s['rid']), 'cancel.json')
    if os.path.exists(flag):
        _cancelled(s, flag)
        raise Stop('cancelled')
    if s['spent'] >= s['budget']:
        raise Stop('budget')
    if s['opts'].get('wall') and env['now']() - env['start'] >= s['opts']['wall']:
        raise Stop('time')
    if s['iteration'] >= s['max_iterations']:
        transition(s, 'failed', 'max iterations reached')
        raise Stop('max_iterations')
    s['iteration'] += 1
    save(s)
    ctx = dict(stage=stage, task=s['task'], cwd=s['cwd'], opts=s['opts'], prompt='%s\nTask: %s\n%s' % (PROMPTS[stage], s['task'], prompt),
               item=None, resume=None, checkpoint=None)
    ctx.update(extra)
    try:
        r = env['executor'](stage, ctx)
        if r.get('measured') is False:
            s['est'] = True
        r = {'text': str(r.get('text') or ''), 'tokens': int(r.get('tokens') or 0), 'error': str(r.get('error') or '')}
    except Exception as e:  # a crash that is not a kill counts as a failed call; KeyboardInterrupt/SystemExit pass through
        r = {'text': '', 'tokens': 0, 'error': '%s: %s' % (type(e).__name__, e)}
    s['spent'] += r['tokens']  # failed calls were billed too
    return r


def _bad(s, why):
    """Count consecutive failed calls; give up at the limit."""
    s['errors'] += 1
    if s['errors'] >= s['opts']['max_errors']:
        transition(s, 'failed', '%d failed call(s) in a row: %s' % (s['errors'], why))
    save(s)


def _artifact(s, key, name, text):
    p = os.path.join(run_dir(s['rid']), name)
    with open(p, 'w', encoding='utf-8', errors='replace') as h:
        h.write(text)
    s['artifacts'][key] = p


def _read(s, key):
    with open(s['artifacts'][key], encoding='utf-8') as h:
        return h.read()[:12000]


def do_plan(s, env):
    r = _call(s, env, 'plan', '')
    if r['error'] or not r['text'].strip():
        return _bad(s, r['error'] or 'empty plan')
    _artifact(s, 'plan_path', 'plan.md', r['text'])
    s['errors'] = 0
    transition(s, 'prd')


def do_prd(s, env):
    r = _call(s, env, 'prd', 'Plan:\n%s\n%s' % (_read(s, 'plan_path'), s.get('prd_note', '')))
    tasks, why = (None, r['error']) if r['error'] else parse_prd(r['text'])
    if not tasks:
        s['prd_note'] = 'The previous reply was rejected: ' + why
        return _bad(s, why)
    _artifact(s, 'prd_path', 'prd.json', json.dumps({'tasks': tasks}, indent=1))
    s.update(tasks=tasks, errors=0)
    transition(s, 'exec')


def do_exec(s, env):
    now = env['now']
    while True:
        t = next((t for t in s['tasks'] if claim_ready(s, t)), None)
        if not t:
            break
        claim(s, t, now())
        note = '\nTask %s: %s\nAcceptance criteria:\n- %s' % (t['id'], t['title'], '\n- '.join(t['criteria']))
        if t.get('recovered') or t['attempts']:
            note += '\nRESUMED task: inspect `git status` and `git diff` first, keep finished work. Saved progress: %s' % json.dumps(t['resume'])[:4000]
        try:
            r = _call(s, env, 'exec', note, item=dict(t), resume=t['resume'], checkpoint=checkpointer(s, t, now))
        except Stop:
            t.update(status='pending', token=None, pid=None, until=0)  # never called: give the claim back
            raise
        c = select(s['rid'], t)[0]
        t.update(token=None, pid=None, until=0, resume=saved(c['payload']) if c else t['resume'])  # a retry keeps saved progress
        if not r['error']:
            t['status'] = 'completed'
        else:
            t['attempts'] += 1
            t['status'] = 'failed' if t['attempts'] >= s['opts']['max_task_attempts'] else 'pending'
            if t['status'] == 'failed':
                save(s)
                return transition(s, 'failed', 'task %s failed %d time(s): %s' % (t['id'], t['attempts'], r['error']))
        save(s)
    why = transition(s, 'verify')
    if why:
        transition(s, 'failed', why)


def run_checks(s, env):
    """Run every required command now; all evidence is stamped with the tree left behind by the batch."""
    s['epoch'] += 1
    rows = []
    for name, key in (('tests', 'test'), ('build', 'build')):
        cmd = s['opts'].get(key)
        if cmd:
            rc, out = env['runner'](cmd, s['cwd'])
            rows.append({'check': name, 'cmd': cmd, 'rc': rc, 'out': out[-2000:], 'epoch': s['epoch']})
    fp, at = tree(s['cwd']), env['now']()
    for r in rows:
        r.update(tree=fp, at=at)
    s['evidence'] = rows
    save(s)
    return [r['check'] for r in rows]


def do_verify(s, env):
    required = run_checks(s, env)
    if not required:
        return transition(s, 'failed', 'no verification command: completion cannot be proven')
    judge = lambda: verdict(s['evidence'], required, s['epoch'], tree(s['cwd']), env['now']())
    v, problems = judge()
    if v == 'approved' and s['opts']['review']:
        want = criteria(s)
        outputs = '\n'.join('$ %s (exit %s)\n%s' % (e['cmd'], e['rc'], e['out'][-1200:]) for e in s['evidence'])
        before = tree(s['cwd'])
        r = _call(s, env, 'verify', 'Criteria: %s\nFresh output:\n%s' % (json.dumps(want), outputs))
        report = None if r['error'] else json_block(r['text'])
        if not report or not isinstance(report.get('criteria'), list):
            return _bad(s, r['error'] or 'unreadable verifier report')  # retry verify; a code fix cannot repair a report
        if tree(s['cwd']) != before:
            return _bad(s, 'tree changed during review')
        required = run_checks(s, env)  # the review may have taken longer than the evidence lives
        v, problems = judge()
        bad = judge_review(report, want)
        if v == 'approved' and bad:
            v, problems = 'rejected', bad
    _artifact(s, 'verify_report_path', 'verify.json', json.dumps({'verdict': v, 'problems': problems, 'evidence': s['evidence']}, indent=1))
    if v == 'approved':
        s['errors'] = 0
        return transition(s, 'complete')
    if v == 'incomplete':
        return _bad(s, '; '.join(problems))
    s['errors'] = 0
    s['fix']['last'] = '; '.join(problems)[:3000]
    transition(s, 'fix', s['fix']['last'])


def do_fix(s, env):
    r = _call(s, env, 'fix', 'Problems:\n' + s['fix']['last'])
    s['epoch'] += 1  # code changed (or may have): older evidence is void
    if r['error']:
        why = 'fix call failed: ' + r['error']
        s['fix']['last'] = (s['fix']['last'] + '\n' + why)[-3000:]
        return transition(s, 'fix', why)  # a failed fix uses up an attempt
    transition(s, 'verify')


STAGES = {'plan': do_plan, 'prd': do_prd, 'exec': do_exec, 'verify': do_verify, 'fix': do_fix}


def new_run(task, cwd, test=None, build=None, budget=400000, max_fix=None, review=True, max_errors=2, max_task_attempts=2, **opts):
    """Create and save a run in phase 'plan'."""
    from tzgate import MAX_REPAIRS
    rid = '%s-%d-%s' % (re.sub(r'[^a-z0-9]+', '-', task.lower()).strip('-')[:20] or 'team', int(time.time()), uuid.uuid4().hex[:4])
    s = dict(schema=1, rid=rid, task=task, cwd=os.path.abspath(cwd), phase='plan', history=[{'phase': 'plan', 'at': time.time(), 'reason': ''}],
             iteration=0, max_iterations=MAX_ITER, spent=0, budget=budget, errors=0, epoch=0, evidence=[], tasks=[], stop='',
             fix={'attempt': 0, 'max': MAX_REPAIRS if max_fix is None else max_fix, 'last': ''},
             artifacts={'plan_path': None, 'prd_path': None, 'verify_report_path': None},
             opts=dict(opts, test=test, build=build, review=review, max_errors=max_errors, max_task_attempts=max_task_attempts))
    save(s)
    return s


def drive(rid, executor, runner=shell, live=liveness, now=time.time, budget=None):
    """Run or resume until complete, failed, cancelled or a limit. Returns (state, stop reason); state None if unreadable."""
    first = load(rid)
    if not first:
        return None, 'no_run'
    h = hold(first['rid'])
    if not h:
        return first, 'already_running'
    try:
        s = load(first['rid'])
        flag = os.path.join(run_dir(s['rid']), 'cancel.json')
        if s['phase'] == 'cancelled':
            if not s.get('preserve', True):
                return s, 'cancelled'
            err = recover(s, live, now)
            if err:
                return s, err
            if os.path.exists(flag):
                os.remove(flag)
            transition(s, 'exec' if s['tasks'] else 'plan', 'resumed from cancelled')
        if s['phase'] in TERMINAL:
            return s, s['phase']
        err = recover(s, live, now)
        if err:
            return s, err
        if budget is not None:
            s['budget'] = budget
        env = dict(executor=executor, runner=runner, now=now, start=now())
        stop = ''
        try:
            while s['phase'] not in TERMINAL:
                STAGES[s['phase']](s, env)
                save(s)
        except Stop as e:
            stop = str(e)
        s['stop'] = stop or s['phase']
        save(s)
        return s, s['stop']
    finally:
        h.close()


def cancel(rid, preserve=True):
    """Ask a run to stop before its next call; with preserve it can be resumed."""
    s = load(rid)
    if not s or s['phase'] in ('complete', 'failed'):
        return False
    flag = os.path.join(run_dir(s['rid']), 'cancel.json')
    _write(flag, {'preserve': preserve})
    h = hold(s['rid'])
    if h:  # nobody is driving: record it now
        s = load(s['rid'])
        _cancelled(s, flag)
        save(s)
        h.close()
    return True


def safe_worktree(repo, name, root=None):
    """Isolated worktree on branch tz/<name>. Reuses only a clean matching tree; never deletes or forces.
    Raises ValueError(leader_worktree_dirty | worktree_mismatch | worktree_dirty | worktree_failed)."""
    git = lambda c, *a: subprocess.run(['git'] + list(a), cwd=c, capture_output=True, text=True)
    top = git(repo, 'rev-parse', '--show-toplevel').stdout.strip()
    if not top:
        raise ValueError('worktree_failed: not a git repository')
    if git(top, 'status', '--porcelain').stdout.strip():
        raise ValueError('leader_worktree_dirty')
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:40] or 'task'
    branch = 'tz/' + slug
    path = os.path.join(root or os.path.join(STATE, 'worktrees'), '%s-%s' % (os.path.basename(top), _sha(top)[:6]), slug)
    base = git(top, 'rev-parse', 'HEAD').stdout.strip()
    if os.path.exists(path):
        if git(path, 'branch', '--show-current').stdout.strip() != branch:
            raise ValueError('worktree_mismatch: ' + path)
        if git(path, 'status', '--porcelain').stdout.strip():
            raise ValueError('worktree_dirty: ' + path)
        return dict(path=path, branch=branch, base=git(path, 'rev-parse', 'HEAD').stdout.strip(), reused=True)
    exists = git(top, 'rev-parse', '--verify', '--quiet', 'refs/heads/' + branch).returncode == 0
    r = git(top, 'worktree', 'add', path, branch) if exists else git(top, 'worktree', 'add', '-b', branch, path)
    if r.returncode:
        raise ValueError('worktree_failed: ' + r.stderr.strip()[-300:])
    return dict(path=path, branch=branch, base=base, reused=False)


def model_executor(stage, ctx):
    """Real worker call through tzagent (paid). Only the CLI with --go uses this."""
    import tzagent, tzsplit
    phase = {'plan': 'plan', 'prd': 'plan', 'exec': 'build', 'verify': 'test', 'fix': 'debug'}[stage]
    model = {r['phase']: r['model'] for r in tzsplit.code_pipeline(ctx['task'])}.get(phase, 'sonnet')
    o = ctx['opts']
    text, tok, err, measured = tzagent.call(ctx['prompt'], model, ctx['cwd'], o.get('turns') or 20, o.get('worker'), o.get('timeout') or 1800, stage in ('exec', 'fix'))
    return {'text': text, 'tokens': tok, 'error': err, 'measured': measured}


def report(s, stop=''):
    """Short human status."""
    out = ['team %s: %s%s' % (s['rid'], s['phase'], ' (stopped: %s)' % stop if stop and stop != s['phase'] else ''),
           'tokens %d [%s] of %d budget | calls %d | fix %d/%d' % (
               s['spent'], 'est' if s.get('est') else 'actual', s['budget'], s['iteration'], min(s['fix']['attempt'], s['fix']['max']), s['fix']['max'])]
    out += ['  %s %s: %s' % (t['status'], t['id'], t['title'][:70]) for t in s['tasks']]
    if s['phase'] in ('failed', 'cancelled') and s['history']:
        out.append('reason: ' + s['history'][-1]['reason'])
    return '\n'.join(out)


USAGE = '''usage: tz team "TASK" --test CMD [--build CMD] [--go] [--budget N] [--max-fix N] [--worker W] [--turns N] [--timeout S] [--wall S] [--worktree] [--no-review]
       tz team --resume ID|last [--go] [--budget N]    tz team status [ID]    tz team cancel [ID]
Without --go nothing is called or written (dry run).'''


def main(argv):
    argv = argv[1:] if argv[:1] == ['team'] else argv
    valued = ('--test', '--build', '--budget', '--max-fix', '--worker', '--turns', '--timeout', '--wall', '--resume')
    opt, words, flags, i = {}, [], set(), 0
    while i < len(argv):
        a = argv[i]
        if a in valued:
            if i + 1 >= len(argv):
                print(USAGE, file=sys.stderr); return 2
            opt[a[2:].replace('-', '_')] = argv[i + 1]; i += 1
        elif a.startswith('--'):
            flags.add(a)
        else:
            words.append(a)
        i += 1
    if flags - {'--go', '--worktree', '--no-review'}:
        print(USAGE, file=sys.stderr); return 2
    try:
        for k in ('budget', 'max_fix', 'turns', 'timeout', 'wall'):
            if k in opt:
                opt[k] = int(opt[k])
        if words[:1] in (['status'], ['cancel']) and len(words) <= 2:
            rid = words[1] if len(words) == 2 else 'last'
            s = load(rid)
            if not s:
                print('no team run ' + rid, file=sys.stderr); return 2
            if words[0] == 'cancel':
                print('cancel requested' if cancel(s['rid']) else 'run already finished')
            else:
                print(report(s, s.get('stop', '')))
            return 0
        rid = opt.pop('resume', None)
        task = ' '.join(words)
        if not rid and not (task and (opt.get('test') or opt.get('build'))):
            print(USAGE, file=sys.stderr); return 2
        if '--go' not in flags:
            print('dry run (add --go to call the worker): plan > prd > exec > verify > fix; complete only when fresh check output passes'); return 0
        if not rid:
            cwd = os.getcwd()
            if '--worktree' in flags:
                cwd = safe_worktree(cwd, task)['path']
            rid = new_run(task, cwd, review='--no-review' not in flags, **opt)['rid']
            print('run ' + rid, flush=True)
        s, stop = drive(rid, model_executor, budget=opt.get('budget'))
    except ValueError as e:
        print(str(e), file=sys.stderr); return 2
    if not s:
        print('no readable team run ' + rid, file=sys.stderr); return 2
    print(report(s, stop))
    return 0 if s['phase'] == 'complete' and stop == 'complete' else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
