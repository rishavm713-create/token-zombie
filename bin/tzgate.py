#!/usr/bin/env python3
# `tz gate`: independent verification of a worker's change. A worker saying "completed" is not evidence; this checks the repo itself.
# Checks: diff scope (tzops.diffcheck), file ownership (tzagent owners.json), TZ Safe on added lines, secret scan, tests, build, checkpoint.
# Status ladder: FAILED < GENERATED (files changed) < IMPLEMENTED (diff/safe/secret/ownership clean) < TESTED (tests and build pass).
# Repair is bounded: repair_prompt() is used at most MAX_REPAIRS times by the caller, then the run stops and reports.
import json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
MAX_REPAIRS = 2
SECRETS = [(r'AKIA[0-9A-Z]{16}', 'AWS access key'), (r'sk-[A-Za-z0-9]{20,}', 'API key (sk-)'), (r'ghp_[A-Za-z0-9]{30,}', 'GitHub token'),
           (r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----', 'private key'),
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


def gate(task, cwd='.', test=None, build=None, allow=None, run_id=None, timeout=600):
    import tzops, tzagent
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
    for name, cmd in (('tests', test), ('build', build)):
        if cmd:
            try:
                p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
                add(name, p.returncode == 0, '' if p.returncode == 0 else (p.stdout + p.stderr)[-400:])
            except Exception as e:
                add(name, False, '%s: %s' % (type(e).__name__, e))
    if run_id:
        try:
            cp = json.load(open(os.path.join(tzagent.STATE, 'agent', run_id + '.json')))
            rows = cp.get('rows', cp) if isinstance(cp, dict) else cp
            add('checkpoint', bool(rows), '%d phase row(s) recorded' % len(rows))
        except Exception as e:
            add('checkpoint', False, 'unreadable: %s' % type(e).__name__)
    core = all(r['ok'] for r in res if r['check'] in ('changes', 'diff', 'ownership', 'safe', 'secrets', 'checkpoint'))
    ran = [r for r in res if r['check'] in ('tests', 'build')]
    status = 'FAILED' if not res[0]['ok'] else 'GENERATED' if not core else 'TESTED' if ran and all(r['ok'] for r in ran) else 'IMPLEMENTED' if not ran else 'GENERATED'
    return status, res


def repair_prompt(task, res):
    """Bounded repair task built from failed checks only."""
    fails = ['- %s: %s' % (r['check'], r['detail']) for r in res if not r['ok']]
    return 'Repair task. Original task: %s\nThe independent gate failed these checks:\n%s\nFix only what these checks report; do not widen scope.' % (task, '\n'.join(fails))


def main(argv):
    if argv and argv[0] == 'gate':
        argv = argv[1:]
    op = lambda k, d=None: argv[argv.index(k) + 1] if k in argv and argv.index(k) + 1 < len(argv) else d
    task = ' '.join(a for i, a in enumerate(argv) if not a.startswith('--') and (i == 0 or not argv[i - 1].startswith('--'))) or 'task'
    st, res = gate(task, os.getcwd(), op('--test'), op('--build'), op('--files').split(',') if op('--files') else None, op('--run'))
    for r in res:
        print('%-10s %-4s %s' % (r['check'], 'ok' if r['ok'] else 'FAIL', r['detail'][:160]))
    print('status: %s' % st)
    return 0 if st in ('TESTED', 'IMPLEMENTED') else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
