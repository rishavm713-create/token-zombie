#!/usr/bin/env python3
"""tz memsearch index|search|expand: progressive recall over Markdown. The files are the truth; the sqlite FTS5 index is
disposable and rebuildable. search prints short hits with ids; expand ID prints that hit's whole section. No network.
chunk / clean / split_long / extract_section and the incremental-index rules adapted from memsearch src/memsearch/chunker.py,
core.py, cli.py, scanner.py (MIT, Copyright (c) 2025 Zilliz Inc.), see NOTICE.
Changed: stdlib only; FTS5 bm25 replaces Milvus and embeddings; chunk ids carry no model name."""
import argparse, hashlib, json, os, re, sqlite3, sys

import tzmem

MAX, OVERLAP = 1500, 2
TOP_K, RRF_K = 3, 60
EXPAND_MAX = 6000  # WHY: expand output lands in the context window
EXT = ('.md', '.markdown')
HEAD = re.compile(r'^(#{1,6})\s+(.+)$')
COMMENT = re.compile(r'<!--.*?-->', re.DOTALL)
# ASCII punctuation only ends a sentence before space/end/CJK, so v1.2.3, e-mails and URLs stay whole
SENTENCE = re.compile(r'(?:……|…|[。！？；]\s*|[.!?;](?=\s|$|[一-鿿぀-ヿ가-힯])\s*)')
ANCHOR = re.compile(r'<!--\s*session:(\S+)\s+turn:(\S+)\s+transcript:(\S+)\s*-->')
USE_FTS = True  # tests flip it to exercise the BM25 fallback


def db_path():
    """The index file, beside the tz mem store."""
    return os.path.join(os.path.dirname(tzmem.db_path()), 'memsearch.db')


# ---------- chunking ----------
def clean(text):
    """Text without HTML comments (session/turn ids dilute ranking)."""
    return re.sub(r'\n{3,}', '\n\n', COMMENT.sub('', text)).strip()


def _meaningful(text):
    """True when something beyond headings and comments remains."""
    body = [ln for ln in COMMENT.sub('', text).splitlines() if not HEAD.match(ln)]
    return len('\n'.join(body).strip()) >= 2


def split_long(text, size):
    """Cut unbroken text into pieces <= size, at the last sentence end when there is one."""
    parts = []
    while len(text) > size:
        cut = 0
        for m in SENTENCE.finditer(text, 0, size):
            cut = m.end()
        cut = cut or size
        parts.append(text[:cut])
        text = text[cut:]
    return parts + [text] if text else parts


def _split_section(lines, base, size, overlap):
    """[(text, start, end)] of a big section: paragraph break first, then line, then sentence."""
    out, cur, first = [], [], 0

    def emit(content, a, b):
        content = content.strip()
        for part in split_long(content, size):
            part = part.strip()
            if clean(part):
                out.append((part, a, b))

    def tail():
        return cur[max(0, len(cur) - overlap):]

    for i, line in enumerate(lines):
        cur.append(line)
        text = '\n'.join(cur)
        brk = not line.strip() and i + 1 < len(lines)
        if len(text) >= size and brk:
            emit(text, base + first + 1, base + i + 1)
            cur = tail()
            first = i + 1 - len(cur)
        elif len(text) >= size and len(cur) > 1:  # roll the current line back into the next chunk
            cur.pop()
            emit('\n'.join(cur), base + first + 1, base + i)
            cur = tail() + [line]
            first = i - len(cur) + 1
        elif len(text) >= size:  # one line bigger than a chunk
            emit(text, base + first + 1, base + i + 1)
            cur, first = [], i + 1
        elif i == len(lines) - 1:
            emit(text, base + first + 1, base + i + 1)
            cur = []
    if cur:
        emit('\n'.join(cur), base + first + 1, base + len(lines))
    return out


def chunk(text, size=MAX, overlap=OVERLAP):
    """Heading-based chunks: dicts of content, heading, level, start, end (1-based, inclusive), hash."""
    lines = text.split('\n')
    heads = [(i, len(m.group(1)), m.group(2).strip()) for i, ln in enumerate(lines) for m in [HEAD.match(ln)] if m]
    if not heads or heads[0][0] > 0:
        heads.insert(0, (0, 0, ''))  # preamble
    out = []
    for n, (a, level, title) in enumerate(heads):
        b = heads[n + 1][0] if n + 1 < len(heads) else len(lines)
        sec = '\n'.join(lines[a:b]).strip()
        if not sec or not _meaningful(sec):
            continue
        parts = [(sec, a + 1, b)] if len(sec) <= size else _split_section(lines[a:b], a, size, overlap)
        out += [{'content': t, 'heading': title, 'level': level, 'start': s, 'end': e, 'hash': _sha(t)}
                for t, s, e in parts]
    return out


