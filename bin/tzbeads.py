#!/usr/bin/env python3
"""tz next extras: hash ids, claims with a lease, parent-child / discovered-from / defer, compaction, prime, JSONL export/import.
base36 hash id + adaptive length adapted from beads internal/idgen/hash.go and internal/storage/domain/adaptive.go (MIT, Copyright (c) 2025 Beads Contributors), see NOTICE.
Claim, readiness, compaction eligibility and prime follow beads behaviour in own Python code. Local files only; no network, no model calls."""
import contextlib, hashlib, json, math, os, re, sys, time

import tznext

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
    import msvcrt

TTL = 7200  # seconds; same life as the tzcont claim board. A dead worker's claim frees itself.
COMPACT_DAYS = 30  # beads tier-1 default
PRIME_CHARS = 1500
ALPHA = '0123456789abcdefghijklmnopqrstuvwxyz'
NBYTES = {3: 2, 4: 3, 5: 4, 6: 4, 7: 5, 8: 5}


def _slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


# ---------- hash ids ----------
def base36(data, length):
    """Bytes as base36, zero padded, keeping the least significant `length` digits."""
    n, s = int.from_bytes(data, 'big'), ''
    while n:
        n, r = divmod(n, 36)
        s = ALPHA[r] + s
    return s.rjust(length, '0')[-length:]


def hash_id(prefix, title, desc, creator, ts_ns, length, nonce=0):
    """beads-compatible hash id: <prefix>-<base36 of sha256(title|desc|creator|ns|nonce)>."""
    h = hashlib.sha256(f'{title}|{desc}|{creator}|{ts_ns}|{nonce}'.encode()).digest()
    return f'{prefix}-{base36(h[:NBYTES.get(length, 3)], length)}'


def id_length(n, lo=3, hi=8):
    """Shortest id length with birthday collision probability <= 0.25 for n tasks."""
    for L in range(lo, hi + 1):
        if 1 - math.exp(-n * n / (2 * 36 ** L)) <= 0.25:
            return L
    return hi


def new_id(cwd, title, desc=''):
    """Unused tz-xxxx id. Two branches adding tasks get different ids, so a merge does not collide."""
    start = id_length(len(tznext.load(cwd)), lo=4)  # min 4: other branches' tasks are invisible here
    for L in range(start, 9):
        for nonce in range(10):
            i = hash_id('tz', title, desc, actor(cwd), time.time_ns(), L, nonce)
            if not os.path.exists(tznext._path(cwd, i)):
                return i
    raise ValueError('no free task id')


# ---------- graph: parent-child, defer ----------
def ancestors(ts, tid):
    """Parent chain of tid, nearest first (stops on a loop)."""
    out, p = [], ts.get(tid, {}).get('parent')
    while p in ts and p != tid and p not in out:
        out.append(p)
        p = ts[p].get('parent')
    return out


def graph(ts):
    """'x cannot finish before y' edges: own and inherited blockers, plus parent waits on child. A cycle = deadlock."""
    g = {}
    for k, t in ts.items():
        g[k] = list(t.get('deps', []))
        for a in ancestors(ts, k):
            g[k] += ts[a].get('deps', [])
    for k, t in ts.items():
        if t.get('parent') in g:
            g[t['parent']].append(k)
    return {k: {'deps': list(dict.fromkeys(v))} for k, v in g.items()}


def unmet(ts, t):
    """Blocking deps not yet done (a missing id counts as unmet)."""
    return [d for d in t.get('deps', []) if ts.get(d, {}).get('status') != 'done']


def hidden(ts, t):
    """Why a task with its own deps met still cannot run (defer date or parent chain); '' when it can."""
    today = time.strftime('%Y-%m-%d')
    for k in [t['id']] + ancestors(ts, t['id']):
        x = ts.get(k, t)
        if x.get('defer', '') > today:
            return f'{k} is deferred until {x["defer"]}'
        if k != t['id'] and x.get('status') == 'blocked':
            return f'parent {k} is blocked'
        if k != t['id'] and x.get('status') != 'done' and unmet(ts, x):
            return f'parent {k} waits on {", ".join(unmet(ts, x))}'
    return ''


def open_children(ts, tid):
    return sorted(k for k, v in ts.items() if v.get('parent') == tid and v['status'] != 'done')


