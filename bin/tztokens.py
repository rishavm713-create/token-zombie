#!/usr/bin/env python3
# `tz tokens [--days N] [--json]`: every token in every chat log (incl. subagent logs), by day and model, per category. MEASURED from logs; no blended total hides a category.
# Each API reply counted once (message id). Thinking is inside output. Cost is not shown here (tz price/attr do that, EST).
import collections, datetime as dt, glob, json, os, sys

CATS = ('input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens')


def scan(root, days=None):
    seen, by_day, by_model, n = set(), collections.defaultdict(lambda: [0] * 4), collections.defaultdict(lambda: [0] * 4), 0
    lim = (dt.datetime.now() - dt.timedelta(days=days)).timestamp() if days else 0
    for f in glob.glob(os.path.join(root, '**', '*.jsonl'), recursive=True):
        if os.path.getmtime(f) < lim:
            continue
        for ln in open(f, 'rb'):
            if b'"usage"' not in ln:
                continue
            try:
                d = json.loads(ln)
            except ValueError:
                continue
            m = d.get('message') if isinstance(d, dict) else None
            u = m.get('usage') if isinstance(m, dict) else None
            if not isinstance(u, dict):
                continue
            k = m.get('id') or d.get('uuid')
            if k in seen:
                continue
            seen.add(k); n += 1
            v = [u.get(c) or 0 for c in CATS]
            day = str(d.get('timestamp') or '')[:10] or 'unknown'
            for tbl, key in ((by_day, day), (by_model, m.get('model') or 'unknown')):
                for i in range(4):
                    tbl[key][i] += v[i]
    return n, by_day, by_model


def main(argv):
    days = int(argv[argv.index('--days') + 1]) if '--days' in argv else None
    n, bd, bm = scan(os.path.expanduser('~/.claude/projects'), days)
    if '--json' in argv:
        print(json.dumps(dict(replies=n, by_day=bd, by_model=bm, order=list(CATS)))); return 0
    tot = [sum(v[i] for v in bd.values()) for i in range(4)]
    print('tokens [MEASURED from chat logs] %d replies%s' % (n, ' (last %d days)' % days if days else ''))
    print('  total   input %d  output %d  cache_read %d  cache_write %d' % tuple(tot))
    for title, tbl in (('by model', bm), ('by day (latest 7)', dict(sorted(bd.items())[-7:]))):
        print(' ' + title)
        for k, v in sorted(tbl.items()):
            print('  %-28s in %-9d out %-9d cr %-11d cw %d' % ((k or '?')[:28], *v))
    return 0 if n else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
