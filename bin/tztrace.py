#!/usr/bin/env python3
# `tz trace`: a chat log as traces (one per user prompt) of observations (GENERATION / TOOL / AGENT) with cost per trace.
# Local and read-only: no SDK, network or telemetry; prompt and tool content never leave the log (--json carries none).
# Trace model, usage/cost details, provided-cost precedence, aggregation and tree rollup adapted from langfuse/langfuse (MIT, not the
# ee/ dirs, (c) 2023-2026 ClickHouse, Inc.), see NOTICE: packages/shared/src/domain/{traces,observations}.ts,
# packages/shared/src/server/pricing-tiers/calculateModelUsageCosts.ts, worker/src/services/IngestionService/index.ts,
# web/src/features/traces/fns/{calculateAggregatedUsage,traceAggregation,treeBuilding}.ts
import glob, json, math, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tzprice
from tztoolprune import _is_prompt
from tzusage import _ts, find_transcript

AGENT_TOOLS = ('Task', 'Agent')


def normalize_usage(raw):
    """Keep numeric buckets >= 0; add `total` (sum of buckets) when the source gave none."""
    out = {}
    for k, v in (raw or {}).items():
        try:
            n = float(v) if v is not None and not isinstance(v, bool) else -1
        except (TypeError, ValueError):
            continue
        if n >= 0 and math.isfinite(n):
            out[k] = int(n) if n.is_integer() else n
    if out and 'total' not in out:
        out['total'] = sum(out.values())
    return out


def usage_details(u):
    """Anthropic `usage` block -> usage buckets; cache writes are split by TTL because they are priced differently."""
    cc = u.get('cache_creation') if isinstance(u.get('cache_creation'), dict) else {}
    w1h = cc.get('ephemeral_1h_input_tokens') or 0
    # WHY max(): old logs give only the aggregate, so whatever is not marked 1 h counts as the 5 min write
    w5 = max(cc.get('ephemeral_5m_input_tokens') or 0, (u.get('cache_creation_input_tokens') or 0) - w1h)
    return normalize_usage({'input': u.get('input_tokens') or 0, 'output': u.get('output_tokens') or 0,
                            'cache_read_input_tokens': u.get('cache_read_input_tokens') or 0,
                            'input_cache_creation_5m': w5, 'input_cache_creation_1h': w1h})


def rates(model):
    """USD per Mtok for each usage bucket, from the single tzprice table [est]."""
    pin, pout = tzprice.price(model)
    c = tzprice.CACHE
    return {'input': pin, 'output': pout, 'cache_read_input_tokens': pin * c['read'],
            'input_cache_creation_5m': pin * c['write_5m'], 'input_cache_creation_1h': pin * c['write_1h']}


def price_usage(model, usage, provided=None):
    """(cost details, total or None, source). A supplied cost switches off list-price inference for every bucket."""
    given = {k: v for k, v in (provided or {}).items() if v is not None}
    if given:
        total = given.get('total')
        if total is None and set(given) <= {'input', 'output'}:
            total = sum(given.values())
        source, cost = 'recorded', given
    else:
        r = rates(model)
        cost = {k: n * r[k] / 1e6 for k, n in (usage or {}).items() if k in r}
        total = sum(cost.values()) if cost else None
        source = 'list' if cost else None
    if total is not None:
        cost['total'] = total
    return cost, total, source


def aggregated(details):
    """input / output / total from one detail dict or a list: keys are matched by the words `input` and `output`."""
    merged = {}
    for d in details if isinstance(details, list) else [details]:
        for k, v in (d or {}).items():
            merged[k] = merged.get(k, 0) + (v or 0)
    i = sum(v for k, v in merged.items() if 'input' in k)
    o = sum(v for k, v in merged.items() if 'output' in k)
    return {'input': i, 'output': o, 'total': merged.get('total', i + o)}


