# tztrace: trace/observation model and per-trace cost. Parity cases follow langfuse's pricing, aggregation and tree tests (MIT).
import shutil, contextlib, io, json, os, tempfile
from harness import ok, done, Z
import tzprice, tztrace as T

near = lambda a, b: a is not None and abs(a - b) < 1e-9
pin, pout = tzprice.price('sonnet')

# usage details
ok('total added', T.normalize_usage({'input': 100, 'output': '200'}) == {'input': 100, 'output': 200, 'total': 300})
ok('supplied total kept', T.normalize_usage({'input': 5, 'total': 9})['total'] == 9)
ok('bad buckets dropped', T.normalize_usage({'a': -1, 'b': None, 'c': 'x', 'd': True, 'e': float('nan')}) == {})
u = T.usage_details({'input_tokens': 1, 'cache_creation_input_tokens': 30, 'cache_creation': {'ephemeral_1h_input_tokens': 10}})
ok('ttl split', u['input_cache_creation_5m'] == 20 and u['input_cache_creation_1h'] == 10 and u['total'] == 31)
ok('aggregate-only cache write', T.usage_details({'cache_creation_input_tokens': 7})['input_cache_creation_5m'] == 7)

# cost
cost, total, src = T.price_usage('claude-sonnet-x', {'input': 1000000, 'output': 1000000, 'total': 2000000, 'weird': 5})
ok('list price', near(total, pin + pout) and src == 'list' and near(cost['total'], total) and 'weird' not in cost)
ok('matches tzprice', near(T.price_usage('opus', T.normalize_usage({'input': 11, 'output': 7, 'cache_read_input_tokens': 500,
   'input_cache_creation_5m': 40, 'input_cache_creation_1h': 60}))[1], tzprice.cost_usd('opus', 11, 7, 500, 40, 60)))
ok('null provided -> inferred', T.price_usage('sonnet', {'input': 10}, {'total': None})[2] == 'list')
ok('provided total wins', T.price_usage('sonnet', {'input': 10 ** 6}, {'total': 0.5})[1:] == (0.5, 'recorded'))
ok('provided in+out summed', T.price_usage('sonnet', {}, {'input': 1, 'output': 2})[1] == 3)
ok('provided other bucket: no total', T.price_usage('sonnet', {}, {'cache': 1})[1] is None)
ok('empty usage unknown', T.price_usage('sonnet', {}) == ({}, None, None))
ok('total-only usage unknown', T.price_usage('sonnet', {'total': 50})[1] is None)
ok('known zero kept', T.price_usage('sonnet', {'input': 0})[1] == 0)

# aggregation
ok('keys by word', T.aggregated([{'input': 1, 'cache_read_input_tokens': 2}, {'output': 3}]) == {'input': 3, 'output': 3, 'total': 6})
ok('explicit total', T.aggregated({'input': 1, 'total': 10})['total'] == 10)
a = T.aggregate([dict(type='GENERATION', totalCost=1.0, usageDetails={'input': 4}), dict(type='TOOL', usageDetails={'input': 9})])
ok('usage from generations only', a['totalCost'] == 1.0 and a['usage']['input'] == 4)
ok('no cost -> None', T.aggregate([dict(type='TOOL')])['totalCost'] is None)

# tree
O = lambda i, p=None, c=None, s=0: dict(id=i, parentObservationId=p, totalCost=c, startTime=s)
rows = T.tree([O('c', 'b', 3, 3), O('a', None, 1, 1), O('b', 'a', None, 2)])
ok('nesting + rollup', [(d, o['id'], s) for d, o, s in rows] == [(0, 'a', 4), (1, 'b', 3), (2, 'c', 3)])
ok('orphan is root', T.tree([O('x', 'gone', 1)])[0][0] == 0)
ok('zero cost is none', T.tree([O('z', None, 0)])[0][2] is None)
ok('children by start', [o['id'] for _, o, _ in T.tree([O('p'), O('l', 'p', s=9), O('e', 'p', s=1)])] == ['p', 'e', 'l'])
ok('duplicate id once', len(T.tree([O('d', s=2), O('d', s=1)])) == 1)
ok('cycle kept', len(T.tree([O('m', 'n', 1), O('n', 'm', 1), O('s', 's')])) == 3)
ok('deep iterative', T.tree([O('0', None, None, 0)] + [O(str(i), str(i - 1), 1, i) for i in range(1, 3000)])[0][2] == 2999)

# transcript -> traces
D = tempfile.mkdtemp()
S = os.path.join(D, 'sess.jsonl')
at = lambda s: f'2026-01-01T00:00:{s:02d}Z'
user = lambda s, c, **kw: dict(type='user', timestamp=at(s), message=dict(role='user', content=c), **kw)


