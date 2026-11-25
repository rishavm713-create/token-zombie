#!/usr/bin/env python3
# `tz standards [dir]`: detects the project's coding conventions from its files (sampled, read-only): indent, quotes, test/lint tools.
import collections, os, re, sys

EXT = ('.py', '.ts', '.tsx', '.js', '.jsx', '.sh')
SKIP = {'node_modules', '.git', 'dist', 'build', '__pycache__', '.venv'}


def files(root, cap=60):
    out = []
    for d, ds, fs in os.walk(root):
        ds[:] = [x for x in ds if x not in SKIP]
        out += [os.path.join(d, f) for f in fs if f.endswith(EXT)]
        if len(out) >= cap:
            break
    return out[:cap]


def detect(root):
    ind, q, n = collections.Counter(), collections.Counter(), 0
    for f in files(root):
        try:
            for l in open(f, errors='ignore').read().splitlines()[:300]:
                m = re.match(r'^(\t+| +)\S', l)
                if m:
                    ind['tabs' if m.group(1)[0] == '\t' else '%d-space' % min(len(m.group(1)), 4)] += 1 if len(m.group(1)) in (2, 4) or m.group(1)[0] == '\t' else 0
                q['single'] += l.count("'") ; q['double'] += l.count('"')
            n += 1
        except OSError:
            pass
    has = lambda *p: any(os.path.exists(os.path.join(root, x)) for x in p)
    tools = [k for k, v in {'pytest': has('pytest.ini', 'tests'), 'npm test': has('package.json'), 'eslint': has('.eslintrc', '.eslintrc.json', 'eslint.config.js'),
                            'prettier': has('.prettierrc', '.prettierrc.json'), 'ruff': has('ruff.toml', '.ruff.toml'), 'black/flake8': has('pyproject.toml', 'setup.cfg', '.flake8')}.items() if v]
    return dict(files=n, indent=ind.most_common(1)[0][0] if ind else 'unknown', quotes=('single' if q['single'] > q['double'] else 'double') if n else 'unknown', tools=tools)


LAYERS = [('models', 'domain', 'entities', 'schemas'), ('repositories', 'db', 'data'), ('services', 'core', 'lib', 'utils'), ('controllers', 'routes', 'api', 'handlers', 'views', 'ui', 'components')]  # low -> high; a lower layer must not import a higher one
STYLE = lambda n: 'snake' if re.fullmatch(r'[a-z0-9]+(_[a-z0-9]+)*', n) and '_' in n else 'kebab' if re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+)+', n) else 'camel' if re.fullmatch(r'[a-z]+[A-Z][A-Za-z0-9]*', n) else 'pascal' if re.fullmatch(r'[A-Z][a-z0-9]+([A-Z][a-z0-9]*)*', n) else 'plain'


def _layer(rel):
    for i, names in enumerate(LAYERS):
        if any(p in names for p in rel.replace('\\', '/').split('/')[:-1]):
            return i
    return None


