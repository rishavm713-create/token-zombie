#!/usr/bin/env python3
# adapted from jokim1/karpathy-skills plugins/karpathy/skills/karpathy-audit/SKILL.md (token size x replay ranking, replay tiers) and
# karpathy-refactor/SKILL.md (baseline, gated slice, snapshot, auto-revert) (MIT, Copyright (c) 2026 Joseph Kim), see NOTICE.
# Upstream is prose only for both; the Python here is TZ's own.
#   rank  [--log LOG] [--cwd DIR] [--requests N] [--add TIER=FILE] [--top N] [--json]
#   slice start ID [--allow-red] [--timeout S] -- CMD...   |  slice verify ID [--no-revert]  |  slice restore|drop ID  |  slice list
# Tokens are EST = chars/4. A slice covers the git worktree only: not ignored files, submodules, the index, or a command's outside effects.
# Off switch for auto-revert: --no-revert or TZ_SLICE_REVERT=0.
import glob, hashlib, json, os, re, shutil, stat, subprocess, sys

TIERS = ('turn', 'session', 'task', 'rare')  # upstream order: every-turn > per-session > per-task > rarely loaded
# ASSUMED replays per session for the non-every-turn tiers; 'turn' uses the request count.
WEIGHT = {'session': 1.0, 'task': 0.25, 'rare': 0.05}
DEFAULT_REQUESTS = 30  # ASSUMED when no log is given
MAX_SNAP = 200 * 1024 * 1024


def _read(p):
    try:
        with open(p, errors='replace') as f:
            return f.read()
    except OSError:
        return None


