#!/usr/bin/env python3
# `tz pr [--base BRANCH]`: prepares a commit message and PR body from the real diff. Read-only: never commits, pushes or opens anything.
import json, os, re, subprocess, sys

SECRET = re.compile(r'AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{30,}|-----BEGIN [A-Z ]*PRIVATE[ ]KEY-----|(?:api[_-]?key|secret|token|password)\s*[=:]\s*["\'][^"\'\s]{12,}["\']', re.I)


def git(*a):
    r = subprocess.run(['git', *a], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ''


def checklist(run_tests=False):
    """Delivery checklist from the real tree: [(name, ok, detail)]. Tests are only run when run_tests is set."""
    root = git('rev-parse', '--show-toplevel') or os.getcwd()
    ls = [f for f in git('ls-files').splitlines() if os.path.isfile(os.path.join(root, f))]
    low = [f.lower() for f in ls]
    tests = [f for f in ls if re.search(r'(^|/)(tests?|spec)/|(^|/)test_[^/]*|_test\.\w+$|\.test\.\w+$', f)]
    out = [('tests present', bool(tests), '%d test file(s)' % len(tests) if tests else 'no test files tracked')]
    if run_tests:
        if os.path.isfile(os.path.join(root, 'tests/run_all.sh')):
            r = subprocess.run(['bash', 'tests/run_all.sh'], cwd=root, capture_output=True, text=True)
            out.append(('tests passing', r.returncode == 0, 'exit %d' % r.returncode))
        else:
            out.append(('tests passing', False, 'no tests/run_all.sh to run'))
    else:
        out.append(('tests passing', None, 'not run (use --run-tests)'))
    d = git('status', '--porcelain').splitlines()
    out.append(('clean tree', not d, 'clean' if not d else '%d uncommitted file(s)' % len(d)))
    out.append(('README', any(re.match(r'readme(\.\w+)?$', f) for f in low), 'README at repo root'))
    out.append(('changelog', any(re.match(r'(changelog|changes|history)(\.\w+)?$', f) for f in low), 'CHANGELOG at repo root'))
    ver = None
    for f in ('package.json', 'pyproject.toml', 'VERSION', 'version.txt', 'Cargo.toml'):
        fp = os.path.join(root, f)
        if os.path.isfile(fp):
            t = open(fp, errors='ignore').read()
            m = re.search(r'"version"\s*:\s*"([^"]+)"', t) if f == 'package.json' else re.search(r'^\s*version\s*=\s*["\']([^"\']+)', t, re.M) if f.endswith('.toml') else re.match(r'\s*(\d[\w.+-]*)', t)
            if m:
                ver = '%s %s' % (f, m.group(1)); break
    out.append(('version set', bool(ver), ver or 'no version in package.json/pyproject.toml/VERSION'))
    bad = []
    for f in ls:
        fp = os.path.join(root, f)
        if f.startswith('tests/') or os.path.getsize(fp) > 1000000:
            continue
        if re.search(r'(^|/)\.env($|\.)|\.pem$|id_rsa$', f):
            bad.append(f); continue
        if SECRET.search(open(fp, errors='ignore').read()):
            bad.append(f)
    out.append(('no secrets', not bad, 'none found' if not bad else 'possible secret in ' + ', '.join(bad[:5])))
    return out


def implemented(base=None):
    """What was implemented: commits, files changed, tests touched, task status. Read-only, from git + handoffs/tasks."""
    if not git('rev-parse', '--git-dir'):
        print('not a git repo: nothing to report'); return 1
    cur = git('rev-parse', '--abbrev-ref', 'HEAD')
    base = base or next((b for b in ('main', 'master') if b != cur and git('rev-parse', '--verify', b)), None)
    rng = '%s...HEAD' % base if base else ('HEAD~1' if git('rev-parse', '--verify', 'HEAD~1') else None)
    commits = git('log', '--format=%h %s', *([rng] if base else ['-5'])).splitlines()
    files = git('diff', '--name-status', rng).splitlines() if rng else []
    files += [l[:2].strip() + '\t' + l[3:] for l in git('status', '--porcelain').splitlines()]
    seen = {}
    for l in files:
        k, _, f = l.partition('\t')
        seen.setdefault(f, k)
    tests = [f for f in seen if re.search(r'(^|/)tests?/|(^|/)test_|_test\.|\.test\.', f)]
    print('IMPLEMENTED on %s (vs %s) [MEASURED from git]' % (cur, base or 'previous commit'))
    print('commits (%d):' % len(commits))
    for c in commits[:20]:
        print('  ' + c)
    print('files changed (%d):' % len(seen))
    for f, k in list(seen.items())[:40]:
        print('  %s %s' % (k, f))
    print('tests changed/added (%d): %s' % (len(tests), ', '.join(tests[:10]) or 'none'))
    try:
        import tznext
        ts = tznext.load(os.getcwd())
    except Exception:
        ts = {}
    if ts:
        print('tasks: %d of %d done' % (sum(t['status'] == 'done' for t in ts.values()), len(ts)))
        for t in list(ts.values())[:25]:
            print('  %s %s %s' % (t['status'], t['id'], t.get('title', '')[:60]))
    else:
        print('tasks: none recorded (tz next add <id> --title ...)')
    return 0


def main(argv):
    if 'implemented' in argv or '--implemented' in argv:
        return implemented(argv[argv.index('--base') + 1] if '--base' in argv else None)
    if 'check' in argv or '--check' in argv:
        if not git('rev-parse', '--git-dir'):
            print('not a git repo', file=sys.stderr); return 2
        cl = checklist('--run-tests' in argv)
        for n, ok, d in cl:
            print('  [%s] %-14s %s' % ('??' if ok is None else 'ok' if ok else 'XX', n, d))
        bad = [n for n, ok, _ in cl if ok is False]
        print('READY for delivery' if not bad else 'NOT READY: ' + ', '.join(bad))
        return 0 if not bad else 1
    base = argv[argv.index('--base') + 1] if '--base' in argv else 'main'
    if not git('rev-parse', '--git-dir'):
        print('not a git repo', file=sys.stderr); return 2
    br = git('rev-parse', '--abbrev-ref', 'HEAD')
    rng = '%s...HEAD' % base if git('rev-parse', '--verify', base) else 'HEAD~1'
    stat = git('diff', '--stat', rng) or git('diff', '--stat')
    files = [l.split('|')[0].strip() for l in stat.splitlines() if '|' in l]
    dirty = git('status', '--porcelain')
    subs = git('log', '--format=%s', rng).splitlines()
    top = sorted({f.split('/')[0] for f in files})
    subject = subs[0] if len(subs) == 1 else '%s: %d files in %s' % (br.split('/')[-1], len(files), ', '.join(top[:3]) or 'repo')
    tests = 'bash tests/run_all.sh' if os.path.isfile('tests/run_all.sh') else '(none detected)'
    print('Suggested commit/PR title:\n  ' + subject[:72])
    print('\nPR body:\n## Changes\n' + '\n'.join('- ' + s for s in subs[:15]) + '\n\n## Files (%d)\n%s' % (len(files), stat.splitlines()[-1] if stat else 'no diff'))
    print('\n## Verify\n- run: ' + tests + '\n- NOT yet run by tz pr (read-only); paste the result here before opening the PR')
    if dirty:
        print('\nuncommitted changes present (%d files): commit them first' % len(dirty.splitlines()))
    print('\nNothing was committed, pushed or opened. Needs your OK for each.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
