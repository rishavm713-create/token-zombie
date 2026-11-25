#!/usr/bin/env python3
# Daily / weekly / monthly / session / 5h-block usage reports over ALL local Claude Code chat logs. Offline, stdlib only.
# adapted from ccusage rust/adapters/claude/src/{paths,dedupe,advisor,usage_wire,usage_wire/iterations,daily/record,
# daily/response_chain}.rs and rust/crates/ccusage-cli/src/home.rs (MIT, Copyright (c) 2025 ryoppippi), see NOTICE.
# Token counts are [actual] (read from the logs). Money is [est]: TZ's own list-price table (tzprice), never fetched.
import argparse, datetime as dt, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tzprice
from tzusage import blocks, _ts

TOK = ('inp', 'out', 'cw', 'cr')
JKEY = dict(inp='inputTokens', out='outputTokens', cw='cacheCreationTokens', cr='cacheReadTokens')
DAYS = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')


def roots():
    """projects/ directories: CLAUDE_CONFIG_DIR (comma list, config dir or projects dir) else XDG claude + ~/.claude."""
    env = [p.strip() for p in os.environ.get('CLAUDE_CONFIG_DIR', '').split(',') if p.strip()]
    if env:
        dirs = [os.path.normpath(os.path.expanduser(p)) for p in env]
        dirs = [os.path.dirname(d) if os.path.basename(d) == 'projects' and os.path.isdir(d) else d for d in dirs]
    else:
        home = os.path.expanduser('~')
        dirs = [os.path.join(os.environ.get('XDG_CONFIG_HOME') or os.path.join(home, '.config'), 'claude'),
                os.path.join(home, '.claude')]
    out, seen = [], set()
    for d in dirs:  # WHY realpath: a symlinked second config dir must not count every reply twice
        p = os.path.join(d, 'projects')
        r = os.path.realpath(p)
        if os.path.isdir(p) and r not in seen:
            seen.add(r)
            out.append(p)
    return out


def usage_files(rts):
    """(projects root, file) for every *.jsonl below the roots, in stable path order."""
    out = [(root, os.path.join(d, n)) for root in rts for d, _, names in os.walk(root) for n in names if n.endswith('.jsonl')]
    return sorted(out, key=lambda x: x[1])


def session_parts(root, path):
    """(session id, project path, project name) from the transcript location, including subagent files."""
    rel = os.path.relpath(path, root).split(os.sep)
    stem = rel[-1][:-6]
    if len(rel) == 2:
        return stem, rel[0], rel[0]
    cut = next((i for i in range(2, len(rel) - 1) if rel[i] == 'subagents'), None)
    i = cut - 1 if cut else len(rel) - 2
    if i < 0:
        return 'unknown', 'Unknown Project', 'unknown'
    return rel[i], os.sep.join(rel[:i]) or 'Unknown Project', rel[0] if len(rel) > 1 else 'unknown'


def _n(v):
    return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else 0


def _iterations(u, kind):
    v = u.get('iterations')
    return [x for x in v if isinstance(x, dict) and x.get('type') == kind] if isinstance(v, list) else []


def counts(u):
    """Token counts from one usage object; the 5m/1h cache split of all 'message' iterations wins over the top-level one."""
    its = _iterations(u, 'message')
    splits = [x.get('cache_creation') for x in its]
    if its and all(isinstance(s, dict) for s in splits):
        split = {k: sum(_n(s.get(k)) for s in splits) for k in ('ephemeral_5m_input_tokens', 'ephemeral_1h_input_tokens')}
    else:
        split = u.get('cache_creation')
    flat = _n(u.get('cache_creation_input_tokens'))
    has = isinstance(split, dict)
    w5 = _n(split.get('ephemeral_5m_input_tokens')) if has else flat
    w1h = _n(split.get('ephemeral_1h_input_tokens')) if has else 0
    c = dict(inp=_n(u.get('input_tokens')), out=_n(u.get('output_tokens')), cr=_n(u.get('cache_read_input_tokens')),
             cw=w5 + w1h, w5=w5, w1h=w1h)
    speed = u.get('speed')
    c['detail'] = ({'standard': 1, 'fast': 2}.get(speed, 0) if isinstance(speed, str) else 0, has)
    return c