def asst(s, mid, usage, content=(), model='claude-sonnet-x', **kw):
    return dict(type='assistant', timestamp=at(s), requestId='r' + mid,
                message=dict(id=mid, model=model, usage=usage, content=list(content)), **kw)


use = lambda i, n, **inp: dict(type='tool_use', id=i, name=n, input=inp)
res = lambda i, **kw: dict(type='tool_result', tool_use_id=i, content='SECRETRESULT', **kw)
U = {'input_tokens': 1000, 'output_tokens': 100}
one = asst(2, 'm1', dict(U, output_tokens=1), [use('t1', 'Bash', command='SECRETCMD')])
main_rows = [user(1, 'first SECRETPROMPT'), one, asst(3, 'm1', U, [use('t2', 'Agent', subagent_type='Explore')]),
             user(4, [res('t1', is_error=True)]), user(9, [res('t2')], toolUseResult={'agentId': 'abc'}),
             user(10, 'compacted', isCompactSummary=True), user(20, [dict(type='text', text='second')]),
             asst(21, 'm2', U, model='mystery-1', costUSD=0.25), asst(22, 'm3', {'input_tokens': 0}, model='<synthetic>')]
write = lambda p, rows: open(p, 'w').write('\n'.join(json.dumps(r) for r in rows) + '\nnot json\n[1]\n')
write(S, main_rows)
os.makedirs(os.path.join(D, 'sess', 'subagents'))
side = os.path.join(D, 'sess', 'subagents', 'agent-abc.jsonl')
write(side, [user(5, 'task', isSidechain=True), one, asst(6, 's1', U, [use('t3', 'Read')], isSidechain=True), user(7, [res('t3')])])
write(os.path.join(D, 'sess', 'subagents', 'agent-zzz.jsonl'), [asst(23, 'z1', U)])
ts = T.traces(S)
ok('one trace per prompt', [t['turn'] for t in ts] == [1, 2])
t1, t2 = ts
by = {o['name']: o for o in t1['observations']}
each = tzprice.cost_usd('sonnet', 1000, 100)
ok('streamed + replayed reply counted once', near(t1['totalCost'], 2 * each) and t1['usage']['input'] == 2000)
ok('final output count', t1['usage']['output'] == 200)
ok('tool error level', by['Bash']['level'] == 'ERROR' and by['Read']['level'] == 'DEFAULT')
ok('subagent nested', by['Read']['parentObservationId'] == 't2' and by['Agent:Explore']['type'] == 'AGENT')
sub = {o['name']: s for _, o, s in T.tree(t1['observations'])}
ok('agent subtree cost', near(sub['Agent:Explore'], each))
ok('latency from prompt', t1['latency'] == 8)
ok('recorded cost used, unmatched agent joins turn', near(t2['totalCost'], 0.25 + each) and t2['sources'] == ['list', 'recorded'])
ok('recorded/zero replies not unpriced', t2['unpriced'] == [] and any(o['name'] == 'Agent:unmatched' for o in t2['observations']))


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = T.main(list(argv) + ['--transcript', S])
    return rc, out.getvalue()


rc, txt = run()
ok('list view', rc == 0 and '2 turns' in txt and '[est]' in txt and '(1 err)' in txt)
rc, txt = run('--top', '--last', '1')
ok('top = dearest', 'turn 2' in txt and 'turn 1' not in txt)
rc, txt = run('--turn', '1')
ok('tree view', rc == 0 and '    GENERATION' in txt and 'AGENT Agent:Explore' in txt and 'SECRETCMD' not in txt)
rc, txt = run('--json')
ok('json export has no content', rc == 0 and 'SECRET' not in txt and json.loads(txt)['traces'][0]['observations'])
ok('missing turn', run('--turn', '99')[0] == 2)
write(S, [user(1, 'q'), asst(2, 'q1', U, model='mystery-1')])
ok('unknown model flagged', 'unknown model priced as' in run()[1])
shutil.rmtree(os.path.join(D, 'sess'))  # WHY: leftover subagent logs would join this trace
write(S, [dict(type='assistant', timestamp=at(1), costUSD=0.5, message=dict(id='k', model='m', usage=U))])
ok('recorded-only label', '[actual from log]' in T.line(T.traces(S)[0]))
write(S, [])
ok('empty log', T.main(['--transcript', S + '.none']) == 1)
src = open(os.path.join(Z, 'bin', 'tztrace.py')).read()
ok('no network or SDK', not any(f'import {m}' in src for m in ('socket', 'urllib', 'http', 'requests', 'langfuse')))
ok('licence saved', 'ClickHouse' in open(os.path.join(Z, 'third_party', 'langfuse', 'LICENSE')).read())
done()