def defer(cwd, tid, until=''):
    """Hide a task (and its children) until a YYYY-MM-DD date; empty date undoes it."""
    if until:
        try:
            until = time.strftime('%Y-%m-%d', time.strptime(until, '%Y-%m-%d'))
        except ValueError:
            return False, 'date must be YYYY-MM-DD'
    with locked(cwd):
        t = tznext.load(cwd).get(tid)
        if not t or t['status'] == 'done':
            return False, 'no such open task'
        t['defer'] = until
        if until and t['status'] == 'active':
            t['status'] = 'pending'  # deferred work is not the active task
            tznext.release(cwd, tid)
            _drop(cwd, t, actor(cwd))
        tznext.save(cwd, t)
    return True, f'deferred until {until}' if until else 'defer cleared'


# ---------- claims ----------
def actor(cwd, by=''):
    """Who is claiming: --by, TZ_ACTOR, else this checkout's path (stable across chats, distinct per worktree)."""
    return by or os.environ.get('TZ_ACTOR') or os.path.abspath(cwd)


def _shared(cwd):
    """(dir, key prefix) inside the repo's common git dir, so all worktrees see one claim board; ('', '') outside git."""
    top = os.path.abspath(cwd)
    while True:
        dot = os.path.join(top, '.git')
        if os.path.exists(dot):
            break
        if os.path.dirname(top) == top:
            return '', ''
        top = os.path.dirname(top)
    common = dot
    if os.path.isfile(dot):  # linked worktree: .git -> gitdir -> commondir
        try:
            gd = os.path.normpath(os.path.join(top, open(dot).read().split('gitdir:', 1)[1].strip()))
            common = os.path.normpath(os.path.join(gd, open(os.path.join(gd, 'commondir')).read().strip()))
        except (OSError, IndexError):
            return '', ''
    rel = os.path.relpath(os.path.abspath(cwd), top)
    return os.path.join(common, 'tz-claims'), '' if rel == '.' else _slug(rel) + '__'


def board(cwd):
    """Writable claim dir + key prefix; falls back to handoffs/tasks/.claims (no git, or .git not writable)."""
    for base, pre in (_shared(cwd), (os.path.join(tznext.tdir(cwd), '.claims'), '')):
        if base:
            try:
                os.makedirs(base, exist_ok=True)
                open(os.path.join(base, '.lock'), 'a').close()
                return base, pre
            except OSError:
                pass
    raise OSError('no writable claim directory')


@contextlib.contextmanager
def locked(cwd):
    """One writer at a time across processes; the OS frees the lock if the holder dies. Not re-entrant."""
    with open(os.path.join(board(cwd)[0], '.lock'), 'a+') as f:
        if fcntl:
            fcntl.flock(f, fcntl.LOCK_EX)  # released on close
            yield
            return
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)


def _cfile(cwd, tid):
    base, pre = board(cwd)
    return os.path.join(base, pre + _slug(tid) + '.json')


def record(cwd, t):
    """Live claim (or done marker) for this task, else None. Title must match: short ids get reused."""
    try:
        r = json.load(open(_cfile(cwd, t['id'])))
        if r.get('title') != t.get('title', '') or not r.get('by'):
            return None
        return r if r.get('done') or r.get('until', 0) > time.time() else None
    except (OSError, ValueError, AttributeError, TypeError):
        return None


def _write(cwd, t, **rec):
    p = _cfile(cwd, t['id'])
    tmp = f'{p}.{os.getpid()}.tmp'
    json.dump(dict(id=t['id'], title=t.get('title', ''), dir=os.path.abspath(cwd), **rec), open(tmp, 'w'))
    os.replace(tmp, p)


def other(cwd, t, by=''):
    """Message when someone else holds (or already finished) this task, else ''."""
    r = record(cwd, t)
    if not r:
        return ''
    if r.get('done'):
        return f'{t["id"]} already done by {r["by"]} (the task file here is behind)' if t['status'] != 'done' else ''
    return '' if r['by'] == actor(cwd, by) else f'{t["id"]} already claimed by {r["by"]}'


def take(cwd, tid, by='', ttl=TTL):
    """Compare-and-set claim: (True, 'claimed'|'renewed') or (False, why). A refusal writes nothing."""
    if ttl <= 0:
        return False, 'ttl must be positive'
    with locked(cwd):
        ts = tznext.load(cwd)
        t = ts.get(tid)
        if not t:
            return False, 'no such task'
        if t['status'] not in ('pending', 'active'):
            return False, f'not claimable: status {t["status"]}'
        why = other(cwd, t, by)
        if why:
            return False, why
        if t not in tznext.ready(ts):
            return False, hidden(ts, t) or 'dependencies not done'
        held = record(cwd, t)
        _write(cwd, t, by=actor(cwd, by), until=time.time() + ttl)
        return True, 'renewed' if held else 'claimed'


