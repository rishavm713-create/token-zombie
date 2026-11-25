#!/usr/bin/env python3
# `tz find-code "task text" [--n N] [DIR]`: which files does this task touch? BM25-lite over file paths + definition names + the
# text head of each file, blended with tzrank personalization (aider-style PageRank seeded from the best BM25 files).
# `tzfind2.py --eval [DIR]`: hit@10 on this repo's own git history (commit subject -> files changed).
# Own implementation of Okapi BM25 (k1=1.2, b=0.75); aider (Apache-2.0, see NOTICE) only supplies the PageRank personalization in tzrank.
# (bin/tzfinder.py is the skill-catalog finder and `tz find` is handoff-note search: neither is the right home.)
import math, os, re, subprocess, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tzmap, tzrank

TEXT = ('.py', '.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.sh', '.md', '.json', '.html', '.css', '.txt', '.toml', '.yml', '.yaml')
STOP = set('the and for with from that this into when not are was add fix use get set new via all any make now only more less per out off one two'.split())
HEAD = 3000  # chars of file text indexed: enough for module docstrings/imports, cheap on big repos


def toks(s):
    """Lowercase word parts; snake/camel split, plus the whole identifier so exact names still match."""
    out = []
    for w in re.findall(r'[A-Za-z][A-Za-z0-9_]*', s):
        parts = [p.lower() for p in re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+', w)]
        out += [p for p in parts if len(p) > 2 and p not in STOP]
        if len(parts) > 1 and len(w) > 3:
            out.append(w.lower())
    return out


def index(root):
    """{file: Counter(term -> weighted tf)}: path x3, definition names x2, text head x1."""
    docs = {}
    for p in tzmap._files(root):
        if not p.endswith(TEXT):
            continue
        rel = os.path.relpath(p, root)
        try:
            if os.path.getsize(p) > 400_000:
                continue
            head = open(p, encoding='utf-8', errors='ignore').read(HEAD)
        except Exception:
            continue
        c = Counter()
        for t in toks(rel.replace('/', ' ').replace('.', ' ').replace('-', ' ')):
            c[t] += 3
        for d in tzmap.defs_methods(p):
            for t in toks(d.replace('.', ' ')):
                c[t] += 2
        for t in toks(head):
            c[t] += 1
        docs[rel] = c
    return docs


def bm25(docs, query, k1=1.2, b=0.75):
    """[(score, file)] best first; query terms de-duplicated."""
    q = set(toks(query))
    n = len(docs) or 1
    avg = sum(sum(c.values()) for c in docs.values()) / n or 1
    df = Counter(t for c in docs.values() for t in q if t in c)
    out = []
    for f, c in docs.items():
        ln = sum(c.values()); s = 0.0
        for t in q:
            if t in c:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * c[t] * (k1 + 1) / (c[t] + k1 * (1 - b + b * ln / avg))
        if s:
            out.append((s, f))
    return sorted(out, reverse=True)


def find(root, task, n=10, docs=None, seeds=2, blend=0.15):
    """[(score, file)]: BM25 order re-scored with tzrank PageRank personalized on the top `seeds` BM25 files and the task's identifiers."""
    docs = docs if docs is not None else index(root)
    bm = bm25(docs, task)
    if not bm:
        return []
    top = bm[0][0]
    score = {f: s / top for s, f in bm}
    if blend and seeds:
        idents, files = tzrank.extract_mentions(task, root)
        mf = {f for _, f in bm[:seeds]} | files
        fr = {}
        for v, f, _ in tzrank.ranked(root, (), idents, mf, tagless=True):
            fr[f] = fr.get(f, 0) + v  # file importance = sum of its definitions' rank, tagless files 0
        m = max(fr.values(), default=0) or 1
        for f in score:
            score[f] += blend * fr.get(f, 0) / m
    return sorted(((s, f) for f, s in score.items()), reverse=True)[:n]


def _git(root, *a):
    return subprocess.run(('git', '-C', root) + a, capture_output=True, text=True).stdout


def history(root, limit=300):
    """[(subject, [files])] for non-merge commits touching 1-8 existing files; the files are the ground truth."""
    out, cur = [], None
    for line in _git(root, 'log', '--no-merges', f'-{limit}', '--name-only', '--format=\x01%s').splitlines():
        if line.startswith('\x01'):
            cur = [line[1:], []]; out.append(cur)
        elif line and cur:
            cur[1].append(line)
    return [(s, fs) for s, fs in out if 1 <= len(fs) <= 8 and any(os.path.exists(os.path.join(root, f)) for f in fs)]


def evaluate(root, k=10, limit=300, **kw):
    """-> dict hit@k (any changed file in top k), recall@k (share of changed files), cases. BM25-only when blend=0."""
    docs = index(root); cases = history(root, limit); hit = rec = 0
    for subj, fs in cases:
        fs = [f for f in fs if f in docs]
        if not fs:
            continue
        got = {f for _, f in find(root, subj, k, docs, **kw)}
        hit += bool(got & set(fs)); rec += len(got & set(fs)) / len(fs)
    n = sum(1 for _, fs in cases if any(f in docs for f in fs)) or 1
    return {'hit': hit / n, 'recall': rec / n, 'cases': n}


def main(argv):
    argv = [a for a in argv if a not in ('find-code', 'find2')]
    n = int(argv[argv.index('--n') + 1]) if '--n' in argv else 10
    if '--n' in argv:
        i = argv.index('--n'); argv = argv[:i] + argv[i + 2:]
    if '--eval' in argv:
        argv.remove('--eval'); root = os.path.abspath(argv[0] if argv else '.')
        for name, kw in (('bm25 only', {'blend': 0}), ('bm25+tzrank', {})):
            r = evaluate(root, **kw)
            print(f'{name}: hit@10 {r["hit"]:.3f}, file recall@10 {r["recall"]:.3f} over {r["cases"]} commits [MEASURED]')
        return 0
    if not argv:
        print('usage: tz find-code "task text" [--n N]', file=sys.stderr); return 2
    root = os.path.abspath(argv[1] if len(argv) > 1 else '.')
    rs = find(root, argv[0], n)
    for s, f in rs:
        print(f'  {s:.3f}  {f}')
    print(f'{len(rs)} likely file(s) (BM25 + PageRank personalization, MEASURED from source)' if rs else 'no matching files')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