def aggregate(observations):
    """Trace metrics: cost summed over all observations (None if none has one), usage over generations only."""
    costs = [o['totalCost'] for o in observations if o.get('totalCost') is not None]
    cd, ud = {}, {}
    for o in observations:
        for dst, src in ((cd, o.get('costDetails')), (ud, o.get('usageDetails') if o.get('type') == 'GENERATION' else None)):
            for k, v in (src or {}).items():
                dst[k] = dst.get(k, 0) + v
    return dict(totalCost=sum(costs) if costs else None, costDetails=cd, usageDetails=ud, usage=aggregated(ud))


def tree(observations):
    """Pre-order [(depth, observation, subtree cost or None)]. Iterative; duplicate ids, orphans and cycles are safe."""
    byid = {}
    for o in sorted(observations, key=lambda o: o.get('startTime') or 0):
        byid.setdefault(o['id'], o)  # WHY earliest wins: a repeated id would otherwise hang under several parents
    kids, roots = {i: [] for i in byid}, []
    for i, o in byid.items():
        p = o.get('parentObservationId')
        (kids[p] if p in byid and p != i else roots).append(i)
    order, seen = [], set()
    for r in roots + list(byid):  # the second pass picks up cycle members no root reaches
        stack = [(r, 0)]
        while stack:
            i, d = stack.pop()
            if i not in seen:
                seen.add(i)
                order.append((i, d))
                stack += [(c, d + 1) for c in reversed(kids[i])]
    sub = {}
    for i, _ in reversed(order):
        parts = [c for c in [byid[i].get('totalCost')] + [sub.get(k) for k in kids[i]] if c]
        sub[i] = sum(parts) if parts else None
    return [(d, byid[i], sub[i]) for i, d in order]


def _rows(path):
    """JSON objects of a transcript; unreadable files and broken lines are skipped."""
    try:
        with open(path, errors='replace') as f:
            for line in f:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if isinstance(d, dict):
                    yield d
    except OSError:
        return


def _obs(oid, kind, name, ts, parent, turn):
    """A new observation record."""
    return dict(id=oid, type=kind, name=name, startTime=ts, endTime=ts, parentObservationId=parent, level='DEFAULT', turn=turn)


def _generation(st, d, m, path, parent, turn):
    """One model reply = one GENERATION, however many log lines (or files) repeat it."""
    mid = m.get('id') or d.get('uuid')
    key = (mid, d.get('requestId')) if mid else (path, len(st['obs']))
    ts, usage = _ts(d.get('timestamp')), usage_details(m['usage'])
    g = st['gens'].get(key)
    if g is None:
        g = st['gens'][key] = _obs(f'gen:{len(st["gens"])}:{mid}', 'GENERATION', str(m.get('model') or 'unknown'), ts, parent, turn)
        g.update(model=m.get('model'), usageDetails=usage, file=path, provided=None)
        st['obs'].append(g)
    elif g['file'] != path:
        return  # replayed into a side log: already counted
    else:  # later lines of a streamed reply may carry the final counts
        g['usageDetails'] = normalize_usage({k: max(g['usageDetails'].get(k, 0), usage.get(k, 0)) for k in usage if k != 'total'})
        g['endTime'] = ts or g['endTime']
    c = d.get('costUSD')
    if isinstance(c, (int, float)) and not isinstance(c, bool) and c >= 0:
        g['provided'] = {'total': c}


