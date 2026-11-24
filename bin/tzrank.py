#!/usr/bin/env python3
# `tz rank [--focus FILE..] [--n N] [DIR]`: the most important definitions in a repo, ranked by who references them.
# Adapted from aider/repomap.py RepoMap.get_ranked_tags (https://github.com/Aider-AI/aider),
# Copyright 2023-2025 Paul Gauthier and Aider contributors, Apache License 2.0 (see NOTICE).
# Changes: tags come from tzmap.defs (ast/regex, no tree-sitter) and word-token references; networkx.pagerank
# replaced by a small power iteration; short names (<6) down-weighted; no disk cache, no chat/mention weights except --focus files.
import math, os, re, sys
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tzmap

EXT = ('.py', '.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.sh')
WORD = re.compile(r'[A-Za-z_][A-Za-z0-9_]{2,}')


def pagerank(nodes, edges, pers=None, d=0.85, it=50):
    """edges: {(src, dst): weight}. Weighted PageRank; dangling mass and teleport follow pers (uniform if None)."""
    n = len(nodes)
    if not n:
        return {}
    tot = sum(pers.values()) if pers else 0
    p = {k: (pers.get(k, 0) / tot if tot else 1 / n) for k in nodes}
    out = defaultdict(float)
    for (s, _), w in edges.items():
        out[s] += w
    r = dict(p)
    for _ in range(it):
        dang = sum(r[k] for k in nodes if not out[k])
        nr = {k: (1 - d) * p[k] + d * dang * p[k] for k in nodes}
        for (s, t), w in edges.items():
            nr[t] += d * r[s] * w / out[s]
        r = nr
    return r


def ranked(root, focus=()):
    """[(rank, file, ident)] best first. Same weighting as aider: x10 long snake/camel names, x0.1 private or
    defined in >5 files, sqrt(ref count), x50 refs from focus files; self-loop 0.1 for unreferenced defs."""
    defines, refs = defaultdict(set), defaultdict(list)
    for p in tzmap._files(root):
        if not p.endswith(EXT):
            continue
        rel = os.path.relpath(p, root)
        ds = {x.split()[-1] for x in tzmap.defs(p)}
        for x in ds:
            defines[x].add(rel)
        try:
            src = open(p, encoding='utf-8', errors='ignore').read()
        except Exception:
            continue
        c = Counter(WORD.findall(src))
        for x in ds:
            c[x] -= 1  # the definition itself is not a reference
        for w, k in c.items():
            refs[w].extend([rel] * k)
    edges = defaultdict(float); nodes = set()
    focus = {os.path.normpath(f) for f in focus}
    for ident, definers in defines.items():
        nodes |= definers
        if not refs.get(ident):
            for f in definers:
                edges[(f, f)] += 0.1
            continue
        mul = 1.0
        if len(ident) >= 8 and ('_' in ident or (any(ch.isupper() for ch in ident) and any(ch.islower() for ch in ident))):
            mul *= 10
        if ident.startswith('_') or len(ident) < 6:  # TZ: short names (open, text) are mostly plain words, not real references
            mul *= 0.1
        if len(definers) > 5:
            mul *= 0.1
        for referencer, k in Counter(refs[ident]).items():
            nodes.add(referencer)
            for f in definers:
                edges[(referencer, f, ident)] = mul * (50 if referencer in focus else 1) * math.sqrt(k)
    flat = defaultdict(float)
    for e, w in edges.items():
        flat[e[:2]] += w
    r = pagerank(nodes, flat, {f: 1.0 for f in focus if f in nodes} or None)
    out_w = defaultdict(float)
    for (s, _), w in flat.items():
        out_w[s] += w
    score = defaultdict(float)
    for e, w in edges.items():
        s, t = e[:2]
        ident = e[2] if len(e) > 2 else None
        if ident is None:
            continue
        score[(t, ident)] += r[s] * w / out_w[s]
    for ident, definers in defines.items():  # unreferenced defs keep a small score so they still list last
        for f in definers:
            score.setdefault((f, ident), r.get(f, 0) * 0.01)
    return sorted(((v, f, i) for (f, i), v in score.items() if f not in focus), reverse=True)


def main(argv):
    if argv and argv[0] == 'rank':
        argv = argv[1:]
    n = int(argv[argv.index('--n') + 1]) if '--n' in argv else 20
    focus = argv[argv.index('--focus') + 1:] if '--focus' in argv else []
    pos = [a for a in argv[:argv.index('--focus')] if '--focus' in argv] if focus else argv
    pos = [a for i, a in enumerate(pos) if a != '--n' and (i == 0 or pos[i - 1] != '--n')]
    root = os.path.abspath(pos[0] if pos else '.')
    rs = ranked(root, focus)[:n]
    for v, f, i in rs:
        print(f'  {v:.4f}  {f}: {i}')
    print(f'{len(rs)} top definition(s) by reference rank (aider-style PageRank, MEASURED from source)' if rs else 'no definitions found')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
