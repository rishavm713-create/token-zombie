# g01 ccusage: offline daily/weekly/monthly/session/block reports and dedup (parity with ccusage MIT tests/docs).
# Synthetic transcripts in a temp HOME only; the real ~/.claude is never read.
import contextlib, datetime as dt, io, json, os, shutil, sys, tempfile
H = tempfile.mkdtemp()
os.environ['HOME'] = os.environ['USERPROFILE'] = H  # before tzprice import: it reads the price override from HOME
for k in ('CLAUDE_CONFIG_DIR', 'XDG_CONFIG_HOME'):
    os.environ.pop(k, None)
from harness import ok, done, Z
import tzccu as C
import tzusage as U
import tzprice


def line(ts, mid='m1', rid='r1', i=10, o=5, cr=0, cw=0, model='claude-sonnet-4-5', side=None, uuid=None, parent=None,
         usage=None, content=None):
    u = dict(input_tokens=i, output_tokens=o, cache_read_input_tokens=cr, cache_creation_input_tokens=cw)
    u.update(usage or {})
    d = dict(type='assistant', timestamp=ts, message=dict(model=model, usage=u))
    for key, v in (('requestId', rid), ('isSidechain', side), ('uuid', uuid), ('parentUuid', parent)):
        if v is not None:
            d[key] = v
    if mid:
        d['message']['id'] = mid
    if content:
        d['message']['content'] = content
    return d


def put(rel, rows, base='.claude'):
    p = os.path.join(H, base, 'projects', *rel.split('/'))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w') as f:
        f.write(''.join((r if isinstance(r, str) else json.dumps(r)) + '\n' for r in rows))
    return p


def reset():
    shutil.rmtree(os.path.join(H, '.claude'), ignore_errors=True)
    shutil.rmtree(os.path.join(H, '.config'), ignore_errors=True)


def run(*a):
    o, e = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
        try:
            rc = C.main(list(a))
        except SystemExit as x:
            rc = x.code
    return rc, o.getvalue(), e.getvalue()


T = '2026-03-02T10:00:00.000Z'  # a Monday
T2 = '2026-03-02T10:00:01.000Z'

ok('no log folder => rc 1, says UNAVAILABLE', run()[0] == 1 and 'UNAVAILABLE' in run()[2])

# dedup
reset()
put('p/s1.jsonl', [line(T, o=5), line(T2, o=40)])
e = C.load()
ok('streamed lines: one reply, largest output kept', len(e) == 1 and e[0]['out'] == 40)
put('p/s2.jsonl', [line(T, o=40)])
ok('same message+request copied to a resumed session counts once', len(C.load()) == 1)
reset()
put('p/s1.jsonl', [line(T, rid='r1'), line(T2, rid='r2')])
ok('same message id, two request ids => two replies', len(C.load()) == 2)
reset()
put('p/s1.jsonl', [line(T, rid='r1', o=50)])
put('p/s1/subagents/agent-a.jsonl', [line(T2, rid='r9', o=900, side=True)])
e = C.load()
ok('sidechain replay merged, parent kept over bigger replay', len(e) == 1 and not e[0]['side'] and e[0]['out'] == 50)
reset()
put('p/s1.jsonl', [line(T, rid='r1'), line(T2, rid='r2'), line(T2, rid='r3', side=True)])
ok('a replay never joins two real parent requests', len(C.load()) == 2)
reset()
put('p/s1.jsonl', [line(T, rid=None), line(T2, rid=None)])
ok('no request id, different times, unlinked => kept apart', len(C.load()) == 2)
reset()
tool = [dict(type='tool_use', id='t1')]
result = dict(type='user', uuid='u2', parentUuid='u1', message=dict(content=[dict(type='tool_result', tool_use_id='t1')]))
put('p/s1.jsonl', [line(T, rid=None, uuid='u1', content=tool), result, line(T2, rid=None, uuid='u3', parent='u2')])
ok('no request id: chain through own tool result => one reply', len(C.load()) == 1)
result['message']['content'][0]['tool_use_id'] = 'other'
put('p/s1.jsonl', [line(T, rid=None, uuid='u1', content=tool), result, line(T2, rid=None, uuid='u3', parent='u2')])
ok('no request id: foreign tool result ends the chain', len(C.load()) == 2)
reset()
put('p/s1.jsonl', [line(T, usage=dict(speed='standard')), line(T, usage=dict(speed='fast'))])
ok('equal copies: the one reporting more detail wins', C.load()[0]['detail'][0] == 2)

