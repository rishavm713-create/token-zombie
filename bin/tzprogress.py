#!/usr/bin/env python3
# `tz progress`: project completion from the real task files (tz next). Percent = done / total tasks; no tasks = unknown, never invented.
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main(argv):
    import tznext
    ts = tznext.load(os.getcwd())
    if not ts:
        print('progress: UNKNOWN (no tasks; add with tz next add <id> --title ...)'); return 1
    n = {}
    for t in ts.values():
        n[t['status']] = n.get(t['status'], 0) + 1
    d = n.get('done', 0); pct = 100 * d // len(ts)
    print('progress %d%% (%d of %d tasks done) [MEASURED from task files]' % (pct, d, len(ts)))
    print('  ' + '  '.join('%s %d' % kv for kv in sorted(n.items())))
    print('  [%s%s]' % ('#' * (pct // 5), '.' * (20 - pct // 5)))
    rd = tznext.ready(ts)
    if rd:
        print('  next: %s %s' % (rd[0]['id'], rd[0]['title'][:50]))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