def _read(st, path, parent=None, turn=0):
    """Collect one transcript. The main log (parent None) opens turns; a subagent log stays inside its caller's."""
    for d in _rows(path):
        m = d.get('message') if isinstance(d.get('message'), dict) else {}
        if parent is None and not d.get('isCompactSummary') and _is_prompt(d):
            turn += 1
            c = m['content']
            text = c if isinstance(c, str) else ' '.join(b.get('text', '') for b in c if b.get('type') == 'text')
            st['prompts'][turn] = (_ts(d.get('timestamp')), ' '.join(text.split())[:50])
        if d.get('type') == 'assistant' and isinstance(m.get('usage'), dict):
            _generation(st, d, m, path, parent, turn)
        for b in m.get('content') if isinstance(m.get('content'), list) else []:
            if not isinstance(b, dict):
                continue
            ts = _ts(d.get('timestamp'))
            if b.get('type') == 'tool_use' and b.get('id') not in st['tools']:
                name, inp = str(b.get('name') or 'tool'), b.get('input') if isinstance(b.get('input'), dict) else {}
                agent = name in AGENT_TOOLS
                if agent:
                    name = f"{name}:{inp.get('subagent_type') or 'general-purpose'}"
                o = st['tools'][b.get('id')] = _obs(str(b.get('id')), 'AGENT' if agent else 'TOOL', name, ts, parent, turn)
                st['obs'].append(o)
            elif b.get('type') == 'tool_result' and b.get('tool_use_id') in st['tools']:
                o = st['tools'][b['tool_use_id']]
                o['endTime'] = ts or o['endTime']
                if b.get('is_error'):
                    o['level'] = 'ERROR'
                if o['type'] == 'AGENT':
                    r = d.get('toolUseResult')
                    aid = r.get('agentId') if isinstance(r, dict) else None
                    hit = None if aid else re.search(r'agentId:\s*([\w-]+)', json.dumps(b.get('content')))
                    if aid or hit:
                        st['links'][aid or hit.group(1)] = o


def _subagents(st, path):
    """Nest each <session>/subagents/agent-<id>.jsonl under its AGENT call; unmatched ones join the turn running at the time."""
    sdir = os.path.join(os.path.splitext(os.path.abspath(path))[0], 'subagents')
    left = {os.path.basename(f)[:-6].replace('agent-', '', 1): f for f in sorted(glob.glob(os.path.join(glob.escape(sdir), '*.jsonl')))}
    while left:
        aid = next((a for a in left if a in st['links']), None)
        f = left.pop(aid or next(iter(left)))
        if aid:
            o = st['links'][aid]
        else:
            ts = next((t for t in (_ts(d.get('timestamp')) for d in _rows(f)) if t), None)
            turn = max([n for n, (t, _) in st['prompts'].items() if t and ts and t <= ts], default=0)
            o = _obs('file:' + os.path.basename(f), 'AGENT', 'Agent:unmatched', ts, None, turn)
            st['obs'].append(o)
        _read(st, f, o['id'], o['turn'])


def traces(path):
    """[trace] for one session log: one per user prompt (turn 0 = before the first), each with priced observations."""
    st = dict(obs=[], gens={}, tools={}, links={}, prompts={})
    _read(st, path)
    _subagents(st, path)
    sid = os.path.splitext(os.path.basename(path))[0]
    groups = {}
    for o in st['obs']:
        o.pop('file', None)
        if o['type'] == 'GENERATION':
            # WHY: all-zero replies (host-made messages) cost nothing and must not raise an unpriced warning
            used = o['usageDetails'].get('total') or o['provided']
            cost, total, source = price_usage(o['model'], o['usageDetails'], o.pop('provided')) if used else ({}, None, None)
            o.update(costDetails=cost, totalCost=total, costSource=source)
        groups.setdefault(o.pop('turn'), []).append(o)
    out = []
    for n in sorted(groups):
        obs = groups[n]
        start, preview = st['prompts'].get(n, (None, '(before first prompt)'))
        times = [t for o in obs for t in (o['startTime'], o['endTime']) if t]
        start = start or min(times, default=None)
        out.append(dict(aggregate(obs), id=f'{sid}:{n}', sessionId=sid, turn=n, name=f'turn {n}', preview=preview, timestamp=start,
                        latency=max(times) - start if times and start else None,
                        sources=sorted({o['costSource'] for o in obs if o.get('costSource')}),
                        unpriced=sorted({str(o['model']) for o in obs if o.get('costSource') == 'list' and not tzprice.known(o['model'])}),
                        observations=obs))
    return out