def take_next(cwd, by='', ttl=TTL):
    """Claim the first ready task nobody holds, atomically; gated tasks are never auto-picked."""
    if ttl <= 0:
        return None, 'ttl must be positive'
    with locked(cwd):
        for t in tznext.ready(tznext.load(cwd)):
            if not t['gate'] and not record(cwd, t):
                _write(cwd, t, by=actor(cwd, by), until=time.time() + ttl)
                return t, 'claimed'
    return None, 'nothing ready and unclaimed'


def _drop(cwd, t, me, force=False):
    r = record(cwd, t)
    if r and (force or not r.get('done') and r['by'] == me):
        os.unlink(_cfile(cwd, t['id']))
        return True
    return False


def drop(cwd, tid, by='', force=False):
    """Release my claim. force: anyone's, including a finished marker (task reverted on purpose)."""
    with locked(cwd):
        t = tznext.load(cwd).get(tid)
        if t and _drop(cwd, t, actor(cwd, by), force):
            return True, 'claim released'
    return False, 'no claim of yours on that task'


def finish(cwd, t, by=''):
    """Leave a done marker so other worktrees do not redo the task before the merge."""
    with locked(cwd):
        _write(cwd, t, by=actor(cwd, by), done=True)


def renew(cwd, t, ttl=TTL):
    """Heartbeat: extend a live claim made from this directory (called when a test passes)."""
    with locked(cwd):
        r = record(cwd, t)
        if r and not r.get('done') and r.get('dir') == os.path.abspath(cwd):
            _write(cwd, t, by=r['by'], until=max(r['until'], time.time() + ttl))
            return True
    return False


# ---------- compaction ----------
def _archive(cwd):
    return os.path.join(tznext.tdir(cwd), 'archive.jsonl')


def _short(t):
    te = t.get('test') or {}
    bits = [t.get('goal', '')[:120], f'verified: {te.get("result", "")[:100]}' if te.get('ok') else '']
    keep = {k: t[k] for k in ('id', 'title', 'status', 'deps', 'gate', 'parent', 'found', 'prio', 'created', 'closed') if k in t}
    return dict(keep, goal='', files=[], next='', model='', test={}, compacted=1,
                summary=' | '.join(b for b in bits if b).replace('\n', ' '))


def compact(cwd, days=COMPACT_DAYS, dry=False):
    """Shrink tasks done >= days ago to a summary; the original is archived first. Returns [(id, before, after)] chars."""
    out = []
    with locked(cwd):
        for tid, t in tznext.load(cwd).items():
            if t.get('status') != 'done' or t.get('compacted'):
                continue
            closed = t.get('closed') or os.path.getmtime(tznext._path(cwd, tid))  # legacy: file age
            if time.time() - closed < days * 86400:
                continue
            s = _short(dict(t, closed=int(closed)))
            before, after = len(json.dumps(t)), len(json.dumps(s))
            if after >= before:
                continue  # beads rule: never make a record bigger
            out.append((tid, before, after))
            if not dry:
                with open(_archive(cwd), 'a', encoding='utf-8') as f:
                    f.write(json.dumps(t, sort_keys=True) + '\n')
                tznext.save(cwd, s)
    return out


def restore(cwd, tid):
    """Bring back the archived original of a compacted task."""
    with locked(cwd):
        t = tznext.load(cwd).get(tid)
        if not t or not t.get('compacted'):
            return False, 'not a compacted task'
        found = None
        try:
            for line in open(_archive(cwd), encoding='utf-8'):
                with contextlib.suppress(ValueError):
                    d = json.loads(line)
                    if isinstance(d, dict) and d.get('id') == tid and d.get('created') == t.get('created'):
                        found = d
        except OSError:
            pass
        if not found:
            return False, 'no archived original'
        tznext.save(cwd, found)
    return True, 'restored'


