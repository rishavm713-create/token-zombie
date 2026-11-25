#!/usr/bin/env python3
"""`tz impact NAME [--depth N]`: who calls a symbol, by depth, importing files, tests to run, risk level.
Idea from SylphxAI/repomap `impact` (MIT); independent code, stdlib only, Python call graph by function, other files by word."""
import ast, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tzmap

TEST = re.compile(r'(^|/)(tests?|spec)/|(^|/)(test_[^/]*|[^/]*_test\.py|[^/]*\.(test|spec)\.[jt]sx?)$')


def _py_funcs(path):
    """{qualified function: set of identifiers it uses}"""
    try:
        tree = ast.parse(open(path, encoding='utf-8', errors='ignore').read())
    except Exception:
        return None
    out = {}

    def walk(body, pre):
        for n in body:
            if isinstance(n, ast.ClassDef):
                walk(n.body, pre + n.name + '.')
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out[pre + n.name] = {x.id for x in ast.walk(n) if isinstance(x, ast.Name)} | \
                                    {x.attr for x in ast.walk(n) if isinstance(x, ast.Attribute)}
                walk(n.body, pre + n.name + '.')
    walk(tree.body, '')
    return out


def impact(root, name, depth=3):
    names, files, rel = {name}, {}, {}
    for p in tzmap._files(root):
        if p.endswith(('.py', '.js', '.ts', '.tsx', '.jsx', '.mjs', '.sh')):
            try:
                files[p] = open(p, encoding='utf-8', errors='ignore').read()
            except Exception:
                pass
    funcs = {p: _py_funcs(p) for p in files if p.endswith('.py')}
    layers, seen, frontier = [], set(), {name}
    for _ in range(depth):
        hit = set()
        for p, fs in funcs.items():
            for q, ids in (fs or {}).items():
                key = (tzmap._rel(p, root), q)
                if key not in seen and q.split('.')[-1] not in frontier and ids & frontier:
                    seen.add(key); hit.add(key)
        if not hit:
            break
        layers.append(sorted(hit))
        frontier = {q.split('.')[-1] for _, q in hit}
    word = re.compile(r'\b%s\b' % re.escape(name))
    users = sorted(tzmap._rel(p, root) for p, s in files.items() if word.search(s))
    called = {f for l in layers for f, _ in l}
    others = [u for u in users if u not in called]  # non-Python or module-level users
    tests = sorted({f for f in called | set(users) if TEST.search(f)})
    n = sum(len(l) for l in layers) + len(others)
    risk = 'HIGH' if n > 15 else 'MEDIUM' if n > 4 else 'LOW'
    return {'risk': risk, 'callers': layers, 'files': users, 'tests': tests, 'count': n}


def main(argv):
    if not argv or argv[0].startswith('-'):
        print('usage: tz impact NAME [--depth N]'); return 2
    d = int(argv[argv.index('--depth') + 1]) if '--depth' in argv else 3
    r = impact(os.getcwd(), argv[0], d)
    print('Impact of %s (%s risk, %d affected)' % (argv[0], r['risk'], r['count']))
    for i, l in enumerate(r['callers'], 1):
        print('depth %d: %s' % (i, ', '.join('%s:%s' % x for x in l[:25])))
    print('files mentioning it: ' + (', '.join(r['files'][:30]) or 'none'))
    print('tests to run: ' + (', '.join(r['tests']) or 'none found'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