def check(root):
    """Per-file violations against the conventions detected in this project (majority rules). Returns {file: [msg]}."""
    fl = files(root, 400)
    info = {}
    for f in fl:
        try:
            txt = open(f, errors='ignore').read()
        except OSError:
            continue
        rel = os.path.relpath(f, root).replace('\\', '/')
        lines = txt.splitlines()
        ind = collections.Counter('tabs' if m.group(1)[0] == '\t' else '%d-space' % len(m.group(1)) for m in (re.match(r'^(\t+| +)\S', l) for l in lines) if m and (m.group(1)[0] == '\t' or len(m.group(1)) in (2, 4)))
        q = (len(re.findall(r"'[^'\n]*'", txt)), len(re.findall(r'"[^"\n]*"', txt)))
        stem = os.path.splitext(os.path.basename(f))[0]
        fn = re.findall(r'^\s*(?:def|function)\s+([A-Za-z_]\w*)', txt, re.M) if f.endswith(('.py', '.js', '.ts', '.jsx', '.tsx')) else []
        imps = re.findall(r'^\s*(?:from|import)\s+([\w./]+)', txt, re.M) + re.findall(r"(?:require\(|from )['\"]([^'\"]+)", txt)
        info[rel] = dict(ind=ind.most_common(1)[0][0] if ind else None, q=q, stem=stem, fn=fn, imps=imps, ext=os.path.splitext(f)[1])
    cnt = lambda it: collections.Counter(it).most_common(1)[0][0] if it else None
    ind0 = cnt([i['ind'] for i in info.values() if i['ind']])
    q0 = cnt(['single' if i['q'][0] > i['q'][1] else 'double' for i in info.values() if sum(i['q'])])
    name0 = {e: cnt([STYLE(i['stem']) for i in info.values() if i['ext'] == e and STYLE(i['stem']) != 'plain']) for e in {i['ext'] for i in info.values()}}
    fn0 = cnt([('snake' if '_' in n else 'camel' if re.search(r'[a-z][A-Z]', n) else None) for i in info.values() for n in i['fn'] if i['ext'] == '.py' or True] or [])
    tops = {r.split('/')[0] for r in info if '/' in r}
    out = collections.defaultdict(list)
    for rel, i in info.items():
        if ind0 and i['ind'] and i['ind'] != ind0:
            out[rel].append(f'indent: file uses {i["ind"]}, project uses {ind0}')
        qq = 'single' if i['q'][0] > i['q'][1] else 'double'
        if q0 and sum(i['q']) >= 6 and qq != q0 and i['ext'] != '.sh':
            out[rel].append(f'quotes: file mostly {qq}, project mostly {q0}')
        st = STYLE(i['stem'])
        if name0.get(i['ext']) and st not in ('plain', name0[i['ext']]) and not i['stem'].startswith(('test', '_')):
            out[rel].append(f'naming: file name is {st}, project files are {name0[i["ext"]]}')
        for n in i['fn']:
            k = 'snake' if '_' in n.strip('_') else 'camel' if re.search(r'[a-z][A-Z]', n) else None
            if k and fn0 and k != fn0 and not n.startswith('__'):
                out[rel].append(f'naming: function {n} is {k}, project functions are {fn0}'); break
        # architecture: folder layout
        if '/' not in rel and 'src' in tops and 'test' not in i['stem'] and i['ext'] in ('.py', '.ts', '.js') and i['stem'] not in ('setup', 'conftest', 'index', 'main', 'app'):
            out[rel].append('architecture: source file at project root, but this project keeps code under src/')
        tdirs = [t for t in ('tests', 'test', '__tests__') if t in tops]
        if tdirs and re.search(r'(^test_|_test\.|\.test\.)', os.path.basename(rel)) and not set(rel.split('/')[:-1]) & {'tests', 'test', '__tests__'}:
            out[rel].append('architecture: test file outside %s/' % tdirs[0])
        lay = _layer(rel)
        if lay is not None:
            for imp in i['imps']:
                hi = _layer(imp.replace('.', '/') + '/x')
                if hi is not None and hi > lay and imp.lstrip('.') != '':
                    out[rel].append(f'architecture: layer violation, {rel.rsplit("/", 1)[0]} (layer {lay}) imports {imp} (higher layer {hi})'); break
    return out


def main(argv):
    r = detect(os.path.abspath(([a for a in argv if not a.startswith('--')] or [os.getcwd()])[0]))
    if '--check' in argv or '--violations' in argv:
        root = os.path.abspath(([a for a in argv if not a.startswith('--')] or [os.getcwd()])[0])
        v = check(root)
        print('standards check: %d file(s) with violations [MEASURED against detected majority conventions]' % len(v))
        for f in sorted(v):
            for m in v[f]:
                print('  %s: %s' % (f, m))
        return 1 if v else 0
    print('standards (sampled %d files) [MEASURED from files, a guess about intent]' % r['files'])
    print('  indent: %s\n  quotes: mostly %s\n  tools: %s' % (r['indent'], r['quotes'], ', '.join(r['tools']) or 'none detected'))
    return 0 if r['files'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