# ---------- prime ----------
def problems(ts):
    """Dependency cycle (lowest id first) and references to tasks that do not exist."""
    out = []
    cyc = tznext.find_cycle(ts)
    if cyc:
        c = cyc[:-1]
        i = c.index(min(c))
        out.append('cycle: ' + ' -> '.join(c[i:] + c[:i] + [c[i]]))
    for k, t in sorted(ts.items()):
        refs = list(t.get('deps', [])) + [t[f] for f in ('parent', 'found') if t.get(f)]
        miss = [r for r in refs if r not in ts]
        if miss:
            out.append(f'{k}: missing task {", ".join(miss)}')
    return out


def _line(t):
    tail = (f' (found during {t["found"]})' if t.get('found') else '') + (f' GATE={t["gate"]}: ask owner' if t.get('gate') else '')
    return f'{t["id"]} p{t.get("prio", 2)} {t.get("title", "")[:60]}{tail}'


def prime(cwd, cap=PRIME_CHARS, top=5):
    """Compact task-state brief for a new session, cut at whole lines to <= cap chars; '' when nothing is open."""
    ts = tznext.load(cwd)
    opened = [t for t in ts.values() if t['status'] != 'done']
    if not opened:
        return ''
    ready = tznext.ready(ts)
    held = {t['id']: other(cwd, t) for t in opened}
    free = [t for t in ready if t['status'] == 'pending' and not held[t['id']]]
    stuck = [t for t in opened if t not in ready]
    L = [f'TZ tasks [actual]: {len(opened)} open, {len(free)} ready, {len(stuck)} blocked, {len(ts) - len(opened)} done']
    L += [f'active: {_line(t)} | next: {t.get("next", "")[:120] or "(unset)"}' for t in ready if t['status'] == 'active' and not held[t['id']]]
    L += [f'do not start: {v}' for v in held.values() if v]
    L += ['ready: ' + _line(t) for t in free[:top]]
    if len(free) > top:
        L.append(f'+{len(free) - top} more ready')
    L += [f'blocked: {t["id"]} ({hidden(ts, t) or ", ".join(unmet(ts, t)) or t["status"]})' for t in stuck[:top]]
    L += problems(ts)[:3]
    foot = 'Take work: tz next claim [id]. New work found: tz next add --title "..." --from <id>.'
    room = cap - len(foot) - 40  # 40: the "more lines" note
    out, used = [], 0
    for i, x in enumerate(L):
        if used + len(x) + 1 > room:
            out.append(f'+{len(L) - i} more lines: tz next')
            break
        out.append(x)
        used += len(x) + 1
    return '\n'.join(out + [foot])[:cap]


def on_start(cwd):
    """SessionStart helper (feature beads_prime, default off): the brief, only when no task pack is injected."""
    from tzlib import feature
    if not feature('beads_prime') or tznext.active(cwd):
        return ''
    return prime(cwd)


# ---------- JSONL export / import ----------
def export(cwd):
    """All tasks, one JSON per line, sorted by id (stable diffs)."""
    return ''.join(json.dumps(t, sort_keys=True, separators=(',', ':')) + '\n' for _, t in sorted(tznext.load(cwd).items()))


def _clean(d):
    """Typed copy of an imported record, or None. Never imports a runnable test command or a live 'active' state."""
    if not isinstance(d, dict) or not isinstance(d.get('id'), str) or not _slug(d['id']) or len(d['id']) > 80:
        return None
    strs = lambda v: [x for x in v if isinstance(x, str)] if isinstance(v, list) else []
    if d.get('status') not in tznext.STATUS or d.get('gate', '') not in ('',) + tznext.GATES:
        return None
    t = dict(id=d['id'], status='pending' if d['status'] == 'active' else d['status'], gate=d.get('gate', ''),
             deps=strs(d.get('deps')), files=strs(d.get('files')))
    for k in ('title', 'goal', 'next', 'model'):
        t[k] = ' '.join(d[k].split()) if isinstance(d.get(k), str) else ''  # one line: these are shown to the agent
    for k in ('parent', 'found', 'defer', 'summary'):
        if isinstance(d.get(k), str) and d[k]:
            t[k] = d[k]
    for k in ('prio', 'created', 'updated', 'closed', 'compacted'):
        if isinstance(d.get(k), int):
            t[k] = d[k]
    te = d.get('test')
    # WHY cmd='': `done --yes` runs the stored command, so a file from elsewhere must not supply one
    t['test'] = dict(cmd='', ok=bool(te.get('ok')), result=str(te.get('result', ''))[:160], time=str(te.get('time', ''))[:20],
                     src='import') if isinstance(te, dict) and te else {}
    return t


