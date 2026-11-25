# Stale-branch check before a full test run: failures on a branch behind main may already be fixed there.
#   tz stale [--dir D] [--base REF] [--json]     exit 0 fresh, 1 stale/diverged, 2 unknown
# Rebuilt from the behaviour documented by ultraworkers/claw-code (ROADMAP "Stale-branch detection before broad
# verification"); provenance unverified, so no upstream code, text or assets are used.
# Local refs only: never fetches, never merges or rebases.
import json, os, re, shlex, subprocess, sys

SHOWN = 3  # missing commit titles listed; more would cost context on every re-sent turn
SEPARATORS = {';', '&&', '||', '|', '&', '(', ')', '|&', ';;'}
WRAPPERS = {'rtk', 'time', 'nice', 'nohup', 'command', 'env', 'npx', 'bunx'}


def _git(cwd, *args):
    """stdout of one read-only git call, or None on any failure."""
    try:
        r = subprocess.run(['git', '-C', cwd, *args], capture_output=True, text=True, errors='replace', timeout=3)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _sha(cwd, ref):
    """Commit id of ref, or None."""
    return _git(cwd, 'rev-parse', '--verify', '--quiet', '--end-of-options', ref + '^{commit}')


def _base_refs(cwd):
    """Local and remote-tracking copy of the default branch (origin/HEAD, else main, else master)."""
    head = _git(cwd, 'symbolic-ref', '--quiet', 'refs/remotes/origin/HEAD') or ''
    names = [head.split('refs/remotes/origin/', 1)[1]] if 'refs/remotes/origin/' in head else ['main', 'master']
    for n in names:
        refs = [r for r in (n, 'origin/' + n) if _sha(cwd, r)]
        if refs:
            return refs
    return []


def _mid_rebase(cwd):
    """True while a rebase is in progress: HEAD is an intermediate commit, so freshness means nothing."""
    for d in ('rebase-merge', 'rebase-apply'):
        p = _git(cwd, 'rev-parse', '--git-path', d)
        if p and os.path.isdir(os.path.join(cwd, p)):
            return True
    return False


def check(cwd, base=None):
    """Freshness of HEAD: state fresh|stale|diverged|unknown, plus base, ahead, behind, missing titles."""
    out = {'state': 'unknown', 'base': base or '', 'ahead': 0, 'behind': 0, 'missing': [], 'why': ''}
    head = _sha(cwd, 'HEAD')
    if not head:
        return dict(out, why='not a git repository with a commit')
    if _mid_rebase(cwd):
        return dict(out, why='rebase in progress')
    best = None
    for ref in ([base] if base else _base_refs(cwd)):
        sha = _sha(cwd, ref)
        if not sha or _git(cwd, 'merge-base', sha, head) is None:  # unrelated or shallow history: counts would lie
            continue
        n = (_git(cwd, 'rev-list', '--left-right', '--count', f'{sha}...{head}') or '').split()
        if len(n) == 2 and (best is None or int(n[0]) > best[0]):  # whichever copy of main is further on wins
            best = (int(n[0]), int(n[1]), ref, sha)
    if not best:
        return dict(out, why='no comparable base branch')
    behind, ahead, ref, sha = best
    state = 'fresh' if not behind else 'diverged' if ahead else 'stale'
    titles = _git(cwd, 'log', '--no-show-signature', f'-{SHOWN}', '--format=%s', f'{head}..{sha}') if behind else ''
    missing = [re.sub(r'[\x00-\x1f\x7f]', ' ', t)[:60] for t in (titles or '').splitlines()]
    return dict(out, state=state, base=ref, ahead=ahead, behind=behind, missing=missing, head=head, base_sha=sha)


