#!/usr/bin/env python3
"""tz next: dependency-aware task list (handoffs/tasks/T-*.json), <=2k-token task pack, auto checkpoint, gates, per-session token split.
Cycle check, atomic claim and hybrid ready order adapted from beads (MIT, Copyright (c) 2025 Beads Contributors) cycles.go + ready sort, see NOTICE.
Claims, parent-child, defer, compaction, prime and JSONL live in tzbeads.py.
Local files only. Never runs a gated task; never launches sessions. status: done|active|blocked|pending; gate: paid|commit|install|publish."""
import glob, json, os, re, sys, time

import tzbeads

STATUS, GATES, PACK_CHARS = ('done', 'active', 'blocked', 'pending'), ('paid', 'commit', 'install', 'publish'), 8000  # 8000 chars ~ 2k tok
ET = lambda n: n // 4  # est tokens, same basis as tzopt
HYBRID_S = 48 * 3600  # beads hybrid: tasks younger than 48 h go by priority, older ones by age (no starvation)
TESTCMD = re.compile(r'run_all\.sh|pytest|npm (run )?test|plugin test|test_\w+\.sh|cargo test|go test')


def tdir(cwd):
    return os.path.join(cwd, 'handoffs', 'tasks')


def _path(cwd, tid):
    return os.path.join(tdir(cwd), 'T-' + re.sub(r'[^a-z0-9]+', '-', tid.lower()).strip('-') + '.json')


def load(cwd):
    out = {}
    for f in sorted(glob.glob(os.path.join(tdir(cwd), 'T-*.json'))):
        try:
            t = json.load(open(f))
            out[t['id']] = t
        except (OSError, ValueError, KeyError):
            pass  # corrupt file: skip, never crash a hook
    return out


def save(cwd, t, stamp=True):
    """Atomic write; `updated` lets JSONL import pick the newer record."""
    os.makedirs(tdir(cwd), exist_ok=True)
    p = _path(cwd, t['id'])
    tmp = f'{p}.{os.getpid()}.tmp'  # per process: two writers must not share a temp file
    if stamp:
        t['updated'] = int(time.time())
    json.dump(t, open(tmp, 'w'), indent=1)
    os.replace(tmp, p)


def _words(s):
    return set(re.findall(r'[a-z0-9]+', s.lower()))


def near_dup(ts, title, cut=0.6):
    """(id, status) of an existing task whose title shares >= cut of its words (Jaccard) with title, else None."""
    w = _words(title)
    for k, v in ts.items():
        o = _words(v.get('title', ''))
        if min(len(w), len(o)) >= 3 and len(w & o) / len(w | o) >= cut:  # short titles ('Build A'/'Build B') are not compared
            return k, v['status']
    return None


def find_cycle(ts):
    """First dependency cycle as [a, b, ..., a], else None (DFS with colours, like beads cycles.go); parent-child counts."""
    ts = tzbeads.graph(ts)
    col = {}
    def dfs(n, path):
        col[n] = 1
        for d in ts.get(n, {}).get('deps', []):
            if d not in ts:
                continue
            if col.get(d) == 1:
                return path[path.index(d):] + [d] if d in path else [d, n, d]
            if d not in col:
                r = dfs(d, path + [d])
                if r:
                    return r
        col[n] = 2
        return None
    for k in sorted(ts):
        if k not in col:
            r = dfs(k, [k])
            if r:
                return r
    return None


def add_dep(cwd, tid, dep):
    """Add dep to tid; refuse (nothing written) when it would create a cycle."""
    ts = load(cwd)
    if tid not in ts or dep not in ts:
        return False, 'no such task'
    if dep in ts[tid]['deps']:
        return True, 'already a dependency'
    ts[tid]['deps'].append(dep)
    cyc = find_cycle(ts)
    if cyc:
        return False, 'refused, dependency cycle: ' + ' -> '.join(cyc)
    save(cwd, ts[tid])
    return True, 'dependency added'