def rank_items(items, requests):
    """items = [(path, tier, chars)] -> rows sorted by token size x replay."""
    rows = []
    for path, tier, chars in items:
        n = requests if tier == 'turn' else WEIGHT[tier]
        rows.append(dict(path=path, tier=tier, tok=chars // 4, replays=n, cost=int(chars // 4 * n)))
    return sorted(rows, key=lambda r: (-r['cost'], TIERS.index(r['tier']), r['path']))


def discover(cwd, home=None):
    """Instruction files Claude Code loads -> [(path, tier, chars)]. Skill name+description is every-turn; the body is per-task."""
    home = home or os.path.expanduser('~')
    items, seen = [], set()

    def add(p, depth=0):
        rp = os.path.realpath(p)
        t = None if rp in seen else _read(p)
        if t is None:
            return
        seen.add(rp)
        items.append((p, 'turn', len(t)))
        if depth < 5:  # @imports load with the file; code spans and fences are not imports
            plain = re.sub(r'```.*?```|`[^`\n]*`', '', t, flags=re.S)
            for ref in re.findall(r'(?:^|\s)@([\w~./-]+)', plain):
                q = os.path.join(home, ref[2:]) if ref.startswith('~/') else os.path.join(os.path.dirname(p), ref)
                if os.path.isfile(q):
                    add(q, depth + 1)

    add(os.path.join(home, '.claude', 'CLAUDE.md'))
    d = os.path.abspath(cwd)
    chain = []
    while d != os.path.dirname(d):
        chain.append(d)
        d = os.path.dirname(d)
    for d in reversed(chain):
        for n in ('CLAUDE.md', 'CLAUDE.local.md', os.path.join('.claude', 'CLAUDE.md')):
            add(os.path.join(d, n))
    for base in (os.path.join(home, '.claude'), os.path.join(os.path.abspath(cwd), '.claude')):
        for pat in (('skills', '*', 'SKILL.md'), ('commands', '*.md')):
            for p in sorted(glob.glob(os.path.join(glob.escape(base), *pat))):
                rp, t = os.path.realpath(p), _read(p)
                if t is None or rp in seen:
                    continue
                seen.add(rp)
                m = re.match(r'---\n.*?\n---\n', t, re.S)
                fm = len(m.group(0)) if m else 0
                if fm and pat[0] == 'skills':
                    items.append((p + ' [frontmatter]', 'turn', fm))
                items.append((p, 'task', len(t) - fm))
    return items


def log_rank(path):
    """MEASURED from one chat log: each tool result's size x the later API requests that carried it, until a compaction.
    Main chain only. -> (requests, rows sorted by cost)."""
    use, live, agg, seen, total = {}, [], {}, set(), 0

    def flush():
        for lab, chars, n in live:
            a = agg.setdefault(lab, dict(label=lab, calls=0, tok=0, replays=0, cost=0))
            a['calls'] += 1
            a['tok'] += chars // 4
            a['replays'] += n
            a['cost'] += chars // 4 * n
        del live[:]

    with open(path, errors='replace') as f:
        for ln in f:
            try:
                d = json.loads(ln)
                if d.get('isSidechain'):
                    continue
                if d.get('isCompactSummary') or d.get('subtype') == 'compact_boundary':
                    flush()
                    continue
                m = d.get('message') or {}
                c, mid = m.get('content'), m.get('id')
                if d.get('type') == 'assistant' and mid and mid not in seen:  # one response spans several lines
                    seen.add(mid)
                    total += 1
                    for r in live:
                        r[2] += 1
            except (ValueError, AttributeError):
                continue
            for b in c if isinstance(c, list) else []:
                if not isinstance(b, dict):
                    continue
                if b.get('type') == 'tool_use':
                    ti = b.get('input') if isinstance(b.get('input'), dict) else {}
                    arg = ti.get('file_path') or ti.get('command') or ti.get('pattern') or ti.get('skill') or ''
                    use[b.get('id')] = ('%s %s' % (b.get('name', '?'), ' '.join(str(arg).split())[:80])).strip()
                elif b.get('type') == 'tool_result' and b.get('tool_use_id') in use:
                    r = b.get('content')
                    if isinstance(r, list):
                        r = '\n'.join(x.get('text', '') for x in r if isinstance(x, dict))
                    live.append([use.pop(b['tool_use_id']), len(r) if isinstance(r, str) else 0, 0])
    flush()
    return total, sorted(agg.values(), key=lambda a: (-a['cost'], a['label']))


# ---- verified slice ----
class SliceError(Exception):
    pass


def _git(root, *a):
    r = subprocess.run(['git', '-C', root] + list(a), capture_output=True)
    if r.returncode:
        raise SliceError('git %s failed: %s' % (a[0], r.stderr.decode('utf-8', 'replace').strip()[:200]))
    return r.stdout


def _root(cwd):
    return os.fsdecode(_git(cwd, 'rev-parse', '--show-toplevel').rstrip(b'\n'))


def _paths(b):
    return set(os.fsdecode(x) for x in b.split(b'\0') if x)


def _dirty(root, head):
    return (_paths(_git(root, 'diff', '--name-only', '--no-renames', '--ignore-submodules=all', '-z', head, '--'))
            | _paths(_git(root, 'ls-files', '-o', '--exclude-standard', '-z')))


def _dir(root, sid):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', sid or ''):
        raise SliceError('bad slice id (letters, digits, _ and - only)')
    key = hashlib.sha1(os.fsencode(root)).hexdigest()[:12]
    return os.path.join(os.path.expanduser('~/.claude/token-zombie'), 'slice', key, sid)


def _capture(root, rel, store, name):
    """Save the current state of one path -> entry dict."""
    p = os.path.join(root, rel)
    try:
        st = os.lstat(p)
    except (FileNotFoundError, NotADirectoryError):
        return dict(kind='absent')
    if stat.S_ISLNK(st.st_mode):
        return dict(kind='link', to=os.readlink(p))
    if not stat.S_ISREG(st.st_mode):
        return dict(kind='other')  # nested repo or submodule: never touched
    shutil.copyfile(p, os.path.join(store, name))
    return dict(kind='file', blob=name, mode=stat.S_IMODE(st.st_mode))


def _same(root, rel, e, store):
    p = os.path.join(root, rel)
    if e['kind'] == 'absent':
        return not os.path.lexists(p)
    if e['kind'] == 'link':
        return os.path.islink(p) and os.readlink(p) == e['to']
    if os.path.islink(p) or not os.path.isfile(p) or stat.S_IMODE(os.stat(p).st_mode) != e['mode']:
        return False
    with open(p, 'rb') as a, open(os.path.join(store, e['blob']), 'rb') as b:
        return a.read() == b.read()


def _put(root, rel, e, store):
    p = os.path.join(root, rel)
    real, parent = os.path.realpath(root), os.path.realpath(os.path.dirname(p))
    if parent != real and not parent.startswith(real + os.sep):
        raise SliceError('refusing to write outside the repo: ' + rel)
    if os.path.islink(p) or os.path.isfile(p):
        os.remove(p)
    elif os.path.isdir(p):
        os.rmdir(p)  # only an emptied directory; a non-empty one raises
    if e['kind'] == 'absent':
        d = os.path.dirname(rel)
        while d:
            try:
                os.rmdir(os.path.join(root, d))
            except OSError:
                break
            d = os.path.dirname(d)
        return
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if e['kind'] == 'link':
        os.symlink(e['to'], p)
    else:
        shutil.copyfile(os.path.join(store, e['blob']), p)
        os.chmod(p, e['mode'])


def _head_entry(root, head, rel, store, name):
    """State of a path that was clean at snapshot time: what a checkout of HEAD gives."""
    out = _git(root, '--literal-pathspecs', 'ls-tree', '-z', head, '--', rel)
    if not out:
        return dict(kind='absent')
    mode, typ, sha = out.split(b'\t', 1)[0].decode().split()
    if typ == 'tree':
        return dict(kind='absent')  # it was a directory: whatever file sits there now goes; its files come back one by one
    if typ != 'blob':
        return dict(kind='other')
    if mode == '120000':
        return dict(kind='link', to=os.fsdecode(_git(root, 'cat-file', 'blob', sha)))
    data = _git(root, 'cat-file', '--filters', '--path=' + rel, sha)  # applies eol/smudge filters
    with open(os.path.join(store, name), 'wb') as f:
        f.write(data)
    um = os.umask(0)
    os.umask(um)
    return dict(kind='file', blob=name, mode=(0o777 if mode == '100755' else 0o666) & ~um)


def counts(text):
    """Test counts from runner output ('212 passed', 'pass 3 fail 0'); the last line naming each wins."""
    c = {}
    for ln in text.splitlines():
        found = re.findall(r'(\d+) (passed|failed|skipped|errors?)\b', ln)
        found += [(n, w) for w, n in re.findall(r'^(?:# )?(pass|fail)(?:ed)?[ :]+(\d+)\b', ln.strip())]
        found += [(n, w) for w, n in re.findall(r'\b(fail)(?:ed)?[ :]+(\d+)\s*$', ln)]
        for n, w in found:
            c[{'pass': 'passed', 'fail': 'failed', 'error': 'errors'}.get(w, w)] = int(n)
    return c


def run_check(cmd, root, timeout):
    try:
        r = subprocess.run(cmd, cwd=root, capture_output=True, timeout=timeout)
        return dict(rc=r.returncode, counts=counts((r.stdout + b'\n' + r.stderr).decode('utf-8', 'replace')))
    except subprocess.TimeoutExpired:
        return dict(rc=124, counts={})
    except OSError:
        return dict(rc=127, counts={})


def matches(base, now):
    """The baseline is reproduced: same exit code, no fewer passes, no more failures/errors/skips (added passing tests are fine)."""
    b, n = base['counts'], now['counts']
    if now['rc'] != base['rc'] or ('passed' in b and n.get('passed', -1) < b['passed']):
        return False
    return all(n.get(k, 0) <= b.get(k, 0) for k in ('failed', 'errors', 'skipped'))


def _fmt(r):
    return 'exit %d%s' % (r['rc'], ''.join(', %d %s' % (v, k) for k, v in sorted(r['counts'].items())))


def _meta(root, sid):
    t = _read(os.path.join(_dir(root, sid), 'meta.json'))
    if t is None:
        raise SliceError('no snapshot for slice ' + sid)
    return json.loads(t)


def start(cwd, sid, cmd, allow_red=False, timeout=600):
    root = _root(cwd)
    d = _dir(root, sid)
    if os.path.exists(d):
        raise SliceError('slice %s already has a snapshot (interrupted run?): verify, restore or drop it first' % sid)
    if not cmd:
        raise SliceError('no verification command given after --')
    base = run_check(cmd, root, timeout)  # baseline BEFORE the snapshot, so the check's own artefacts are part of the pre-slice state
    if base['rc'] in (124, 127):
        raise SliceError('verification command did not run (%s)' % _fmt(base))
    if base['rc'] and not allow_red:
        raise SliceError('red baseline (%s): no behaviour-preserved claim possible; fix it or pass --allow-red' % _fmt(base))
    head = _git(root, 'rev-parse', 'HEAD').decode().strip()
    dirty = sorted(_dirty(root, head))
    size = sum(os.lstat(os.path.join(root, f)).st_size for f in dirty if os.path.isfile(os.path.join(root, f)))
    if size > MAX_SNAP:
        raise SliceError('uncommitted and untracked files exceed %d MB: commit or ignore them first' % (MAX_SNAP >> 20))
    os.makedirs(d, mode=0o700)
    try:
        files = {f: _capture(root, f, d, 'b%d' % i) for i, f in enumerate(dirty)}
        with open(os.path.join(d, 'meta.json'), 'w') as f:
            json.dump(dict(root=root, head=head, cmd=cmd, timeout=timeout, base=base, files=files), f)
    except BaseException:
        shutil.rmtree(d, ignore_errors=True)
        raise
    return base


def restore(cwd, sid):
    """Put the worktree back to the pre-slice bytes. What gets overwritten is saved first. Never writes the git index.
    -> (restored paths, directory holding the discarded versions)."""
    root = _root(cwd)
    d, m = _dir(root, sid), _meta(root, sid)
    if _git(root, 'rev-parse', 'HEAD').decode().strip() != m['head']:
        raise SliceError('HEAD moved since the snapshot: not forcing a restore over newer work (slice unrevertable)')
    drop = d + '.discarded'
    n = 0
    while os.path.exists(drop):
        n += 1
        drop = '%s.discarded%d' % (d, n)
    os.makedirs(drop, mode=0o700)
    todo, saved = [], {}
    for i, rel in enumerate(sorted(_dirty(root, m['head']) | set(m['files']))):
        e = m['files'].get(rel)
        store = d
        if e is None:
            e, store = _head_entry(root, m['head'], rel, drop, 'head%d' % i), drop
        if e['kind'] == 'other' or _same(root, rel, e, store):
            continue
        cur = _capture(root, rel, drop, 'd%d' % i)
        if cur['kind'] == 'other' and e['kind'] == 'absent':
            continue  # a directory or nested repo now sits there: leave it (its new files are listed on their own)
        saved[rel] = cur
        todo.append((rel, e, store))
    with open(os.path.join(drop, 'meta.json'), 'w') as f:
        json.dump(saved, f)
    # removals first (deepest first), so a path that turned from file into directory can come back
    for rel, e, store in sorted(todo, key=lambda t: (t[1]['kind'] != 'absent', -t[0].count('/') if t[1]['kind'] == 'absent' else 0)):
        _put(root, rel, e, store)
    shutil.rmtree(d)
    return [t[0] for t in todo], drop


def verify(cwd, sid, revert=True):
    """-> (exit code, marker lines). 0 verified, 1 reverted or left failing, 4 unstable (fail then pass)."""
    root = _root(cwd)
    m = _meta(root, sid)
    one = run_check(m['cmd'], root, m['timeout'])
    note = '' if not m['base']['rc'] else ' (red baseline: no behaviour-preserved claim)'
    if matches(m['base'], one):
        shutil.rmtree(_dir(root, sid))
        return 0, ['Verified %s: baseline reproduced%s' % (sid, note)]
    two = run_check(m['cmd'], root, m['timeout'])  # rerun once to detect a flake
    if matches(m['base'], two):
        return 4, ['Unstable %s: failed (%s) then passed; snapshot kept, review before trusting it' % (sid, _fmt(one))]
    why = 'baseline %s; now %s' % (_fmt(m['base']), _fmt(two))
    if not revert or os.environ.get('TZ_SLICE_REVERT') == '0':
        return 1, ['Failed %s: %s. Auto-revert off; snapshot kept (slice restore %s)' % (sid, why, sid)]
    done, drop = restore(root, sid)
    return 1, ['Reverted %s: %s. Pre-slice state restored (%d paths); discarded versions: %s' % (sid, why, len(done), drop)]


def _slice_cli(a):
    cmd = []
    if '--' in a:
        i = a.index('--')
        a, cmd = a[:i], a[i + 1:]
    flags = {x for x in a if x in ('--allow-red', '--no-revert')}
    a = [x for x in a if x not in flags]
    timeout = 600
    if '--timeout' in a:
        i = a.index('--timeout')
        timeout = int(a[i + 1])
        del a[i:i + 2]
    cwd = os.getcwd()
    if a == ['list']:
        base = os.path.dirname(_dir(_root(cwd), 'x'))
        print('\n'.join(sorted(x for x in (os.listdir(base) if os.path.isdir(base) else []) if '.' not in x)) or 'no open slices')
        return 0
    if len(a) != 2 or a[0] not in ('start', 'verify', 'restore', 'drop'):
        raise ValueError('slice start|verify|restore|drop ID, or slice list')
    op, sid = a
    if op == 'start':
        print('Baseline %s: %s' % (sid, _fmt(start(cwd, sid, cmd, '--allow-red' in flags, timeout))))
    elif op == 'verify':
        rc, lines = verify(cwd, sid, '--no-revert' not in flags)
        print('\n'.join(lines))
        return rc
    elif op == 'restore':
        done, drop = restore(cwd, sid)
        print('restored %d paths; discarded versions: %s\n%s' % (len(done), drop, '\n'.join(done)))
    else:
        root = _root(cwd)
        _meta(root, sid)
        shutil.rmtree(_dir(root, sid))
        print('dropped ' + sid)
    return 0


def _rank_cli(a):
    import argparse
    ap = argparse.ArgumentParser(prog='tzreplayrank rank')
    ap.add_argument('--log')
    ap.add_argument('--cwd', default='.')
    ap.add_argument('--requests', type=int)
    ap.add_argument('--add', action='append', default=[], metavar='TIER=FILE')
    ap.add_argument('--top', type=int, default=15)
    ap.add_argument('--json', action='store_true')
    o = ap.parse_args(a)
    extra = []
    for spec in o.add:
        tier, _, p = spec.partition('=')
        t = _read(p)
        if tier not in TIERS or t is None:
            raise ValueError('--add wants %s=FILE (readable): %s' % ('|'.join(TIERS), spec))
        extra.append((p, tier, len(t)))
    total, results = log_rank(o.log) if o.log else (0, [])
    if o.requests is not None:
        n, basis = o.requests, 'given'
    else:
        n, basis = (total, 'MEASURED from log') if total else (DEFAULT_REQUESTS, 'ASSUMED')
    given = {os.path.realpath(x[0]) for x in extra}
    rows = rank_items(extra + [x for x in discover(o.cwd) if os.path.realpath(x[0]) not in given], n)
    top = max(0, o.top)
    if o.json:
        print(json.dumps(dict(requests=n, basis=basis, files=rows[:top], results=results[:top])))
        return 0
    print('instruction files ranked by token size x replays [tokens EST=chars/4; every-turn = %d requests, %s; other tier weights ASSUMED]' % (n, basis))
    for r in rows[:top]:
        print('  %10s  %7d tok x %-5s %-7s %s' % (f"{r['cost']:,}", r['tok'], f"{r['replays']:g}", r['tier'], r['path']))
    if not rows:
        print('  none found')
    if o.log:
        print('tool results in the log ranked by token size x later requests that carried them [replays MEASURED, reset at compaction]')
        for r in results[:top]:
            print('  %10s  %7d tok, %d calls, %d replays  %s' % (f"{r['cost']:,}", r['tok'], r['calls'], r['replays'], r['label']))
    return 0


def main(argv):
    try:
        if argv[:1] == ['rank']:
            return _rank_cli(argv[1:])
        if argv[:1] == ['slice']:
            return _slice_cli(argv[1:])
    except SliceError as e:
        print('slice: %s' % e, file=sys.stderr)
        return 3
    except (ValueError, IndexError, OSError) as e:
        print('error: %s' % e, file=sys.stderr)
        return 2
    except SystemExit as e:  # argparse
        return e.code if isinstance(e.code, int) else 2
    print('usage: tzreplayrank rank [--log LOG] ... | slice start|verify|restore|drop ID [-- CMD...] | slice list', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