def _sha(s):
    return hashlib.sha256(s.encode('utf-8', 'replace')).hexdigest()[:16]


def chunk_id(source, c):
    """Stable id: a moved or edited chunk gets a new one, an unchanged one keeps it."""
    return _sha(f"markdown:{source}:{c['start']}:{c['end']}:{c['hash']}")


# ---------- index ----------
def _open(path):
    """Open (and create) the index; sets .fts when FTS5 is usable."""
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    c = sqlite3.connect(path, factory=tzmem._C)
    c.execute('CREATE TABLE IF NOT EXISTS chunks(rid INTEGER PRIMARY KEY, id TEXT UNIQUE, source TEXT, heading TEXT,'
              ' level INT, start INT, stop INT, hash TEXT, content TEXT)')
    c.execute('CREATE INDEX IF NOT EXISTS chunks_source ON chunks(source)')
    if USE_FTS:
        try:
            c.execute('CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(text)')
            c.fts = True
        except sqlite3.OperationalError:
            c.fts = False
    return c


def _under(path, root):
    return path == root or path.startswith(os.path.join(root, ''))


def _walk(root):
    """Markdown files below root; hidden files and dirs are skipped."""
    for d, dirs, names in os.walk(root):
        dirs[:] = sorted(x for x in dirs if not x.startswith('.'))
        for n in sorted(names):
            if not n.startswith('.') and n.lower().endswith(EXT) and os.path.isfile(os.path.join(d, n)):
                yield os.path.join(d, n)


def scan(paths):
    """(files, prune) for the paths; no paths = the current project's default memory files."""
    if not paths:
        root = os.path.realpath(os.getcwd())
        files = [os.path.realpath(f) for f in tzmem.files(root)]
        # WHY: the default set is narrow, so only rows whose file is gone are pruned (explicit indexes survive)
        return files, lambda s, live: _under(s, root) and not os.path.isfile(s)
    files, dirs = [], []
    for p in (os.path.realpath(os.path.expanduser(x)) for x in paths):
        if os.path.isdir(p):
            dirs.append(p)
            files += _walk(p)
        elif os.path.isfile(p):
            if p.lower().endswith(EXT):
                files.append(p)
        else:
            dirs.append(p)  # deleted path: drop what was indexed from it
    files = list(dict.fromkeys(os.path.realpath(f) for f in files))
    return files, lambda s, live: s not in live and any(_under(s, d) for d in dirs)


def _delete(c, rid):
    c.execute('DELETE FROM chunks WHERE rid=?', (rid,))
    if c.fts:
        c.execute('DELETE FROM fts WHERE rowid=?', (rid,))


def _index_file(c, source, text, force):
    """Sync one file's rows; returns (added, removed)."""
    want = {chunk_id(source, k): k for k in chunk(text)}
    have = dict(c.execute('SELECT id, rid FROM chunks WHERE source=?', (source,)).fetchall())
    drop = [i for i in have if force or i not in want]
    for i in drop:
        _delete(c, have.pop(i))
    added = 0
    for i, k in want.items():
        if i in have:
            continue
        rid = c.execute('INSERT INTO chunks(id,source,heading,level,start,stop,hash,content) VALUES(?,?,?,?,?,?,?,?)',
                        (i, source, k['heading'], k['level'], k['start'], k['end'], k['hash'], k['content'])).lastrowid
        if c.fts:
            c.execute('INSERT INTO fts(rowid, text) VALUES(?,?)', (rid, clean(k['content'])))
        added += 1
    return added, len([i for i in drop if i not in want])


def _read(path):
    with open(path, encoding='utf-8-sig', errors='replace') as f:
        return f.read()


def index(paths=(), force=False, db=None):
    """Incremental index; returns {'files','added','removed','failed'}. force re-writes every chunk of those files."""
    c = _open(db or db_path())
    try:
        files, prune = scan(list(paths))
        r = {'files': 0, 'added': 0, 'removed': 0, 'failed': []}
        for f in files:
            try:
                a, g = _index_file(c, f, _read(f), force)
            except (OSError, UnicodeError) as e:
                r['failed'].append(f'{f}: {e}')
                continue
            r['files'] += 1
            r['added'] += a
            r['removed'] += g
        live = set(files)
        for (s,) in c.execute('SELECT DISTINCT source FROM chunks').fetchall():
            if prune(s, live):
                for (rid,) in c.execute('SELECT rid FROM chunks WHERE source=?', (s,)).fetchall():
                    _delete(c, rid)
                    r['removed'] += 1
        c.commit()
        return r
    finally:
        c.close()