def add(cwd, tid, title='', deps=(), gate='', goal='', files=(), nxt='', model='', force=False, prio=2, parent='', found=''):
    """Create a task; empty tid gets a hash id. Returns (task | None, message)."""
    if not tid:
        if not title:
            return None, 'id or --title required'
        tid = tzbeads.new_id(cwd, title, goal)
    with tzbeads.locked(cwd):
        return _add(cwd, tid, title, deps, gate, goal, files, nxt, model, force, prio, parent, found)


def _add(cwd, tid, title, deps, gate, goal, files, nxt, model, force, prio, parent, found):
    ts = load(cwd)
    if tid in ts:
        return None, f'duplicate: {tid} exists ({ts[tid]["status"]}); not overwritten'
    if os.path.exists(_path(cwd, tid)):  # 'A' and 'a' share a file name
        return None, f'duplicate: the file for {tid} exists; not overwritten'
    dup = [k for k, v in ts.items() if title and v.get('title', '').lower() == title.lower()]
    if dup:
        return None, f'duplicate title of {dup[0]}'
    nd = None if force else near_dup(ts, title)
    if nd:
        return None, f'duplicate work? {nd[0]} ({nd[1]}) has a near-identical title; add --force if it is really new'
    bad = [d for d in deps if d not in ts]
    if bad or gate and gate not in GATES or tid in deps:
        return None, f'bad deps {bad} or gate {gate!r}'
    if parent and (parent not in ts or ts[parent]['status'] == 'done') or found and found not in ts:
        return None, f'bad parent {parent!r} (must be an open task) or from {found!r}'
    t = dict(id=tid, title=title, deps=list(deps), gate=gate, status='pending', goal=goal, files=list(files), next=nxt, model=model, test={},
             prio=prio, created=int(time.time()))
    t.update({k: v for k, v in (('parent', parent), ('found', found)) if v})
    cyc = find_cycle({**ts, tid: t})
    if cyc:
        return None, 'refused, dependency cycle: ' + ' -> '.join(cyc)
    save(cwd, t)
    return t, 'added'


def ready(ts):
    """pending/active tasks whose deps are all done, not deferred, parents unblocked: active first, then hybrid (48 h)."""
    r = [t for t in ts.values() if t['status'] in ('active', 'pending') and not tzbeads.unmet(ts, t) and not tzbeads.hidden(ts, t)]
    now = time.time()
    def key(t):
        c = t.get('created') or 0
        old = now - c > HYBRID_S  # no 'created' (legacy file) counts as old
        return (t['status'] != 'active', not old, c if old else t.get('prio', 2), c, t['id'])
    return sorted(r, key=key)


def _lock(cwd):
    return os.path.join(tdir(cwd), '.active.lock')