def total(e):
    return sum(e[k] for k in TOK)


def _envelope(d):
    """(record, message) for a normal line or a subagent 'agent progress' line (data.message.message)."""
    m = d.get('message')
    if isinstance(m, dict) and isinstance(m.get('usage'), dict):
        return d, m
    p = d.get('data')
    p = p.get('message') if isinstance(p, dict) else None
    if isinstance(p, dict):
        m = p.get('message')
        if isinstance(m, dict) and isinstance(m.get('usage'), dict):
            return dict(p, sessionId=d.get('sessionId')), m
    return None, None


def _blocks_of(d, kind, field):
    """Values of `field` from the content blocks of one type on a log line."""
    m = d.get('message')
    c = m.get('content') if isinstance(m, dict) else None
    return [b.get(field) for b in c if isinstance(b, dict) and b.get('type') == kind] if isinstance(c, list) else []


def read_file(root, path):
    """Usage entries of one transcript (advisor iterations become their own entries). Bad lines are skipped."""
    sid, ppath, project = session_parts(root, path)
    nodes, out = {}, []  # nodes: uuid -> response chain, for logs that carry no requestId
    try:
        f = open(path, 'rb')
    except OSError:
        return out
    with f:
        for raw in f:
            if b'"usage"' not in raw and b'"tool_result"' not in raw:
                continue
            try:
                d = json.loads(raw.decode('utf-8', 'ignore'))
                rec, m = _envelope(d)
            except Exception:
                continue
            if not isinstance(d, dict):
                continue
            parent = nodes.get(d.get('parentUuid')) if isinstance(d.get('parentUuid'), str) else None
            uid = d.get('uuid') if isinstance(d.get('uuid'), str) else None
            if rec is None:  # a tool result for this response's own tool call keeps the chain; a prompt ends it
                ids = _blocks_of(d, 'tool_result', 'tool_use_id')
                if parent and uid and ids and all(i in parent['tools'] for i in ids):
                    nodes[uid] = parent
                continue
            ts = _ts(rec.get('timestamp'))
            if ts is None:
                continue
            u = m['usage']
            c = counts(u)
            mid = m.get('id') if isinstance(m.get('id'), str) and m.get('id') else None
            rid = rec.get('requestId') if isinstance(rec.get('requestId'), str) and rec.get('requestId') else None
            chain = None
            if mid and not rid:
                sig = (mid,) + tuple(c[k] for k in TOK)
                node = parent if parent and parent['sig'] == sig else dict(sig=sig, id=(path, len(out), uid), tools=set())
                node['tools'].update(x for x in _blocks_of(d, 'tool_use', 'id') if isinstance(x, str))
                chain = node['id']
                if uid:
                    nodes[uid] = node
            base = dict(ts=ts, session=sid, path=ppath, project=project, rid=rid, chain=chain,
                        uuid=uid, side=rec.get('isSidechain') is True)
            model = m.get('model') if isinstance(m.get('model'), str) else ''
            found = [dict(base, mid=mid, model=model, **c)]
            adv = [x for x in _iterations(u, 'advisor_message') if isinstance(x.get('model'), str) and x.get('model')]
            for n, x in enumerate(adv):  # billed separately from the main model's top-level totals
                found.append(dict(base, mid=mid and f'{mid}:advisor:{n}', model=x['model'], uuid=uid and f'{uid}:{n}',
                                  **counts(x)))
            out.extend(e for e in found if total(e))
    return out


def _better(a, b):
    """True when copy `a` should replace copy `b`: parent over sidechain, then more tokens, then more detail."""
    if a['side'] != b['side']:
        return b['side']
    if total(a) != total(b):
        return total(a) > total(b)
    return a['detail'] > b['detail']


