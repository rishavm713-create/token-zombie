#!/usr/bin/env python3
"""tz mem index|search "q": local full-text memory over handoffs/*.md, HANDOFF.md, docs/*.md. On demand only, never run from a hook.
Chunker adapted from memsearch (MIT, Copyright Zilliz) chunker.py: ~1500 chars, 2-line overlap, sha256[:16] ids; see NOTICE.
Store: ~/.claude/token-zombie/mem.db (sqlite FTS5; pure-python BM25 over the same table when FTS5 is missing)."""
import glob, hashlib, math, os, re, sqlite3, sys

CHUNK, OVERLAP = 1500, 2
SRC = ('HANDOFF.md', 'handoffs/*.md', 'docs/*.md')


def db_path():
    return os.path.join(os.path.expanduser('~'), '.claude', 'token-zombie', 'mem.db')


def chunks(text):
    """[(start_line, text)]: line-aligned chunks of ~CHUNK chars; each starts with the last OVERLAP lines of the previous one."""
    L = text.splitlines()
    out, cur, size, start = [], [], 0, 1
    for i, ln in enumerate(L, 1):
        if cur and size + len(ln) + 1 > CHUNK:
            out.append((start, '\n'.join(cur)))
            cur = cur[-OVERLAP:]
            start = i - len(cur)
            size = sum(len(x) + 1 for x in cur)
        cur.append(ln)
        size += len(ln) + 1
    if cur and (not out or len(cur) > OVERLAP):  # a tail of only overlap lines adds nothing
        out.append((start, '\n'.join(cur)))
    return [(s, t) for s, t in out if t.strip()]


def cid(path, start, text):
    return hashlib.sha256(f'{path}:{start}:{text}'.encode()).hexdigest()[:16]


class _C(sqlite3.Connection):
    fts = False


USE_FTS = True  # tests flip it to exercise the BM25 fallback


def _open(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    c = sqlite3.connect(path, factory=_C)
    c.execute('CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY, path TEXT, line INT, text TEXT)')
    try:
        if not USE_FTS:
            raise sqlite3.OperationalError('fts off')
        c.execute('CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(text, id UNINDEXED)')
        c.fts = True
    except sqlite3.OperationalError:
        c.fts = False
    return c


def files(root):
    seen = []
    for g in SRC:
        for f in sorted(glob.glob(os.path.join(root, g))):
            if os.path.isfile(f) and f not in seen:
                seen.append(f)
    return seen


def index(root, db=None):
    """Re-index root's files; unchanged chunks (same id) are kept. Returns (files, new, removed)."""
    c = _open(db or db_path())
    root = os.path.abspath(root)
    want, n_new = {}, 0
    for f in files(root):
        rel = os.path.relpath(f, root).replace(os.sep, "/")
        for s, t in chunks(open(f, encoding='utf-8', errors='ignore').read()):
            want[cid(rel, s, t)] = (rel, s, t)
    have = {r[0]: r[1] for r in c.execute('SELECT id, path FROM chunks')}
    # one db per machine, rows keyed by relative path: a re-index replaces rows with the same path
    paths = {v[0] for v in want.values()}
    gone = [i for i, p in have.items() if p in paths and i not in want]
    for i in gone:
        c.execute('DELETE FROM chunks WHERE id=?', (i,))
        if c.fts:
            c.execute('DELETE FROM fts WHERE id=?', (i,))
    for i, (rel, s, t) in want.items():
        if i not in have:
            c.execute('INSERT INTO chunks VALUES(?,?,?,?)', (i, rel, s, t))
            if c.fts:
                c.execute('INSERT INTO fts(text, id) VALUES(?,?)', (t, i))
            n_new += 1
    c.commit(); c.close()
    return len(paths), n_new, len(gone)


def _tok(s):
    return re.findall(r'[a-z0-9_]+', s.lower())


def _bm25(rows, q, k1=1.5, b=0.75):
    qt = set(_tok(q))
    docs = [(r, _tok(r[3])) for r in rows]
    N = len(docs) or 1
    avg = sum(len(d) for _, d in docs) / N or 1
    df = {t: sum(1 for _, d in docs if t in d) for t in qt}
    res = []
    for r, d in docs:
        sc = 0.0
        for t in qt:
            f = d.count(t)
            if f:
                sc += math.log(1 + (N - df[t] + .5) / (df[t] + .5)) * f * (k1 + 1) / (f + k1 * (1 - b + b * len(d) / avg))
        if sc > 0:
            res.append((sc, r))
    return sorted(res, key=lambda x: -x[0])


def search(q, k=5, db=None):
    """[(score, 'path:line', snippet)] best first. Empty when nothing matches or no index."""
    p = db or db_path()
    if not os.path.isfile(p):
        return []
    c = _open(p)
    try:
        toks = _tok(q)
        if not toks:
            return []
        if c.fts:
            m = ' OR '.join(f'"{t}"' for t in toks)
            rows = c.execute('SELECT c.path, c.line, c.text, bm25(fts) FROM fts JOIN chunks c ON c.id = fts.id WHERE fts MATCH ? ORDER BY bm25(fts) LIMIT ?', (m, k)).fetchall()
            return [(-r[3], f'{r[0]}:{r[1]}', _snip(r[2], toks)) for r in rows]
        rows = c.execute('SELECT id, path, line, text FROM chunks').fetchall()
        return [(sc, f'{r[1]}:{r[2]}', _snip(r[3], toks)) for sc, r in _bm25(rows, q)[:k]]
    finally:
        c.close()


def _snip(text, toks, n=200):
    for ln in text.splitlines():
        if any(t in ln.lower() for t in toks):
            return ln.strip()[:n]
    return text.strip()[:n]


def main(argv):
    if not argv or argv[0] not in ('index', 'search'):
        print('usage: tz mem index [DIR] | tz mem search "query" [-k N]'); return 2
    if argv[0] == 'index':
        f, n, g = index(argv[1] if len(argv) > 1 else os.getcwd())
        print(f'indexed {f} files: {n} new chunks, {g} stale removed -> {db_path()}'); return 0
    k = 5
    if '-k' in argv:
        i = argv.index('-k'); k = int(argv[i + 1]); argv = argv[:i] + argv[i + 2:]
    r = search(' '.join(argv[1:]), k)
    for sc, loc, sn in r:
        print(f'{loc}  [{sc:.2f}] {sn}')
    if not r:
        print('no match (run: tz mem index)')
    return 0 if r else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
