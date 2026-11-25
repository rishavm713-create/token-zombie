#!/usr/bin/env python3
# `tz rank [--focus FILE..] [--n N] [--tokens N] [--mention TEXT] [--lines] [DIR]`: the most important definitions in a repo, ranked by who references them.
# Adapted from aider/repomap.py RepoMap.get_ranked_tags (https://github.com/Aider-AI/aider),
# Copyright 2023-2025 Paul Gauthier and Aider contributors, Apache License 2.0 (see NOTICE).
# Changes: tags come from tzmap.defs (ast/regex, no tree-sitter) and word-token references; networkx.pagerank
# replaced by a small power iteration; short names (<6) down-weighted; no disk cache.
# Also adapted: get_ranked_tags personalization (mentioned idents x10, mentioned files, path-part match) and
# get_ranked_tags_map_uncached token-budget binary search (--tokens); aider/coders/base.py get_ident_mentions idea.
# --tokens / --lines maps list key project files first and can show definition lines (tzaider, same source).
import math, os, re, sys
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tzaider, tzmap

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


def extract_mentions(text, root='.'):
    """(idents, files) named in free text: every identifier-like word, and words that are a file path or basename in root."""
    idents = set(re.findall(r'[A-Za-z_][A-Za-z0-9_]*', text))
    paths = {}
    for p in tzmap._files(root):
        rel = os.path.relpath(p, root)
        paths.setdefault(rel, rel); paths.setdefault(os.path.basename(rel), rel)
    toks = set(re.findall(r'[\w./-]+', text))
    return idents, {paths[t] for t in toks if t in paths}


def ranked(root, focus=(), mentioned_idents=(), mentioned_files=(), methods=False, tagless=False):
    """[(rank, file, ident)] best first. Same weighting as aider: x10 long snake/camel names, x0.1 private or
    defined in >5 files, sqrt(ref count), x50 refs from focus files; self-loop 0.1 for unreferenced defs."""
    defines, refs, qual = defaultdict(set), defaultdict(list), {}
    mentioned_idents = set(mentioned_idents); mentioned_files = {os.path.normpath(f) for f in mentioned_files}
    allf = set()
    for p in tzmap._files(root):
        if not p.endswith(EXT):
            continue
        rel = os.path.relpath(p, root); allf.add(rel)
        raw = (tzmap.defs_methods if methods else tzmap.defs)(p)
        ds = {x.split()[-1].split('.')[-1] for x in raw}  # methods rank by leaf name
        for x in raw:
            qual.setdefault((rel, x.split()[-1].split('.')[-1]), x.split()[-1])
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
        if ident in mentioned_idents:
            mul *= 10
        for referencer, k in Counter(refs[ident]).items():
            nodes.add(referencer)
            for f in definers:
                edges[(referencer, f, ident)] = mul * (50 if referencer in focus else 1) * math.sqrt(k)
    flat = defaultdict(float)
    for e, w in edges.items():
        flat[e[:2]] += w
    pers = {f: 1.0 for f in focus if f in nodes}
    if mentioned_idents or mentioned_files:  # aider personalization: base 100/N, mentioned file max(.,base), +base per path-part match
        base = 100 / max(len(nodes), 1); pers = {f: base for f in focus if f in nodes}
        for f in nodes:
            if f in mentioned_files:
                pers[f] = max(pers.get(f, 0), base)
            if {*f.split(os.sep), os.path.basename(f), os.path.splitext(os.path.basename(f))[0]} & mentioned_idents:
                pers[f] = pers.get(f, 0) + base
    r = pagerank(nodes, flat, pers or None)
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
    out = sorted(((v, f, qual.get((f, i), i)) for (f, i), v in score.items() if f not in focus), reverse=True)
    if tagless:  # aider appends files that carry no tags last, by node rank
        have = {f for _, f, _ in out}
        out += [(0.0, f, '') for f in sorted(allf - have - focus, key=lambda f: (-r.get(f, 0), f))]
    return out


def fit_budget(items, max_tokens, render, count=lambda s: len(s) // 4):
    """Aider token-budget bisect on tag count: start max_tokens//25 tags, stop within 15% error. -> (text, n_tags, tokens)."""
    lo, hi = 0, len(items)
    mid = min(max_tokens // 25, hi)
    best, best_n, best_t = '', 0, 0
    while lo <= hi:
        text = render(items[:mid]); t = count(text)
        err = abs(t - max_tokens) / max(max_tokens, 1)
        if (t <= max_tokens and t > best_t) or err < 0.15:
            best, best_n, best_t = text, mid, t
            if err < 0.15:
                break
        if t < max_tokens:
            lo = mid + 1
        else:
            hi = mid - 1
        mid = (lo + hi) // 2
    return best, best_n, best_t


def render_tags(rs):
    """Group ranked (v, file, ident) by file, files in first-seen (best-rank) order."""
    by = {}
    for _, f, i in rs:
        by.setdefault(f, []).append(i)
    return ''.join(f'{f}:\n' + ''.join(f'  {i}\n' for i in ids if i) for f, ids in by.items())


def main(argv):
    if argv and argv[0] == 'rank':
        argv = argv[1:]
    opt = {}
    for k in ('--tokens', '--mention'):  # value options; strip them so the old positional parsing is untouched
        if k in argv:
            i = argv.index(k); opt[k] = argv[i + 1]; argv = argv[:i] + argv[i + 2:]
    lines = '--lines' in argv
    methods = '--methods' in argv or lines or bool(opt)
    argv = [a for a in argv if a not in ('--methods', '--lines')]
    n = int(argv[argv.index('--n') + 1]) if '--n' in argv else 20
    focus = argv[argv.index('--focus') + 1:] if '--focus' in argv else []
    pos = [a for a in argv[:argv.index('--focus')] if '--focus' in argv] if focus else argv
    pos = [a for i, a in enumerate(pos) if a != '--n' and (i == 0 or pos[i - 1] != '--n')]
    root = os.path.abspath(pos[0] if pos else '.')
    if opt or lines:
        mi, mf = extract_mentions(opt.get('--mention', ''), root)
        rs = ranked(root, focus, mi, mf, methods=True, tagless=True)
        render = (lambda ts: tzaider.render_lines(root, ts)) if lines else render_tags
        if '--tokens' in opt:
            text, k, t = fit_budget(tzaider.with_important(root, rs, focus), int(opt['--tokens']), render)
            print(text, end='')
            print(f'{k} tag(s), ~{t} tokens [est chars/4] of budget {opt["--tokens"]}')
            return 0
        if lines:
            print(render(tzaider.with_important(root, rs[:n], focus)), end='')
            return 0
        rs = rs[:n]
    else:
        rs = ranked(root, focus, methods=methods)[:n]
    for v, f, i in rs:
        print(f'  {v:.4f}  {f}: {i}')
    print(f'{len(rs)} top definition(s) by reference rank (aider-style PageRank, MEASURED from source)' if rs else 'no definitions found')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