def rebuild(paths=(), db=None):
    """Re-create the rows from the Markdown; a damaged index file is thrown away first."""
    p = db or db_path()
    try:
        return index(paths, True, p)
    except sqlite3.DatabaseError as e:
        if isinstance(e, sqlite3.OperationalError):  # locked / disk full: the file is not damaged
            raise
        os.remove(p)
        return index(paths, True, p)


# ---------- recall ----------
def rrf(rankings, k=RRF_K):
    """Reciprocal rank fusion of ranked id lists, scaled so first in every list = 1.0."""
    score = {}
    for ranking in rankings:
        for n, i in enumerate(ranking, 1):
            score[i] = score.get(i, 0) + 1 / (k + n)
    top = len(rankings) / (k + 1) or 1
    return {i: s / top for i, s in score.items()}


def _ranked(c, toks, prefix):
    """Matching rows (id, source, heading, start, stop, hash, content), best bm25 first."""
    cols = 'c.id, c.source, c.heading, c.start, c.stop, c.hash, c.content'
    where, args = '', []
    if prefix:
        d = os.path.join(prefix, '')
        where, args = '(c.source = ? OR substr(c.source, 1, ?) = ?)', [prefix, len(d), d]
    if c.fts:
        m = ' OR '.join(f'"{t}"' for t in toks)
        q = (f'SELECT {cols} FROM fts JOIN chunks c ON c.rid = fts.rowid WHERE fts MATCH ?'
             + (f' AND {where}' if where else '') + ' ORDER BY bm25(fts), c.source, c.start')
        return c.execute(q, [m] + args)
    rows = c.execute(f'SELECT {cols} FROM chunks c' + (f' WHERE {where}' if where else ''), args).fetchall()
    docs = [(r, None, None, clean(r[6])) for r in rows]
    return [d[0] for _, d in tzmem._bm25(docs, ' '.join(toks), k1=1.2)]


def _unique(rows, n):
    """First n rows with distinct content (a note copied into HANDOFF.md shows once)."""
    out, seen = [], set()
    for r in rows:
        if r[5] not in seen:
            seen.add(r[5])
            out.append(r)
            if len(out) >= n:
                break
    return out


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0


def search(q, k=TOP_K, prefix=None, recent=False, db=None):
    """[dict(id, source, heading, start, end, score, snippet)] best first; [] for no index or no match."""
    p = db or db_path()
    toks = re.findall(r'\w+', q.lower())
    if not toks or k < 1 or not os.path.isfile(p):
        return []
    c = _open(p)
    try:
        prefix = os.path.realpath(prefix) if prefix else None
        rows = _unique(_ranked(c, toks, prefix), k * 3 if recent else k)
    finally:
        c.close()
    by = {r[0]: r for r in rows}
    ranks = [list(by)]
    if recent:
        ranks.append(sorted(by, key=lambda i: -_mtime(by[i][1])))
    score = rrf(ranks)
    return [{'id': i, 'source': by[i][1], 'heading': by[i][2], 'start': by[i][3], 'end': by[i][4],
             'score': round(score[i], 4), 'snippet': tzmem._snip(clean(by[i][6]), toks, 160)}
            for i in sorted(score, key=lambda i: -score[i])[:k]]


def extract_section(lines, start, level):
    """(text, first, last) of the section holding line `start`: its heading up to the next same or higher one."""
    a, b = start - 1, len(lines)
    if level > 0:
        for i in range(min(start, len(lines)) - 1, -1, -1):
            m = HEAD.match(lines[i])
            if m and len(m.group(1)) <= level:
                a = i
                break
        for i in range(start, len(lines)):
            m = HEAD.match(lines[i])
            if m and len(m.group(1)) <= level:
                b = i
                break
    return '\n'.join(lines[a:b]), a + 1, b