def dedupe(entries):
    """One entry per API response, across all files: streamed block lines, resumed/copied logs and sidechain replays."""
    slots, link, keys, routes = [], [], {}, {}

    def find(i):
        while link[i] != i:
            i = link[i]
        return i

    for e in entries:
        mid, k = e['mid'], []
        if mid and e['rid']:
            k = [('r', mid, e['rid'])]
        elif mid:
            k = [('t', mid, e['session'], e['ts'])] + ([('c', mid, e['session'], e['chain'])] if e['chain'] else [])
        elif e['uuid']:
            k = [('u', e['uuid'])]
        hits = [find(keys[x]) for x in k if x in keys]
        route = (mid, e['session'])
        if mid and not (e['side'] and hits):  # a sidechain may replay the parent's reply under a new request id
            j = next((j for j in (find(r) for r in routes.get(route, ())) if j not in hits and (e['side'] or slots[j]['side'])), None)
            if j is not None:  # only one: two real parent calls must never be joined through a replay
                hits.append(j)
        if hits:
            i = hits[0]
            for j in dict.fromkeys(hits[1:]):
                if j != i:
                    if _better(slots[j], slots[i]):
                        slots[i] = slots[j]
                    slots[j], link[j] = None, i
            old = slots[i]
            if _better(e, old):
                slots[i] = e
            sessions = {e['session'], old['session']}
        else:
            i = len(slots)
            slots.append(e)
            link.append(i)
            sessions = {e['session']}
        for x in k:
            keys[x] = i
        if mid:
            for s in sessions:
                routes.setdefault((mid, s), {})[i] = 1
    return [e for e in slots if e is not None]


def load(rts=None):
    """All deduplicated usage entries from the local logs."""
    return dedupe([e for root, p in usage_files(roots() if rts is None else rts) for e in read_file(root, p)])


def cost(e):
    return tzprice.cost_usd(e['model'], e['inp'], e['out'], e['cr'], e['w5'], e['w1h'])


def summarize(entries):
    """Totals plus per-model split for one report row."""
    models = {}
    for e in entries:
        m = models.get(e['model'] or 'unknown')
        if m is None:
            m = models[e['model'] or 'unknown'] = dict.fromkeys([JKEY[k] for k in TOK], 0)
            m['cost'] = 0.0
        for k in TOK:
            m[JKEY[k]] += e[k]
        m['cost'] += cost(e)
    row = {JKEY[k]: sum(m[JKEY[k]] for m in models.values()) for k in TOK}
    row['totalTokens'] = sum(row.values())
    row['totalCost'] = round(sum(m['cost'] for m in models.values()), 6)
    row['modelsUsed'] = sorted(models)
    row['modelBreakdowns'] = []
    for name, m in sorted(models.items(), key=lambda x: -x[1]['cost']):
        b = dict(modelName=name, **m)
        b['cost'] = round(b['cost'], 6)
        if not tzprice.known(name):
            b['pricedAs'] = tzprice.DEFAULT
        row['modelBreakdowns'].append(b)
    return row


def unpriced(entries):
    return sorted({e['model'] or 'unknown' for e in entries if not tzprice.known(e['model'])})


def day(ts, zone=None):
    return dt.datetime.fromtimestamp(ts, zone).date()


def period(kind, d, start=6):
    """Bucket label for a date: the day, the week's first day (start: 0=Monday .. 6=Sunday) or YYYY-MM."""
    if kind == 'weekly':
        return (d - dt.timedelta(days=(d.weekday() - start) % 7)).isoformat()
    return d.strftime('%Y-%m') if kind == 'monthly' else d.isoformat()


