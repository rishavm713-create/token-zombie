#!/usr/bin/env python3
# `tz features [--md]`: the 69-feature board with honest status. D = done (command exists + tested), P = partial, M = missing (reason: host API or not built).
# '*' after a command marks a feature added in the 69-features upgrade. Source of truth: bin/tzfeatures.json.
import json, os, sys

NAME = {'D': 'DONE', 'P': 'PARTIAL', 'M': 'MISSING'}


def load():
    return json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tzfeatures.json')))


def main(argv):
    rows = load()
    c = {k: sum(1 for r in rows if r[3] == k) for k in 'DPM'}
    md = '--md' in argv
    B, R = ('**', '**') if md else ('\033[1;32m', '\033[0m')
    out = ['# TOKEN ZOMBIE: %d features. %d done, %d partial, %d missing\n' % (len(rows), c['D'], c['P'], c['M'])] if md else ['TOKEN ZOMBIE: %d features. %d done, %d partial, %d missing' % (len(rows), c['D'], c['P'], c['M'])]
    sec = ''
    for n, s, name, st, cmd in rows:
        if s != sec:
            sec = s; out.append(('\n## ' if md else '\n') + s)
        new = cmd.endswith('*')
        line = '%2s %-8s %s%s' % (n, NAME[st], name, '  -> tz ' + cmd.rstrip('*') if cmd != '-' else '  (not built)')
        out.append(('- ' if md else '') + (B + line + '  NEW' + R if new else line))
    print('\n'.join(out))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
