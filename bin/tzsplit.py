#!/usr/bin/env python3
# Owner-workflow defaults. All advice/local files only: nothing is spawned, pushed or installed.
#   tz split "task A" "task B" ..   one session per task: cheapest fitting model, worktree cmd, lock for shared resources, test last
#   tz lock acquire|release|status NAME [--ttl S]   atomic lock dir for a shared resource (live test, device, port); stale after ttl (default 1800s)
#   tz hsize [DIR] [--json]          handoff size check: daily notes <=30 lines, master top block <=15 lines, weekly merge due
import json, os, re, sys, time, glob

D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
SHARED = re.compile(r'\b(live test|e2e|premiere|simulator|device|browser|port \d+|database|db|deploy|install|publish)\b', re.I)
BUILD_FIRST = 'build the whole batch first with syntax checks only; one live test at the end, holding the lock'


def lockdir(name):
    base = os.path.expanduser(os.environ.get('TZ_LOCK_DIR', '~/.claude/token-zombie/locks'))
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, re.sub(r'[^A-Za-z0-9_.-]', '-', name)[:60] or 'lock')


def lock(op, name, ttl=1800):
    p = lockdir(name)
    meta = os.path.join(p, 'owner.json')
    held = None
    if os.path.isdir(p):
        try:
            held = json.load(open(meta))
        except (OSError, ValueError):
            held = {'ts': os.path.getmtime(p)}
        if time.time() - held.get('ts', 0) > ttl:
            held = None  # stale
    if op == 'status':
        return (0, f'{name}: held pid {held.get("pid", "?")} for {int(time.time() - held["ts"])}s') if held else (0, f'{name}: free')
    if op == 'release':
        for f in glob.glob(os.path.join(p, '*')):
            os.remove(f)
        if os.path.isdir(p):
            os.rmdir(p)
        return 0, f'{name}: released'
    if op == 'acquire':
        if held is None and os.path.isdir(p):
            lock('release', name)
        try:
            os.mkdir(p)
        except FileExistsError:
            return 1, f'{name}: busy (held {int(time.time() - held["ts"])}s); wait or release if the holder is gone'
        json.dump({'ts': time.time(), 'pid': os.getppid()}, open(meta, 'w'))
        return 0, f'{name}: acquired (stale after {ttl}s); release: tz lock release {name}'
    return 2, 'usage: tz lock acquire|release|status NAME [--ttl S]'


def detect(prompt):
    """Independent tasks in one prompt: numbered/bulleted lines or 'also/then ...' clauses. [] when fewer than 2 (heuristic, advice only)."""
    items = [re.sub(r'^\s*(\d+[.)]|[-*])\s*', '', l).strip() for l in (prompt or '').splitlines() if re.match(r'^\s*(\d+[.)]|[-*])\s+\S', l)]
    if len(items) < 2:
        items = [x.strip() for x in re.split(r'\b(?:also|and then|then)\b|;', prompt or '', flags=re.I) if len(x.split()) >= 4]
    return items if len(items) >= 2 else []


def plan(tasks):
    import tzroute, tzmore
    out = []
    for i, t in enumerate(tasks, 1):
        r = tzroute.route(t)
        out.append(dict(n=i, task=t, model=r['model'], mode=r['mode'], worktree=tzmore.worktree_cmd(t),
                        lock=sorted({m.lower() for m in SHARED.findall(t)}) or None))
    shared = {}
    for x in out:
        for k in x['lock'] or []:
            shared.setdefault(k, []).append(x['n'])
    return dict(sessions=out, lock_needed={k: v for k, v in shared.items() if len(v) > 1}, rule=BUILD_FIRST,
                basis='EST keyword heuristic; one session per task, each in its own worktree; the checking step runs last')


def hsize(root):
    hd = os.path.join(root, 'handoffs')
    bad, days = [], set()
    for f in sorted(glob.glob(os.path.join(hd, '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*.md'))):
        n = sum(1 for _ in open(f, errors='replace'))
        days.add(os.path.basename(f)[:10])
        if n > 30:
            bad.append((os.path.relpath(f, root), n))
    top = None
    for name in ('HANDOFF.md', os.path.join('docs', 'HANDOFF.md')):
        p = os.path.join(root, name)
        if os.path.exists(p):
            top = 0
            for ln in open(p, errors='replace'):
                if ln.strip() == '---':
                    break
                top += 1
            top = (name, top)
            break
    return dict(over_30=bad, daily_days=len(days), merge_due=len(days) >= 7, master_top=top,
                master_top_over_15=bool(top and top[1] > 15))


def main(argv):
    c, a = argv[0], argv[1:]
    js = '--json' in a
    a = [x for x in a if x != '--json']
    if c == 'lock':
        ttl = 1800
        if '--ttl' in a:
            i = a.index('--ttl'); ttl = int(a[i + 1]); del a[i:i + 2]
        if len(a) < 2:
            print('usage: tz lock acquire|release|status NAME [--ttl S]', file=sys.stderr); return 2
        rc, msg = lock(a[0], a[1], ttl); print(msg); return rc
    if c == 'split':
        if not a:
            print('usage: tz split "task A" "task B" ...', file=sys.stderr); return 2
        r = plan(a)
        if js:
            print(json.dumps(r, indent=1)); return 0
        for x in r['sessions']:
            print(f"{x['n']}. [{x['model']}] {x['task']}\n   {x['worktree']}" + (f"\n   shared: {', '.join(x['lock'])}" if x['lock'] else ''))
        for k, v in r['lock_needed'].items():
            print(f"lock '{k}' shared by tasks {v}: tz lock acquire {k}  ... tz lock release {k}")
        print('rule: ' + r['rule'] + '\nTZ starts nothing; open one session per line yourself.')
        return 0
    if c == 'hsize':
        r = hsize(os.path.abspath(a[0] if a else '.'))
        if js:
            print(json.dumps(r)); return 0
        for f, n in r['over_30']:
            print(f'OVER: {f} has {n} lines (max 30): trim to done/left/next')
        if r['master_top_over_15']:
            print(f'OVER: {r["master_top"][0]} top block {r["master_top"][1]} lines (max 15, end with ---)')
        if r['merge_due']:
            print(f'MERGE DUE: {r["daily_days"]} daily days; merge into the master top block')
        if not (r['over_30'] or r['master_top_over_15'] or r['merge_due']):
            print('handoff sizes ok')
        return 1 if (r['over_30'] or r['master_top_over_15']) else 0
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