def expand(cid, around=None, db=None):
    """Full context of one hit, read from the file as it is now. around=N: the chunk plus N lines each side.
    Returns None for an unknown id; {'error':...} when the file or the chunk is gone."""
    p = db or db_path()
    if not os.path.isfile(p):
        return None
    c = _open(p)
    try:
        row = c.execute('SELECT source, heading, level, start, stop, hash FROM chunks WHERE id=?', (cid,)).fetchone()
    finally:
        c.close()
    if not row:
        return None
    source, heading, level, start, stop, h = row
    try:
        text = _read(source)
    except OSError:
        return {'error': f'source file not readable: {source} (run: tz memsearch index)'}
    # WHY: lines may have moved since indexing; find the same content again instead of showing the wrong section
    same = [k for k in chunk(text) if k['hash'] == h]
    if not same:
        return {'error': f'index is out of sync with {source} (run: tz memsearch index)'}
    k = min(same, key=lambda x: abs(x['start'] - start))
    lines = text.split('\n')
    if lines and not lines[-1]:
        lines.pop()
    if around is not None:
        a, b = max(0, k['start'] - 1 - around), min(len(lines), k['end'] + around)
        body, a, b = '\n'.join(lines[a:b]), a + 1, b
    else:
        body, a, b = extract_section(lines, k['start'], k['level'])
    out = {'id': cid, 'source': source, 'heading': k['heading'], 'start': a, 'end': min(b, len(lines)), 'content': body}
    m = ANCHOR.search(body)
    if m:
        out['anchor'] = dict(zip(('session', 'turn', 'transcript'), m.groups()))
    return out


# ---------- CLI ----------
def _args(argv):
    ap = argparse.ArgumentParser(prog='tz memsearch', description='search then expand over Markdown memory')
    sub = ap.add_subparsers(dest='cmd', required=True)
    i = sub.add_parser('index', help='incremental index (no PATH: HANDOFF.md, handoffs/, docs/ here)')
    i.add_argument('paths', nargs='*')
    i.add_argument('--force', action='store_true', help='rebuild these files from scratch')
    s = sub.add_parser('search', help='step 1: short hits with ids')
    s.add_argument('query', nargs='+')
    s.add_argument('-k', type=int, default=TOP_K)
    s.add_argument('--all', action='store_true', help='every indexed project, not only this folder')
    s.add_argument('--recent', action='store_true', help='also favour newer files')
    s.add_argument('--json', action='store_true')
    e = sub.add_parser('expand', help='step 2: the whole section of one hit')
    e.add_argument('id')
    e.add_argument('--lines', type=int, help='chunk plus N lines each side instead of the section')
    e.add_argument('--max', type=int, default=EXPAND_MAX, help='character cap, 0 = none')
    e.add_argument('--json', action='store_true')
    return ap.parse_args(argv)


def _cli_index(a):
    r = (rebuild if a.force else index)(a.paths)
    for f in r['failed']:
        print('failed:', f)
    print(f"indexed {r['files']} files: {r['added']} chunks written, {r['removed']} stale removed [actual] -> {db_path()}")
    return 1 if r['failed'] else 0


def _cli_search(a):
    hits = search(' '.join(a.query), a.k, None if a.all else os.getcwd(), a.recent)
    if a.json:
        print(json.dumps(hits, ensure_ascii=False))
    else:
        for h in hits:
            print(f"{h['id']}  {h['source']}:{h['start']}-{h['end']}  [{h['heading'] or '-'}] {h['snippet']}")
        print('more: tz memsearch expand ID' if hits else 'no match (run: tz memsearch index)')
    return 0 if hits else 1


def _cli_expand(a):
    r = expand(a.id, a.lines)
    if not r or 'error' in r:
        print(r['error'] if r else f'unknown id: {a.id}')
        return 1
    n = len(r['content'])
    if 0 < a.max < n:
        r['content'] = r['content'][:a.max]
        r['cut'] = n - a.max
    if a.json:
        print(json.dumps(r, ensure_ascii=False))
        return 0
    print(f"{r['source']} (lines {r['start']}-{r['end']})")
    if 'anchor' in r:
        print('session: {session}  turn: {turn}  transcript: {transcript}'.format(**r['anchor']))
    print('\n' + r['content'])
    if 'cut' in r:
        print(f"[cut {r['cut']} chars [actual]; --max 0 shows all]")
    return 0


def main(argv):
    """CLI entry; returns the exit code."""
    try:
        a = _args(argv)
    except SystemExit as e:
        return e.code
    try:
        return {'index': _cli_index, 'search': _cli_search, 'expand': _cli_expand}[a.cmd](a)
    except sqlite3.DatabaseError as e:
        print(f'index error: {e} (the index is disposable: tz memsearch index --force)')
        return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