def _money(cost, sources):
    """Cost with its label: recorded-only figures come from the log, anything priced here is an estimate."""
    if cost is None:
        return 'cost unknown'
    return f"${cost:.4f} {'[actual from log]' if list(sources) == ['recorded'] else '[est]'}"


def _tokens(u):
    """Short in/out token text."""
    k = lambda n: f'{n / 1000:.1f}k' if n >= 1000 else str(int(n))
    return f"{k(u['input'])} in {k(u['output'])} out"


def line(t):
    """One list row for a trace."""
    obs = t['observations']
    gens = sum(o['type'] == 'GENERATION' for o in obs)
    err = sum(o['level'] == 'ERROR' for o in obs)
    lat = f"  {t['latency']:.0f}s" if t['latency'] is not None else ''
    return (f"turn {t['turn']:<3} {_money(t['totalCost'], t['sources'])}  {_tokens(t['usage'])}  {gens} gen {len(obs) - gens} tool"
            + (f' ({err} err)' if err else '') + f'{lat}  "{t["preview"]}"')


def detail(t):
    """The observation tree of one trace; an AGENT line shows the cost of everything under it."""
    out = [line(t)]
    for depth, o, sub in tree(t['observations']):
        s = '  ' * (min(depth, 8) + 1) + f"{o['type']} {o['name']}"
        if sub is not None:
            s += '  ' + _money(sub, t['sources'])
        if o['type'] == 'GENERATION':
            s += '  ' + _tokens(aggregated(o['usageDetails']))
        if o['level'] == 'ERROR':
            s += '  ERROR'
        if o['startTime'] and o['endTime'] and o['endTime'] - o['startTime'] >= 1:
            s += f"  {o['endTime'] - o['startTime']:.0f}s"
        out.append(s)
    return '\n'.join(out)


def main(argv):
    """CLI: tz trace [--last N] [--top] [--turn K] [--json] [--transcript P]."""
    import argparse
    ap = argparse.ArgumentParser(prog='tz trace', description='Per-prompt traces and cost from the local chat log.')
    ap.add_argument('--transcript')
    ap.add_argument('--cwd', default=os.getcwd())
    ap.add_argument('--last', type=int, default=10, help='how many traces to list (default 10)')
    ap.add_argument('--top', action='store_true', help='most expensive traces first')
    ap.add_argument('--turn', type=int, help='show the observation tree of one turn')
    ap.add_argument('--json', action='store_true', help='local export: traces and observations, no prompt or tool content')
    a = ap.parse_args(argv)
    path = a.transcript or find_transcript(os.path.abspath(a.cwd))
    ts = traces(path) if path and os.path.isfile(path) else []
    if not ts:
        print('tz trace: no traced replies found (pass --transcript)', file=sys.stderr)
        return 1
    if a.turn is not None:
        ts = [t for t in ts if t['turn'] == a.turn]
        if not ts:
            print(f'tz trace: no turn {a.turn} in this log', file=sys.stderr)
            return 2
    if a.json:
        print(json.dumps(dict(label=tzprice.LABEL, prices_as_of=tzprice.AS_OF, unit='USD, seconds, tokens',
                              traces=[{k: v for k, v in t.items() if k != 'preview'} for t in ts])))
        return 0
    if a.turn is not None:
        print(detail(ts[0]))
    else:
        total = aggregate([o for t in ts for o in t['observations']])
        sources = sorted({s for t in ts for s in t['sources']})
        n = max(a.last, 1)
        shown = sorted(ts, key=lambda t: -(t['totalCost'] or 0))[:n] if a.top else ts[-n:]
        print(f"traces {os.path.basename(path)}: {len(ts)} turns, session {_money(total['totalCost'], sources)}, "
              f"{_tokens(total['usage'])} (in includes cache) [MEASURED tokens]")
        for t in shown:
            print(line(t))
    bad = sorted({m for t in ts for m in t['unpriced']})
    if bad:
        print(f"unknown model priced as {tzprice.DEFAULT} [est]: {', '.join(bad)}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
