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


def main(argv):
    r = detect(os.path.abspath(argv[0] if argv else os.getcwd()))
    print('standards (sampled %d files) [MEASURED from files, a guess about intent]' % r['files'])
    print('  indent: %s\n  quotes: mostly %s\n  tools: %s' % (r['indent'], r['quotes'], ', '.join(r['tools']) or 'none detected'))
    return 0 if r['files'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