def _segments(command):
    """Command split into argv lists at shell operators, redirections dropped; [] when it cannot be parsed."""
    try:
        lex = shlex.shlex(command.replace('\\\n', ' ').replace('\n', ' ; '), posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        return []
    segs, cur, skip = [], [], False
    for t in tokens:
        if skip:
            skip = False
        elif t in SEPARATORS:
            segs.append(cur)
            cur = []
        elif t[:1] in '<>' or t.startswith('&>'):
            if cur and cur[-1].isdigit():
                cur.pop()  # the fd in 2>file
            skip = True
        else:
            cur.append(t)
    return [s for s in segs + [cur] if s]


def _unwrap(a):
    """argv without env assignments and common launch wrappers."""
    while a:
        if re.match(r'[A-Za-z_]\w*=', a[0]) or a[0] in WRAPPERS:
            a = a[1:]
        elif a[0] == 'timeout':
            a = a[1:]
            while a and a[0].startswith('-'):
                a = a[1:]
            a = a[1:]  # the duration
        elif a[:2] in (['poetry', 'run'], ['uv', 'run'], ['pipenv', 'run']):
            a = a[2:]
        elif re.fullmatch(r'python[\d.]*', os.path.basename(a[0])) and a[1:2] == ['-m']:
            a = a[2:]
        else:
            break
    return a


def _positional(args, valued=()):
    """Arguments that are neither flags nor the value of a flag listed in valued."""
    out, skip = [], False
    for x in args:
        if skip:
            skip = False
        elif x.startswith('-'):
            skip = x in valued
        else:
            out.append(x)
    return out


def _has(args, *flags):
    """True when any of the flags is present, as `-k x`, `-kx` or `--flag=x`."""
    return any(x == f or x.startswith(f + '=') or (len(f) == 2 and x.startswith(f)) for x in args for f in flags)


def _broad_argv(a):
    """True when argv runs a whole test suite (no file, name or package selector)."""
    prog, args = os.path.basename(a[0]), a[1:]
    if {'-h', '--help', '--version', '--collect-only', '--no-run'} & set(args):
        return False
    if prog in ('bash', 'sh', 'zsh') and args:
        prog, args = os.path.basename(args[0]), args[1:]
    if prog == 'run_all.sh':
        return not _positional(args)
    if prog in ('pytest', 'py.test'):
        pos = _positional(args, ('-n', '-p', '-c', '-o', '-W', '-r', '--maxfail', '--tb', '--rootdir', '--timeout', '--durations', '--cov'))
        return not _has(args, '-k', '-m', '--lf', '--last-failed') and all(p.rstrip('/') in ('.', 'tests', 'test', './tests') for p in pos)
    if prog == 'unittest':
        return not _has(args, '-k') and (not _positional(args) or args[:1] == ['discover'])
    if prog == 'cargo' and args[:1] == ['test']:
        own = args[1:args.index('--')] if '--' in args else args[1:]
        extra = args[len(own) + 2:]
        return not (_has(own, '-p', '--package', '--test', '--bin', '--lib', '--example', '--doc')
                    or _positional(own, ('-j', '--jobs', '--features', '--target', '--manifest-path', '--profile'))
                    or _positional(extra, ('--test-threads', '--skip', '--format', '--color')))
    if prog == 'go' and args[:1] == ['test']:
        return './...' in args and not _has(args, '-run')
    if prog in ('npm', 'yarn', 'pnpm', 'bun'):
        rest = args[1:] if args[:1] == ['run'] else args
        return rest[:1] == ['test'] and not _positional(rest[1:]) and not _has(args, '--filter', '--workspace', '-w', '-t')
    if prog == 'make':
        return args in (['test'], ['check'])
    if prog in ('jest', 'vitest'):
        pos = _positional(args[1:] if args[:1] == ['run'] else args, ('--config', '-c', '--maxWorkers', '--reporter'))
        return not pos and not _has(args, '-t', '--testNamePattern', '--onlyChanged', '-o', '--changed')
    if prog in ('tox', 'ctest', 'rspec'):
        return not _positional(args, ('-j', '-p')) and not _has(args, '-e', '-R', '-L')
    return False


def broad_test_dir(command, cwd):
    """Directory in which command runs a full test suite (following plain `cd`), or None."""
    for seg in _segments(command):
        if seg[0] == 'cd' and len(seg) == 2:
            cwd = os.path.normpath(os.path.join(cwd, os.path.expanduser(seg[1])))
            continue
        a = _unwrap(seg)
        if a and _broad_argv(a):
            return cwd
    return None


def message(r):
    """One short paragraph describing a stale result."""
    miss = '; '.join(f'"{t}"' for t in r['missing'])
    return (f"TOKEN ZOMBIE stale branch: HEAD is {r['behind']} commit(s) [actual] behind {r['base']}"
            f" ({r['state']}, {r['ahead']} ahead). Failures from this full test run may already be fixed there, so do not "
            f"debug them as new regressions yet. Missing commit titles (data): {miss}. Merge or rebase {r['base']} first, "
            "or run a targeted test. Local refs only (no fetch).")


def _first_time(session, key):
    """True once per session and (repo head, base head) pair; remembers it."""
    import tzopt
    p = os.path.join(tzopt.STATE, f'claw-stale-{re.sub(r"[^A-Za-z0-9_-]", "_", session)}.json')
    seen = tzopt._load(p, [])
    seen = seen if isinstance(seen, list) else []
    if key in seen:
        return False
    tzopt._save(p, (seen + [key])[-20:])
    return True


def hook(data):
    """PreToolUse(Bash): ('deny'|'warn', text) or ('', ''). A deny happens once, so a rerun goes through."""
    from tzlib import feature
    warn, block = feature('stale_warn'), feature('stale_block')
    if not (warn or block) or data.get('tool_name') != 'Bash':
        return '', ''
    cwd = broad_test_dir((data.get('tool_input') or {}).get('command') or '', data.get('cwd') or os.getcwd())
    if not cwd:
        return '', ''
    r = check(cwd)
    if r['state'] not in ('stale', 'diverged'):
        return '', ''
    # WHY once per pair: repeating the text costs context, and a repeated block would trap a deliberate stale test
    if not _first_time(data.get('session_id') or 'x', f"{r['head']}:{r['base_sha']}"):
        return '', ''
    if block:
        return 'deny', message(r) + ' Blocked once; rerun the same command to test this branch anyway.'
    return 'warn', message(r)


def main(argv):
    """CLI: report branch freshness."""
    import argparse
    ap = argparse.ArgumentParser(prog='tz stale', description='is this branch behind main? (local refs only)')
    ap.add_argument('--dir', default='.')
    ap.add_argument('--base', help='compare against this ref instead of the default branch')
    ap.add_argument('--json', action='store_true')
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return e.code
    r = check(os.path.abspath(a.dir), a.base)
    if a.json:
        print(json.dumps(r))
    elif r['state'] == 'unknown':
        print(f"unknown: {r['why']}")
    else:
        print(f"{r['state']}: {r['behind']} behind, {r['ahead']} ahead of {r['base']} [actual, local refs]")
        for t in r['missing']:
            print(f'  missing: {t}')
    return {'fresh': 0, 'unknown': 2}.get(r['state'], 1)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