# parsing
reset()
iterated = dict(cache_creation=dict(ephemeral_5m_input_tokens=0, ephemeral_1h_input_tokens=11142), iterations=[
    dict(type='message', cache_creation=dict(ephemeral_5m_input_tokens=0, ephemeral_1h_input_tokens=11142)),
    dict(type='advisor_message', model='claude-fable-5-2', input_tokens=77025, output_tokens=3),
    dict(type='message', cache_creation=dict(ephemeral_5m_input_tokens=1181, ephemeral_1h_input_tokens=0))])
put('p/s1.jsonl', [line(T, i=4, o=244, cw=12323, usage=iterated)])
e = sorted(C.load(), key=lambda x: x['inp'])
ok('upstream: message iteration splits sum to 12323', e[0]['cw'] == 12323 and e[0]['w5'] == 1181 and e[0]['w1h'] == 11142)
ok('advisor iteration is its own entry with its own model', len(e) == 2 and e[1]['inp'] == 77025 and e[1]['model'] == 'claude-fable-5-2')
reset()
prog = dict(type='progress', sessionId='s1', data=dict(message=line(T, mid='a1', rid='ra', i=7, o=3)))
put('p/s1.jsonl', ['{"usage" broken', '["usage"]', json.dumps(prog),
                   line(T, mid='z', model='<synthetic>', i=0, o=0), line('nonsense', mid='bad'),
                   line(T, mid='x', rid='rx', i=-5, o=True, usage=dict(iterations=3))])
e = C.load()
ok('progress envelope read; broken, synthetic, undated, junk-number lines skipped', len(e) == 1 and e[0]['inp'] == 7)

# discovery
reset()
put('p/s1.jsonl', [line(T, mid='a')])
put('p/s2.jsonl', [line(T, mid='b', rid='rb')], base='.config/claude')
ok('XDG config dir and ~/.claude both read', len(C.load()) == 2)
os.environ['CLAUDE_CONFIG_DIR'] = os.path.join(H, '.config', 'claude', 'projects') + ',' + os.path.join(H, '.config', 'claude')
ok('CLAUDE_CONFIG_DIR wins; projects/ form accepted and not doubled', [x['mid'] for x in C.load()] == ['b'] and len(C.roots()) == 1)
os.environ.pop('CLAUDE_CONFIG_DIR')
sp = lambda r: C.session_parts('/x', os.path.join('/x', *r.split('/')))
ok('session path: plain file', sp('proj/abc.jsonl') == ('abc', 'proj', 'proj'))
ok('session path: subagent file belongs to parent session', sp('proj/abc/subagents/agent-1.jsonl') == ('abc', 'proj', 'proj'))
ok('session path: nested session folder', sp('proj/abc/chat.jsonl') == ('abc', 'proj', 'proj'))

# periods
d = dt.date(2026, 3, 4)  # Wednesday
ok('week starts Sunday by default (ccusage claude weekly)', C.period('weekly', d) == '2026-03-01')
ok('week can start Monday', C.period('weekly', d, 0) == '2026-03-02')
ok('month bucket', C.period('monthly', d) == '2026-03')
ok('--last windows', C.last_since('daily', 7, d) == dt.date(2026, 2, 26) and C.last_since('weekly', 2, d) == dt.date(2026, 2, 22)
   and C.last_since('monthly', 4, d) == dt.date(2025, 12, 1))

# reports
reset()
put('alpha/s1.jsonl', [line(T, mid='a', rid='1', i=1000000, o=0, model='claude-opus-4-6'),
                       line(T, mid='b', rid='2', i=0, o=1000000, model='claude-haiku-4-5')])
put('beta/s2.jsonl', [line('2026-04-10T23:30:00Z', mid='c', rid='3', i=100, o=50, cr=1000, cw=200, model='mystery-9000')])
rc, o, _ = run('daily', '--json', '--timezone', 'UTC')
if rc == 2:  # no time zone database on this system
    os.environ['TZ'] = 'UTC'
