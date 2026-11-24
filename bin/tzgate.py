#!/usr/bin/env python3
# `tz gate`: independent verification of a worker's change. A worker saying "completed" is not evidence; this checks the repo itself.
# Checks: diff scope, file ownership, TZ Safe on added lines, secret scan, syntax, public-API compatibility (tzapi), tests (exit code AND tests actually ran), regression link, project-configured lint/type/audit, build, checkpoint.
# Status ladder: FAILED < GENERATED (files changed) < IMPLEMENTED (diff/safe/secret/ownership clean) < TESTED (tests and build pass).
# Repair is bounded: repair_prompt() is used at most MAX_REPAIRS times by the caller, then the run stops and reports.
import json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
MAX_REPAIRS = 2
SECRETS = [(r'AKIA[0-9A-Z]{16}', 'AWS access key'), (r'sk-[A-Za-z0-9]{20,}', 'API key (sk-)'), (r'ghp_[A-Za-z0-9]{30,}', 'GitHub token'),
           (r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE' + r' KEY-----', 'private key'),
           (r'(?i)(password|secret|api[_-]?key|token)\s*[:=]\s*[\'"][^\'"\s]{8,}[\'"]', 'hardcoded credential')]


def sh(args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True).stdout


def changed(cwd):
    """(tracked changed files, untracked files, added lines of both)."""
    tracked = sh(['git', 'diff', '--name-only', 'HEAD'], cwd).split()
    untracked = [f for f in sh(['git', 'ls-files', '--others', '--exclude-standard'], cwd).split() if not re.search(r'(^|/)(__pycache__|node_modules|\.pytest_cache)/|\.pyc$', f)]
    added = [l[1:] for l in sh(['git', 'diff', '-U0', 'HEAD'], cwd).splitlines() if l.startswith('+') and not l.startswith('+++')]
    for f in untracked:
        try:
            added += open(os.path.join(cwd, f), errors='ignore').read().splitlines()[:2000]
        except Exception:
            pass
    return tracked, untracked, added

NOTESTS = re.compile(r'collected 0 items|no tests ran|Ran 0 tests|No tests found|no test files|Tests:\s+0 total|0 passing', re.I)
CODE = ('.py', '.js', '.jsx', '.ts', '.tsx')


def have(tool):
    import shutil
    return shutil.which(tool) is not None


def read(cwd, f):
    try:
        return open(os.path.join(cwd, f), errors='ignore').read()
    except OSError:
        return ''


def detect_checks(cwd):
    """Lint, type and audit commands the PROJECT itself is configured for: [(check, command, binary)]. Nothing is invented:
    no config, no check. A configured tool that is not installed is reported as skipped, never as passed."""
    out, pyp, setup = [], read(cwd, 'pyproject.toml'), read(cwd, 'setup.cfg') + read(cwd, 'tox.ini')
    ex = lambda f: os.path.exists(os.path.join(cwd, f))
    if ex('ruff.toml') or ex('.ruff.toml') or '[tool.ruff' in pyp:
        out.append(('lint', 'ruff check .', 'ruff'))
    elif ex('.flake8') or '[flake8]' in setup:
        out.append(('lint', 'flake8 .', 'flake8'))
    if ex('mypy.ini') or '[tool.mypy' in pyp or '[mypy' in setup:
        out.append(('types', 'mypy .', 'mypy'))
    elif ex('pyrightconfig.json') or '[tool.pyright' in pyp:
        out.append(('types', 'pyright', 'pyright'))
    if ex('requirements.txt'):
        out.append(('audit', 'pip-audit -r requirements.txt', 'pip-audit'))
    if ex('package.json'):
        try:
            sc = json.loads(read(cwd, 'package.json')).get('scripts', {})
        except ValueError:
            sc = {}
        if 'lint' in sc:
            out.append(('lint', 'npm run --silent lint', 'npm'))
        ty = next((k for k in ('typecheck', 'type-check', 'tsc') if k in sc), None)
        if ty:
            out.append(('types', 'npm run --silent ' + ty, 'npm'))
        elif ex('tsconfig.json'):
            out.append(('types', 'npx --no-install tsc --noEmit', 'npx'))
        if ex('package-lock.json'):
            out.append(('audit', 'npm audit --audit-level=high', 'npm'))
    return out


def syntax(files, cwd):
    """Always-on zero-dependency syntax check of changed files (python ast, node --check)."""
    bad = []
    for f in files:
        p = os.path.join(cwd, f)
        if not os.path.isfile(p):
            continue
        if f.endswith('.py'):
            try:
                compile(open(p, errors='ignore').read(), f, 'exec')
            except SyntaxError as e:
                bad.append('%s line %s: %s' % (f, e.lineno, e.msg))
        elif f.endswith(('.js', '.mjs', '.cjs')) and have('node'):
            r = subprocess.run(['node', '--check', p], capture_output=True, text=True)
            if r.returncode:
                bad.append('%s: %s' % (f, r.stderr.strip().splitlines()[-1][:120] if r.stderr.strip() else 'syntax error'))
    return bad


def is_test(f):
    import tzapi
    b = os.path.basename(f)
    return tzapi.is_test_file(f) or '.test.' in b or '.spec.' in b


def relevance(files, cwd):
    """Changed code files that NO test file mentions by module name. Only meaningful when the repo has test files at all.
    Static link only (name appears in a test file): it shows a test could exercise the change, not that it does."""
    all_files = sh(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd).split()
    tests = [f for f in all_files if f.endswith(CODE) and is_test(f)]
    if not tests:
        return None
    text = {t: read(cwd, t) for t in tests}
    miss = []
    for f in files:
        if not f.endswith(CODE) or is_test(f) or any(is_test(g) for g in [f]):
            continue
        mod = os.path.splitext(os.path.basename(f))[0]
        if mod in ('__init__', 'index', 'main', 'conftest') or any(t in files for t in tests):
            continue
        if not any(re.search(r'\b%s\b' % re.escape(mod), t) for t in text.values()):
            miss.append(f)
    return miss


def gate(task, cwd='.', test=None, build=None, allow=None, run_id=None, timeout=600, allow_api=False, static=True):
    import tzops, tzagent, tzapi
    tracked, untracked, added = changed(cwd)
    files = tracked + untracked
    res = []
    add = lambda n, ok, d='': res.append({'check': n, 'ok': ok, 'detail': d})
    add('changes', bool(files), '%d file(s) changed' % len(files) if files else 'worker produced no changes')
    iss = [i for i in tzops.diffcheck(task, allow, cwd) if i != 'no changes vs HEAD']
    if allow:
        iss += ['outside task scope: ' + f for f in untracked if not any(f == a or f.startswith(a.rstrip('/') + '/') for a in allow)]
    add('diff', not iss, '; '.join(iss[:5]))
    try:
        owners = json.load(open(tzagent.owners_path()))
    except Exception:
        owners = {}
    clash = [f for f in files if owners.get(f) not in (None, task)]
    add('ownership', not clash, 'owned by another task: ' + ', '.join(clash) if clash else '')
    bad = [why for l in added for ok, why in [tzops.safe(l)] if not ok]
    add('safe', not bad, 'added line is destructive: ' + bad[0] if bad else '')
    leaks = sorted({why for l in added for pat, why in SECRETS if re.search(pat, l)})
    add('secrets', not leaks, ', '.join(leaks))
    sx = syntax(files, cwd)
    add('syntax', not sx, '; '.join(sx[:3]))
    api = tzapi.check(tracked, cwd)
    add('api', not api or allow_api, ('allowed (--allow-api-change): ' if api and allow_api else 'public interface changed: ') + '; '.join(api[:3]) if api else 'no public Python interface changed')
    for name, cmd in (('tests', test), ('build', build)):
        if cmd:
            try:
                p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
                out = p.stdout + p.stderr
                if p.returncode == 0 and name == 'tests' and NOTESTS.search(out):
                    add(name, False, 'command exited 0 but executed no tests: ' + NOTESTS.search(out).group(0))
                else:
                    add(name, p.returncode == 0, '' if p.returncode == 0 else out[-400:])
            except Exception as e:
                add(name, False, '%s: %s' % (type(e).__name__, e))
    if test:
        miss = relevance(files, cwd)
        if miss is not None:
            add('regression', not miss, 'changed code no test file mentions: ' + ', '.join(miss[:5]) if miss else 'every changed code file is referenced by a test file')
    for name, cmd, binary in (detect_checks(cwd) if static else []):
        if not have(binary):
            res.append({'check': name, 'ok': True, 'skipped': True, 'detail': 'skipped: %s configured but not installed (%s)' % (binary, cmd)}); continue
        try:
            p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
            o = p.stdout + p.stderr
            if name == 'audit' and p.returncode and re.search(r'ENOTFOUND|EAI_AGAIN|ECONNREFUSED|Connection|network|offline', o, re.I):
                res.append({'check': name, 'ok': True, 'skipped': True, 'detail': 'skipped: audit needs network (%s)' % cmd}); continue
            add(name, p.returncode == 0, '%s: ' % cmd + o[-300:] if p.returncode else cmd)
        except Exception as e:
            add(name, False, '%s: %s' % (type(e).__name__, e))
    if run_id:
        try:
            cp = json.load(open(os.path.join(tzagent.STATE, 'agent', run_id + '.json')))
            rows = cp.get('rows', cp) if isinstance(cp, dict) else cp
            add('checkpoint', bool(rows), '%d phase row(s) recorded' % len(rows))
        except Exception as e:
            add('checkpoint', False, 'unreadable: %s' % type(e).__name__)
    ok = lambda names: all(r['ok'] for r in res if r['check'] in names)
    core = ok(('changes', 'diff', 'ownership', 'safe', 'secrets', 'checkpoint', 'syntax', 'api'))
    ran = [r for r in res if r['check'] in ('tests', 'build') and not r.get('skipped')]
    extra = ok(('lint', 'types', 'audit', 'regression'))
    status = 'FAILED' if not res[0]['ok'] else 'GENERATED' if not core else 'TESTED' if ran and all(r['ok'] for r in ran) and extra else 'IMPLEMENTED' if not ran or (all(r['ok'] for r in ran) and not extra) else 'GENERATED'
    return status, res


def repair_prompt(task, res):
    """Bounded repair task built from failed checks only."""
    fails = ['- %s: %s' % (r['check'], r['detail']) for r in res if not r['ok']]
    hint = '\nKeep existing public function signatures exactly as they were; callers depend on them.' if any(r['check'] == 'api' and not r['ok'] for r in res) else ''
    hint += '\nAdd or extend a test that exercises the changed code.' if any(r['check'] == 'regression' and not r['ok'] for r in res) else ''
    return 'Repair task. Original task: %s\nThe independent gate failed these checks:\n%s\nFix only what these checks report; do not widen scope.%s' % (task, '\n'.join(fails), hint)


def main(argv):
    if argv and argv[0] == 'gate':
        argv = argv[1:]
    op = lambda k, d=None: argv[argv.index(k) + 1] if k in argv and argv.index(k) + 1 < len(argv) else d
    task = ' '.join(a for i, a in enumerate(argv) if not a.startswith('--') and (i == 0 or not argv[i - 1].startswith('--') or argv[i - 1] == '--allow-api-change')) or 'task'
    st, res = gate(task, os.getcwd(), op('--test'), op('--build'), op('--files').split(',') if op('--files') else None, op('--run'), allow_api='--allow-api-change' in argv)
    for r in res:
        print('%-10s %-4s %s' % (r['check'], 'skip' if r.get('skipped') else 'ok' if r['ok'] else 'FAIL', r['detail'][:160]))
    print('status: %s' % st)
    return 0 if all(r['ok'] for r in res) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