def claim(cwd, tid):
    """Atomic single-active claim (O_EXCL). (True, '') or (False, holder id). A stale lock (holder no longer active) is replaced."""
    os.makedirs(tdir(cwd), exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(_lock(cwd), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, tid.encode()); os.close(fd)
            return True, ''
        except FileExistsError:
            try:
                h = open(_lock(cwd)).read().strip()
            except OSError:
                continue
            if h == tid:
                return True, ''
            if load(cwd).get(h, {}).get('status') == 'active':
                return False, h
            try:
                os.unlink(_lock(cwd))  # stale
            except OSError:
                pass
    return False, '?'


def release(cwd, tid):
    try:
        if open(_lock(cwd)).read().strip() == tid:
            os.unlink(_lock(cwd))
    except OSError:
        pass


def start(cwd, tid, approved=False, by=''):
    ts = load(cwd)
    t = ts.get(tid)
    if not t:
        return False, 'no such task'
    if t['status'] == 'done':
        return False, 'already done; not restarted'
    if t not in ready(ts):
        return False, 'dependencies not done' if tzbeads.unmet(ts, t) else tzbeads.hidden(ts, t) or f'status {t["status"]}'
    if t['gate'] and not approved:
        return False, f'GATE {t["gate"]}: owner approval needed (rerun with --approved only after the owner says yes)'
    for o in ts.values():
        if o['status'] == 'active' and o['id'] != tid:
            return False, f'{o["id"]} is already active; finish or block it first'
    shared, why = tzbeads.take(cwd, tid, by)  # other worktrees / agents must not run the same task
    if not shared:
        return False, why
    got, holder = claim(cwd, tid)
    if not got:
        if why == 'claimed':
            tzbeads.drop(cwd, tid, by)
        return False, f'{holder} is already active (claimed); finish or block it first'
    t['status'] = 'active'
    save(cwd, t)
    return True, 'active'


def record_test(cwd, t, cmd, ok, line, src='manual'):
    t['test'] = dict(cmd=cmd, ok=bool(ok), result=line[:160], time=time.strftime('%Y-%m-%d %H:%M'), src=src)
    save(cwd, t)


def done(cwd, tid, cmd='', yes=False, by=''):
    """Mark done only after the task's test passes (runs it with consent)."""
    ts = load(cwd)
    t = ts.get(tid)
    if not t:
        return False, 'no such task'
    kids = tzbeads.open_children(ts, tid)
    if kids:
        return False, f'open child tasks, finish them first: {", ".join(kids)}'
    cmd = cmd or t['test'].get('cmd', '')
    if not cmd:
        return False, 'no test command; give --test'
    if not yes:
        return False, f'will run: {cmd}  (rerun with --yes)'
    import tzhandoff
    ok, line = tzhandoff.run_test(os.getcwd() if not os.path.isdir(cwd) else cwd, cmd)
    record_test(cwd, t, cmd, ok, line)
    if not ok:
        return False, f'test failed, task stays {t["status"]}: {line}'
    t['status'] = 'done'
    t['closed'] = int(time.time())
    save(cwd, t)
    release(cwd, tid)
    tzbeads.finish(cwd, t, by)
    return True, f'done, verified: {line}'


def active(cwd):
    a = [t for t in load(cwd).values() if t['status'] == 'active']
    return a[0] if a else None


def pack(cwd):
    """<=2k-token context for the ACTIVE task only; '' when none."""
    t = active(cwd)
    if not t:
        return ''
    ts = load(cwd)
    te = t.get('test') or {}
    L = [f'TOKEN ZOMBIE task pack [{t["id"]}] {t["title"]}', f'goal: {t["goal"]}',
         'deps done: ' + (', '.join(t['deps']) or 'none'), 'files: ' + (', '.join(t['files']) or 'none'),
         'last test: ' + (f'{te["cmd"]} -> {"PASS" if te["ok"] else "FAIL"} {te["result"]} ({te["time"]})' if te else 'none yet'),
         f'next action: {t["next"] or "(unset)"}']
    if t.get('parent') in ts:
        L.insert(2, f'part of: {t["parent"]} {ts[t["parent"]]["title"]}')
    if t.get('model'):
        L.append('model advice: ' + t['model'])
    gated = [o['id'] + ':' + o['gate'] for o in ready(ts) if o['gate'] and o['id'] != t['id']]
    if gated:
        L.append('gated, do NOT run, ask owner: ' + ', '.join(gated))
    L.append('Gates (paid/commit/install/publish): stop and ask the owner; never auto-run. No rediscovery: read only the files above.')
    return '\n'.join(L)[:PACK_CHARS]


def checkpoint(cwd, reason='manual'):
    """Refresh git snapshot + log it. No commands run, nothing gated touched. Returns True if an active task or task state exists."""
    try:
        import tzhandoff
        p = tzhandoff.checkpoint(cwd)
    except Exception:
        p = None
    t = active(cwd)
    if t:
        t['checkpoint'] = dict(reason=reason, time=time.strftime('%Y-%m-%d %H:%M'))
        save(cwd, t)
    return bool(p or t)


def on_tool(data):
    """PostToolUse: a Bash test command that clearly passed -> record on the active task + checkpoint. Silent."""
    if data.get('tool_name') != 'Bash':
        return
    cmd = (data.get('tool_input') or {}).get('command', '')
    r = data.get('tool_response')
    txt = json.dumps(r) if not isinstance(r, str) else r
    if not TESTCMD.search(cmd) or (isinstance(r, dict) and (r.get('interrupted') or r.get('is_error'))):
        return
    if re.search(r'FAIL|fail[ :]+[1-9]|Traceback|Error', txt) or not re.search(r'pass|PASS|ok', txt):
        return
    cwd = data.get('cwd') or os.getcwd()
    t = active(cwd)
    if not t:
        return
    m = re.findall(r'TOTAL pass \d+ fail 0|pass[ :]+\d+[^"\\]{0,30}', txt)
    # keep only the test segment of a chained line: replaying the whole (cut) line ran other commands and failed
    seg = next(x for x in re.split(r'\s*(?:;|&&|\|\|)\s*', cmd) if TESTCMD.search(x))
    record_test(cwd, t, seg.split('|')[0].replace('2>&1', '').strip()[:200], True, m[-1] if m else 'pass', 'hook')
    try:
        tzbeads.renew(cwd, t)  # heartbeat: verified progress keeps the claim alive
    except OSError:
        pass
    checkpoint(cwd, 'verified-test-pass')
    try:
        import tzbus
        tzbus.mood('test')
    except Exception:
        pass


def _replies(path):
    seen, out = set(), []
    try:
        lines = open(path, encoding='utf-8', errors='ignore').read().splitlines()
    except OSError:
        return out
    for raw in lines:
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        m = d.get('message') or {}
        u = m.get('usage')
        if d.get('type') == 'assistant' and u and m.get('id') not in seen:
            seen.add(m.get('id'))
            c = m.get('content')
            cmds = ' '.join((b.get('input') or {}).get('command', '') for b in c if isinstance(b, dict) and b.get('type') == 'tool_use') if isinstance(c, list) else ''
            out.append((u, cmds))
    return out


def measure(cwd, transcript, home=None):
    """Per-session token split from a transcript. startup/work/verify/output measured from usage; pack = est; repeated = cache_read after reply 1; overhead = tz hook chars/4 (est)."""
    R = _replies(transcript)
    if not R:
        return {}
    g = lambda u, k: u.get(k) or 0
    full = lambda u: g(u, 'input_tokens') + g(u, 'cache_creation_input_tokens') + g(u, 'cache_read_input_tokens')
    m = dict(startup=full(R[0][0]), pack=ET(len(pack(cwd))), repeated=0, work=0, verify=0, replies=len(R))
    for u, c in R[1:]:
        m['repeated'] += g(u, 'cache_read_input_tokens')
        new = g(u, 'input_tokens') + g(u, 'cache_creation_input_tokens') + g(u, 'output_tokens')
        m['verify' if TESTCMD.search(c) else 'work'] += new
    sid = os.path.basename(transcript)[:-6]
    try:
        s = json.load(open(os.path.join(home or os.path.expanduser('~'), '.claude', 'token-zombie', f'live-{sid}.json')))
        m['tz_overhead'] = ET(sum(h.get('chars', 0) for h in s.get('hooks', {}).values()))
    except (OSError, ValueError):
        m['tz_overhead'] = 0
    return m


def render(ts, cwd=None):
    """Task list + the next eligible task; compacted tasks are only counted."""
    if not ts:
        return 'no tasks. add: tz next add <id> --title ...'
    held = {k: tzbeads.other(cwd, t) for k, t in ts.items() if t['status'] != 'done'} if cwd else {}
    rd = [t for t in ready(ts) if not held.get(t['id'])]
    L = [f'{t["status"]:8} {t["id"]:14} {t["title"][:40]}' + (f' deps={",".join(t["deps"])}' if t['deps'] else '') + (f' GATE={t["gate"]}' if t['gate'] else '')
         + (f' parent={t["parent"]}' if t.get('parent') else '') + (f' defer={t["defer"]}' if t.get('defer') else '') for t in ts.values() if not t.get('compacted')]
    old = sum(1 for t in ts.values() if t.get('compacted'))
    if old:
        L.append(f'+{old} compacted done task(s) hidden (tz next restore <id>)')
    L += ['do not start: ' + v for v in held.values() if v]
    if rd:
        n = rd[0]
        L.append(f'NEXT: {n["id"]}' + (f'  GATE {n["gate"]}: stop and ask the owner; not auto-run' if n['gate'] else f' -> tz next start {n["id"]}'))
    else:
        L.append('NEXT: nothing eligible (all done, claimed, deferred or blocked by deps)')
    return '\n'.join(L)


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='tz next')
    ap.add_argument('sub', nargs='?', default='list', choices=['list', 'add', 'start', 'done', 'block', 'pack', 'checkpoint', 'measure', 'set', 'dep', *tzbeads.SUBS])
    ap.add_argument('id', nargs='?', default='')
    ap.add_argument('--cwd', default=os.getcwd())
    ap.add_argument('--title', default=''); ap.add_argument('--goal', default=''); ap.add_argument('--dep', action='append', default=[])
    ap.add_argument('--gate', default=''); ap.add_argument('--file', action='append', default=[]); ap.add_argument('--next', dest='nxt', default='')
    ap.add_argument('--prio', type=int, default=2); ap.add_argument('--model', default=''); ap.add_argument('--test', default=''); ap.add_argument('--yes', action='store_true')
    ap.add_argument('--approved', action='store_true'); ap.add_argument('--force', action='store_true'); ap.add_argument('--transcript', default='')
    ap.add_argument('--by', default=''); ap.add_argument('--ttl', type=int, default=tzbeads.TTL); ap.add_argument('--days', type=int, default=tzbeads.COMPACT_DAYS)
    ap.add_argument('--dry', action='store_true'); ap.add_argument('--until', default=''); ap.add_argument('--parent', default=''); ap.add_argument('--from', dest='found', default='')
    a = ap.parse_args(argv)
    cwd = os.path.abspath(a.cwd)
    if a.sub == 'list':
        print(render(load(cwd), cwd)); return 0
    if a.sub == 'pack':
        print(pack(cwd) or 'no active task'); return 0
    if a.sub == 'checkpoint':
        ok = checkpoint(cwd, a.nxt or 'manual'); print('checkpoint saved' if ok else 'nothing to checkpoint'); return 0 if ok else 1
    if a.sub == 'measure':
        import tzusage
        tp = a.transcript or tzusage.find_transcript(cwd)
        m = measure(cwd, tp) if tp else {}
        if not m:
            print('no transcript'); return 1
        print('session tokens: startup {startup} | pack ~{pack} [est] | repeated ctx {repeated} | work {work} | verify {verify} | TZ overhead ~{tz_overhead} [est] | {replies} replies'.format(**m))
        return 0
    if a.sub in tzbeads.SUBS:
        return tzbeads.cli(a, cwd)
    if a.sub == 'add':
        found = (active(cwd) or {}).get('id', '.') if a.found == '.' else a.found
        t, msg = add(cwd, a.id, a.title, a.dep, a.gate, a.goal, a.file, a.nxt, a.model, a.force, a.prio, a.parent, found)
        print(f'{msg} {t["id"]}' if t and not a.id else msg); return 0 if t else 1
    if not a.id:
        print('id required', file=sys.stderr); return 2
    if a.sub == 'start':
        ok, msg = start(cwd, a.id, a.approved, a.by); print(msg); return 0 if ok else 3
    if a.sub == 'done':
        ok, msg = done(cwd, a.id, a.test, a.yes, a.by); print(msg); return 0 if ok else 3
    if a.sub == 'dep':
        if not a.dep:
            print('--dep required', file=sys.stderr); return 2
        ok, msg = add_dep(cwd, a.id, a.dep[0]); print(msg); return 0 if ok else 3
    ts = load(cwd); t = ts.get(a.id)
    if not t:
        print('no such task'); return 1
    if a.sub == 'block':
        t['status'] = 'blocked' if t['status'] != 'done' else 'done'
        release(cwd, a.id)
        tzbeads.drop(cwd, a.id, a.by)
    if a.nxt: t['next'] = a.nxt
    if a.file: t['files'] = a.file
    save(cwd, t); print(t['status']); return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