def _same(old, new):
    norm = lambda x: {k: v for k, v in (_clean(x) or {}).items() if k not in ('test', 'updated') and v not in ('', [])}
    return norm(old) == norm(new)


def _merge(old, new):
    """Newer record wins, but done stays done, gates are never dropped, local test command and active state survive."""
    done_now = new['status'] == 'done' and old['status'] != 'done'
    if old['status'] == 'done' and (new['status'] != 'done' or new.get('compacted') and not old.get('compacted')):
        return None  # a foreign summary must not replace a full local record (compact here archives first)
    if not done_now and new.get('updated', 0) <= old.get('updated', 0):
        return None
    m = dict(new, gate=old.get('gate') or new['gate'], test=old.get('test') or new['test'])
    if done_now and new['test']:
        m['test'] = new['test']
    if old['status'] == 'active' and not done_now:
        m['status'] = 'active'
    return m


def load_jsonl(cwd, text):
    """Upsert JSONL by id. Returns (counts, notes); id clashes and cycle-closing records are refused."""
    n, notes = dict(added=0, updated=0, same=0, kept=0, skipped=0), []
    with locked(cwd):
        ts = tznext.load(cwd)
        for num, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                new = _clean(json.loads(line))
            except ValueError:
                new = None
            if not new:
                n['skipped'] += 1
                notes.append(f'line {num}: not a valid task')
                continue
            tid, old, kind = new['id'], ts.get(new['id']), 'added'
            if old:
                if _same(old, new):
                    n['same'] += 1
                    continue
                clash = old.get('title') != new['title'] and old.get('created') != new.get('created')
                new, kind = None if clash else _merge(old, new), 'updated'
                if not new:
                    n['kept'] += 1
                    notes.append(f'{tid}: id clash, local kept' if clash else f'{tid}: local kept (done or not older)')
                    continue
            elif os.path.exists(tznext._path(cwd, tid)):
                n['skipped'] += 1
                notes.append(f'{tid}: file name already used by another task')
                continue
            trial = {**ts, tid: new}
            if tznext.find_cycle(trial) and not tznext.find_cycle(ts):
                n['skipped'] += 1
                notes.append(f'{tid}: refused, would create a dependency cycle')
                continue
            ts = trial
            tznext.save(cwd, new, stamp=False)
            if new['status'] == 'done':
                tznext.release(cwd, tid)
            n[kind] += 1
    return n, notes


# ---------- CLI (reached through `tz next <sub>`) ----------
def cli(a, cwd):
    """Run one of the sub-commands this module owns; a = the tznext argparse result."""
    if a.sub == 'claim' and not a.id:
        t, msg = take_next(cwd, a.by, a.ttl)
        print(f'{msg}: {_line(t)}' if t else msg)
        return 0 if t else 3
    if a.sub == 'prime':
        print(prime(cwd) or 'no open tasks')
        return 0
    if a.sub == 'export':
        sys.stdout.write(export(cwd))
        return 0
    if a.sub == 'check':
        p = problems(tznext.load(cwd))
        print('\n'.join(p) or 'no cycles or missing tasks')
        return 3 if p else 0
    if a.sub == 'compact':
        r = compact(cwd, a.days, a.dry)
        saved = sum(b - c for _, b, c in r)
        print(f'{"would compact" if a.dry else "compacted"} {len(r)} task(s), {saved} chars smaller [actual]')
        return 0
    if not a.id:
        print('id required', file=sys.stderr)
        return 2
    if a.sub == 'import':
        try:
            text = open(a.id, encoding='utf-8').read()
        except (OSError, UnicodeError) as e:
            print(f'cannot read {a.id}: {e}', file=sys.stderr)
            return 1
        n, notes = load_jsonl(cwd, text)
        print('\n'.join(notes[:10] + [' '.join(f'{k} {v}' for k, v in n.items())]))
        return 0
    if a.sub == 'claim':
        ok, msg = take(cwd, a.id, a.by, a.ttl)
    elif a.sub == 'unclaim':
        ok, msg = drop(cwd, a.id, a.by, a.force)
    elif a.sub == 'defer':
        ok, msg = defer(cwd, a.id, a.until)
    else:
        ok, msg = restore(cwd, a.id)
    print(msg)
    return 0 if ok else 3


SUBS = ('claim', 'unclaim', 'prime', 'compact', 'restore', 'export', 'import', 'check', 'defer')


def main(argv):
    """Same CLI as `tz next`."""
    return tznext.main(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