j = json.loads(run('daily', '--json')[1]) if rc else json.loads(o)
r = j['daily'][0]
ok('daily json shape and labels', [x['date'] for x in j['daily']] == ['2026-03-02', '2026-04-10'] and j['labels']['tokens'] == 'actual' and j['labels']['cost'] == 'est')
ok('per-model split, cost from TZ table', [(m['modelName'], m['cost']) for m in r['modelBreakdowns']]
   == [(m, round(tzprice.cost_usd(m, a, b), 6)) for m, a, b in (('claude-opus-4-6', 1000000, 0), ('claude-haiku-4-5', 0, 1000000))]
   or sorted(m['cost'] for m in r['modelBreakdowns']) == sorted([tzprice.PRICES['opus'][0], tzprice.PRICES['haiku'][1]]))
ok('totals add up', j['totals']['totalTokens'] == 2001350 and j['totals']['cacheReadTokens'] == 1000)
ok('unknown model listed and marked priced-as', j['totals']['unpricedModels'] == ['mystery-9000'] and j['daily'][1]['modelBreakdowns'][0]['pricedAs'] == 'sonnet')
j = json.loads(run('monthly', '--json', '--order', 'desc')[1])
ok('monthly, descending', [x['month'] for x in j['monthly']] == ['2026-04', '2026-03'])
j = json.loads(run('weekly', '--json', '-w', 'monday')[1])
ok('weekly rows keyed by week start', j['weekly'][0]['week'] == '2026-03-02')
j = json.loads(run('session', '--json')[1])
ok('session rows', [(x['sessionId'], x['projectPath']) for x in j['session']] == [('s1', 'alpha'), ('s2', 'beta')])
j = json.loads(run('session', '--json', '--id', 's2', '--project', 'alpha')[1])
ok('--id searches every project', [x['sessionId'] for x in j['session']] == ['s2'])
j = json.loads(run('daily', '--json', '--project', 'beta')[1])
ok('--project filter', j['totals']['totalTokens'] == 1350)
j = json.loads(run('daily', '--json', '--instances')[1])
ok('--instances splits by project', [x['project'] for x in j['daily']] == ['alpha', 'beta'])
j = json.loads(run('daily', '--json', '--since', '20260401', '--until', '2026-04-30')[1])
ok('--since/--until', len(j['daily']) == 1 and j['totals']['inputTokens'] == 100)
rc, o, _ = run('daily', '--breakdown')
ok('text: labels, breakdown, TOTAL, priced-as note', rc == 0 and '[actual]' in o and '[est]' in o and '  claude-opus' in o and 'TOTAL' in o and 'priced as sonnet' in o)
ok('empty selection is said plainly', 'no usage found' in run('daily', '--project', 'nope')[1])
ok('--last with --since is an error', run('daily', '--last', '1', '--since', '20260101')[0] == 2)
ok('bad date / bad --last / bad zone are errors', [run('daily', *a)[0] for a in (('--since', 'x'), ('--last', '0'), ('--timezone', 'No/Where'))] == [2, 2, 2])

# blocks
es = C.load()
b = C.block_report(es, now=U._ts('2026-04-11T00:00:00Z'))['blocks']
ok('blocks: data, gap, active', [x['isGap'] for x in b] == [False, True, False] and b[-1]['isActive'] and b[0]['entries'] == 2 and b[2]['totalTokens'] == 1350)
ok('blocks --active only', len(C.block_report(es, now=U._ts('2026-04-11T00:00:00Z'), active=True)['blocks']) == 1)
rc, o, _ = run('blocks')
ok('blocks text renders gap', rc == 0 and '(gap)' in o)

# tzusage.totals (single chat) follows the same fullest-copy rule
reset()
p = put('p/s1.jsonl', [line(T, o=5, i=10, cr=100), line(T2, o=40, i=10, cr=100),
                       line(T2, mid='s', model='<synthetic>', i=0, o=0)])
t = U.totals(p)
ok('totals: streamed reply counted once with final output', (t['turns'], t['inp'], t['out'], t['cr']) == (1, 10, 40, 100))
ok('totals: synthetic notice does not zero context', t['last'] == 110)
sf = os.path.join(H, 'inc.state')
p = put('p/inc.jsonl', [line(T, o=5)])
U.totals_inc(p, sf)
with open(p, 'a') as f:
    f.write(json.dumps(line(T2, o=40)) + '\n')
t = U.totals_inc(p, sf)
ok('incremental: reply split across scans not double counted', (t['turns'], t['inp'], t['out']) == (1, 10, 40))
src = open(os.path.join(Z, 'bin', 'tzccu.py')).read()
ok('offline: no network or process imports', not any(x in src for x in ('urllib', 'socket', 'http.client', 'subprocess', 'requests')))
shutil.rmtree(H, ignore_errors=True)
done()
