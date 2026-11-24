#!/usr/bin/env python3
# `tz bench harbor [--dataset NAME] [--n N]`: prints (or, with --run, runs) the Harbor/Terminal-Bench command for a tz agent vs plain claude A/B.
# Nothing is installed or downloaded; if harbor is missing it says how. Result numbers come only from Harbor itself (never invented here).
import shutil, subprocess, sys


def main(argv):
    op = lambda k, d: argv[argv.index(k) + 1] if k in argv else d
    ds, n = op('--dataset', 'terminal-bench@2.0'), op('--n', '5')
    cmds = ['harbor run -d %s -a claude-code -m claude-sonnet-5-5 -n %s   # control' % (ds, n),
            'CLAUDE_CONFIG_DIR=~/tzab/treatment harbor run -d %s -a claude-code -m claude-sonnet-5-5 -n %s   # treatment (tz installed)' % (ds, n)]
    if not shutil.which('harbor'):
        print('harbor not installed (nothing downloaded). Install: pipx install harbor-framework  (or uv tool install harbor). Then:')
        print('\n'.join('  ' + c for c in cmds)); return 1
    if '--run' in argv:
        return max(subprocess.call(c.split('   #')[0], shell=True) for c in cmds)
    print('\n'.join(cmds)); return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
