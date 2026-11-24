#!/usr/bin/env python3
# tz safe|impact|diffcheck|run. Destructive-command rules follow the approach of cc-safety-net (MIT, J Liew); diff scope check follows
# the karpathy-skills idea of "every changed line traces to the task" (MIT, Joseph Kim). Rules rewritten here, no code copied.
import os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RULES = [
    (r'\bgit\s+reset\s+--hard', 'git reset --hard drops uncommitted work'),
    (r'\bgit\s+clean\s+-\w*[fd]', 'git clean deletes untracked files'),
    (r'\bgit\s+push\b.*(--force\b|-f\b)(?!-with-lease)', 'force push rewrites remote history'),
    (r'\bgit\s+(checkout|restore)\s+(--\s+)?\.(\s|$)', 'discards all working-tree changes'),
    (r'\bgit\s+branch\s+-D\b', 'git branch -D deletes an unmerged branch'),
    (r'\bgit\s+stash\s+(drop|clear)', 'stash drop loses saved work'),
    (r'\brm\s+-\w*[rR]\w*\s+(-\w+\s+)*(/|~|\$HOME|\*|\.)(\s|$)', 'rm -r on root, home, cwd or a wildcard'),
    (r'\bfind\b.*\s-delete\b', 'find -delete removes files in bulk'),
    (r'\b(mkfs|dd\s+if=.*of=/dev/)', 'writes to a raw device'),
    (r'\bchmod\s+-R\s+(777|000)', 'recursive chmod 777/000'),
    (r'(curl|wget)[^|]*\|\s*(sudo\s+)?(ba|z)?sh', 'pipes a download into a shell'),
    (r'\bDROP\s+(TABLE|DATABASE)\b|\bTRUNCATE\s+TABLE\b', 'drops data'),
]


def safe(cmd):
    """(ok, reason). Quoted text after echo/printf is not scanned."""
    c = re.sub(r"^\s*(echo|printf)\s.*$", '', cmd, flags=re.M)
    for pat, why in RULES:
        if re.search(pat, c, re.I if 'DROP' in pat else 0):
            return False, why
    return True, ''


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout


def impact(target, root='.'):
    """Files that import/call target (path or symbol). rg with git grep fallback."""
    sym = os.path.splitext(os.path.basename(target))[0]
    out = sh('git', '-C', root, 'grep', '-lIwE', sym) or ''
    hits = [f for f in out.split() if os.path.normpath(os.path.join(root, f)) != os.path.normpath(os.path.join(root, target))]
    tests = [f for f in hits if re.search(r'test|spec', f)]
    return sym, [f for f in hits if f not in tests], tests


def diffcheck(task, allow=None, root='.'):
    """Flags: files outside --files, debug leftovers, big diffs, lockfile/format churn. Returns list of strings."""
    names = sh('git', '-C', root, 'diff', '--name-only', 'HEAD').split()
    if not names:
        return ['no changes vs HEAD']
    issues = []
    for f in names:
        if allow and not any(f == a or f.startswith(a.rstrip('/') + '/') for a in allow):
            issues.append('outside task scope: ' + f)
    d = sh('git', '-C', root, 'diff', '-U0', 'HEAD')
    for m in re.finditer(r'^\+(?!\+\+)(.*(console\.log|debugger|print\(.*DEBUG|TODO|FIXME|pdb\.set_trace).*)$', d, re.M):
        issues.append('leftover: ' + m.group(1).strip()[:70])
    n = sum(1 for l in d.splitlines() if l[:1] in '+-' and l[:3] not in ('+++', '---'))
    if n > 400:
        issues.append('large diff: %d changed lines; split it' % n)
    for f in names:
        if re.search(r'package-lock|yarn\.lock|\.min\.', f):
            issues.append('generated/lock file changed: ' + f)
    return issues


STAGES = [('understand', 'tz map'), ('explore', 'tz reuse / tz similar'), ('plan', 'tz plan'), ('allocate', 'tz route'),
          ('build', 'tz agent "<task>" --worktree'), ('coordinate', 'tz coord'), ('verify', 'tz verify + tz diffcheck'),
          ('optimize', 'tz opt'), ('ship', 'tz pr'), ('remember', 'tz handoff')]


def run(task, go, test):
    print('tz run: %s' % task)
    for i, (n, c) in enumerate(STAGES, 1):
        print('%2d %-10s %s' % (i, n, c))
    if not go:
        print('dry: add --go to run the build stage (tz agent, budgeted, worktree). Local stages cost 0 tokens.')
        return 0
    import tzagent
    a = ['agent', task, '--worktree'] + (['--test', test] if test else [])
    return tzagent.main(a)


def main(argv):
    c, r = argv[0], argv[1:]
    if c == 'safe':
        ok, why = safe(' '.join(r))
        print('ok' if ok else 'BLOCK: ' + why)
        return 0 if ok else 2
    if c == 'impact':
        if not r:
            print('usage: tz impact FILE|SYMBOL', file=sys.stderr); return 2
        sym, src, tests = impact(r[0])
        print('%s: %d files reference it, %d tests' % (sym, len(src), len(tests)))
        for f in src[:30]: print('  ' + f)
        for f in tests[:10]: print('  test ' + f)
        return 0
    if c == 'diffcheck':
        words = [a for a in r if not a.startswith('--')]
        allow = r[r.index('--files') + 1].split(',') if '--files' in r else None
        if allow: words = [w for w in words if w != r[r.index('--files') + 1]]
        iss = diffcheck(' '.join(words), allow)
        print('\n'.join(iss) if iss else 'diff ok')
        return 1 if any(not i.startswith('no changes') for i in iss) else 0
    if c == 'run':
        t = r[r.index('--test') + 1] if '--test' in r else None
        words = [a for a in r if not a.startswith('--') and a != t]
        return run(' '.join(words), '--go' in r, t)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
