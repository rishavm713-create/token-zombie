#!/usr/bin/env python3
# `tz pr [--base BRANCH]`: prepares a commit message and PR body from the real diff. Read-only: never commits, pushes or opens anything.
import os, subprocess, sys


def git(*a):
    r = subprocess.run(['git', *a], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ''


def main(argv):
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