def last_since(kind, n, today, start=6):
    """First date of a window holding the last n days / weeks / months, today's included."""
    if kind == 'weekly':
        return dt.date.fromisoformat(period(kind, today, start)) - dt.timedelta(weeks=n - 1)
    if kind == 'monthly':
        m = today.year * 12 + today.month - 1 - (n - 1)
        return dt.date(m // 12, m % 12 + 1, 1)
    return today - dt.timedelta(days=n - 1)


def report(entries, kind='daily', zone=None, start=6, order='asc', instances=False):
    """Rows for daily/weekly/monthly (optionally split by project) or session, plus grand totals."""
    name = dict(daily='date', weekly='week', monthly='month', session='sessionId')[kind]
    groups = {}
    for e in entries:
        if kind == 'session':
            key = (e['session'], e['path'])
        else:
            key = (period(kind, day(e['ts'], zone), start), e['project'] if instances else '')
        groups.setdefault(key, []).append(e)
    rows = []
    for (label, extra), es in groups.items():
        row = {name: label}
        if kind == 'session':
            row['projectPath'] = extra
            row['lastActivity'] = day(max(e['ts'] for e in es), zone).isoformat()
        elif instances:
            row['project'] = extra
        row.update(summarize(es))
        rows.append(row)
    sort = 'lastActivity' if kind == 'session' else name
    rows.sort(key=lambda r: (r[sort], r[name]), reverse=order == 'desc')
    return {kind: rows, 'totals': _totals(entries)}


def _totals(entries):
    t = summarize(entries)
    del t['modelsUsed'], t['modelBreakdowns']
    if unpriced(entries):
        t['unpricedModels'] = unpriced(entries)
    return t


def block_report(entries, now=None, active=False, order='asc'):
    """5-hour blocks (tzusage.blocks) over all logs, each with its models and cost [est: the provider window may differ]."""
    es = sorted(entries, key=lambda e: e['ts'])
    rows, i = [], 0
    iso = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat().replace('+00:00', 'Z')
    for b in blocks([(e['ts'], total(e)) for e in es], now):
        mine = []
        while not b['gap'] and i < len(es) and es[i]['ts'] <= b['last']:
            mine.append(es[i])
            i += 1
        if active and not b['active']:
            continue
        row = dict(startTime=iso(b['start']), endTime=iso(b['end']), isActive=b['active'], isGap=b['gap'], entries=len(mine))
        row.update(summarize(mine))
        if b['active']:
            row['burnRate'] = dict(tokensPerMinute=round(b['burn'], 1))
            row['projection'] = dict(totalTokens=b['projected'])
        rows.append(row)
    if order == 'desc':
        rows.reverse()
    return {'blocks': rows}


def render(kind, data, breakdown=False):
    """Plain text table for a report dict."""
    L = [f'{kind} usage: tokens [actual] from local Claude Code logs; cost [est] at TZ list prices as of {tzprice.AS_OF}']
    head = f"{'period':<22} {'input':>12} {'output':>12} {'cache write':>13} {'cache read':>14} {'total':>14} {'cost [est]':>11}"
    L.append(head)

    def line(label, r, c, tail=''):
        nums = ' '.join(f'{r[JKEY[k]]:>{w},}' for k, w in zip(TOK, (12, 12, 13, 14)))
        tot = sum(r[JKEY[k]] for k in TOK)
        return f'{label[:22]:<22} {nums} {tot:>14,} {"$%.2f" % c:>11}' + (f'  {tail}' if tail else '')
    for r in data[kind]:
        if kind == 'blocks':
            if r['isGap']:
                L.append(f"{r['startTime'][:16]}Z  (gap)")
                continue
            tail = f"ACTIVE ~{int(r['burnRate']['tokensPerMinute'])}/min, projected {r['projection']['totalTokens']:,} [est]" if r['isActive'] else ''
            L.append(line(r['startTime'][:16] + 'Z', r, r['totalCost'], tail))
        else:
            label = r.get('date') or r.get('week') or r.get('month') or r.get('sessionId')
            tail = r.get('project') or (f"{r['lastActivity']} {r['projectPath']}" if 'sessionId' in r else '')
            L.append(line(label, r, r['totalCost'], ' '.join(filter(None, [tail, ','.join(r['modelsUsed'])]))))
        if breakdown:
            L.extend(line('  ' + b['modelName'], b, b['cost']) for b in r['modelBreakdowns'])
    t = data.get('totals')
    if t:
        L.append(line('TOTAL', t, t['totalCost']))
    seen = (t or {}).get('unpricedModels') or sorted({b['modelName'] for r in data[kind] for b in r['modelBreakdowns'] if 'pricedAs' in b})
    if seen:
        L.append(f"no list price for {', '.join(seen)}: priced as {tzprice.DEFAULT} [est]")
    return '\n'.join(L)


def _date(v):
    for f in ('%Y%m%d', '%Y-%m-%d'):
        try:
            return dt.datetime.strptime(v, f).date()
        except ValueError:
            pass
    raise argparse.ArgumentTypeError(f'bad date {v!r} (use YYYYMMDD or YYYY-MM-DD)')


def _positive(v):
    if not v.isdigit() or int(v) < 1:
        raise argparse.ArgumentTypeError('must be a whole number, 1 or more')
    return int(v)


def parser():
    ap = argparse.ArgumentParser(prog='tz usage', description='Offline usage reports from local Claude Code logs.')
    ap.add_argument('kind', nargs='?', default='daily', choices=['daily', 'weekly', 'monthly', 'session', 'blocks'])
    ap.add_argument('--since', type=_date)
    ap.add_argument('--until', type=_date)
    ap.add_argument('--last', type=_positive, help='last N days / weeks / months')
    ap.add_argument('--project', help='only this project folder name')
    ap.add_argument('--id', help='session: only this session id (searches every project)')
    ap.add_argument('-w', '--start-of-week', default='sunday', choices=DAYS)
    ap.add_argument('--order', default='asc', choices=['asc', 'desc'])
    ap.add_argument('--breakdown', action='store_true', help='add one line per model')
    ap.add_argument('--instances', action='store_true', help='split date rows by project')
    ap.add_argument('--active', action='store_true', help='blocks: only the active block')
    ap.add_argument('--timezone', help='IANA name; default is the local zone')
    ap.add_argument('--json', action='store_true')
    return ap


def main(argv=None):
    ap = parser()
    a = ap.parse_args(sys.argv[1:] if argv is None else argv)
    if a.last and (a.since or a.until or a.kind in ('session', 'blocks')):
        ap.error('--last works with daily/weekly/monthly and not with --since/--until')
    zone = None
    if a.timezone:
        try:
            from zoneinfo import ZoneInfo
            zone = ZoneInfo(a.timezone)
        except Exception:
            ap.error(f'unknown time zone {a.timezone!r} (or no time zone data on this system)')
    rts = roots()
    if not rts:
        print('tz usage: no Claude Code log folder found (UNAVAILABLE); set CLAUDE_CONFIG_DIR', file=sys.stderr)
        return 1
    start = DAYS.index(a.start_of_week)
    es = load(rts)  # WHY filter after dedup: the original of a replayed reply may lie outside the window
    since = last_since(a.kind, a.last, dt.datetime.now(zone).date(), start) if a.last else a.since
    if since or a.until:
        es = [e for e in es if (not since or day(e['ts'], zone) >= since) and (not a.until or day(e['ts'], zone) <= a.until)]
    if a.id:
        es = [e for e in es if e['session'] == a.id]
    elif a.project:
        es = [e for e in es if e['project'] == a.project]
    if a.kind == 'blocks':
        data = block_report(es, active=a.active, order=a.order)
    else:
        data = report(es, a.kind, zone, start, a.order, a.instances)
    if a.json:
        print(json.dumps(dict(data, labels=dict(tokens='actual', cost='est', pricesAsOf=tzprice.AS_OF))))
    elif not data[a.kind]:
        print(f'{a.kind} usage: no usage found for this selection')
    else:
        print(render(a.kind, data, a.breakdown))
    return 0


if __name__ == '__main__':
    sys.exit(main())
