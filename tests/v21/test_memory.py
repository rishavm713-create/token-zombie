# tzfit (fit/audit/plan_inject), tznext (cycles/claim/hybrid), tzmem (chunk/index/search).
import os, sys, json, tempfile, time
from harness import ok, done, Z
import tzfit, tznext, tzmem
from tzlib import feature

# fit
s = '\n'.join(f'line {i} ' + 'x' * 40 for i in range(1000))
r = tzfit.fit(s, 2000)
ok('fit cap', len(r) <= 2000 and '... (+' in r and 'chars cut, tz recall)' in r)
ok('fit keeps head and tail', r.startswith('line 0 ') and r.rstrip().endswith('x' * 40) and 'line 999' in r)
ok('fit short untouched', tzfit.fit('abc', 10) == 'abc')
ok('fit tiny cap', len(tzfit.fit('y' * 500, 60)) <= 60)
ok('audit report-only list', isinstance(tzfit.audit(), list) and all(len(x) == 3 for x in tzfit.audit()))

# plan_inject
H = tempfile.mkdtemp(); P = tempfile.mkdtemp()
os.environ['HOME'] = H
os.environ['TZ_FEAT_PLAN_REINJECT'] = '0'
open(os.path.join(P, 'task_plan.md'), 'w').write('\n'.join(f'step {i}' for i in range(200)))
d = dict(cwd=P, session_id='s1', source='compact')
ok('plan gate off', tzfit.plan_inject(d) == '')
os.environ['TZ_FEAT_PLAN_REINJECT'] = '1'
ok('plan startup pointer', 'task_plan.md' in tzfit.plan_inject(dict(d, source='startup')) and 'step 5' not in tzfit.plan_inject(dict(d, source='startup')))
t = tzfit.plan_inject(d)
ok('plan compact full', 'step 0' in t and 'step 49' in t and 'step 199' in t and 'step 100\n' not in t and len(t) <= tzfit.PLAN_CAP)
ok('plan hash gate', tzfit.plan_inject(d) == '')
open(os.path.join(P, 'task_plan.md'), 'a').write('\nnew progress')
ok('plan changed reinjects', 'new progress' in tzfit.plan_inject(dict(d, hook_event_name='PreCompact', source='')))
os.makedirs(os.path.join(P, 'handoffs')); os.remove(os.path.join(P, 'task_plan.md'))
open(os.path.join(P, 'handoffs', 'STATE.md'), 'w').write('state')
ok('plan resume no dup of newest handoff', tzfit.plan_inject(dict(d, source='resume', session_id='s2')) == '')
ok('plan compact STATE.md', 'state' in tzfit.plan_inject(dict(d, session_id='s3')))

# tznext
T = tempfile.mkdtemp()
tznext.add(T, 'a', 'alpha task one'); tznext.add(T, 'b', 'beta task two', ['a']); tznext.add(T, 'c', 'gamma job three', ['b'])
ok('cycle none', tznext.find_cycle(tznext.load(T)) is None)
g, m = tznext.add_dep(T, 'a', 'c')
ok('cycle refused', not g and 'cycle' in m and tznext.load(T)['a']['deps'] == [])
ok('self cycle refused', not tznext.add_dep(T, 'a', 'a')[0])
ok('dep ok', tznext.add_dep(T, 'c', 'a')[0])
ts = tznext.load(T); ts['x'] = dict(id='x', deps=['y']); ts['y'] = dict(id='y', deps=['x'])
ok('find_cycle detects', tznext.find_cycle(ts) is not None)
ok('claim', tznext.start(T, 'a')[0])
ok('claim exclusive', tznext.claim(T, 'zzz') == (False, 'a'))
tznext.release(T, 'a'); ts = tznext.load(T); ts['a']['status'] = 'done'; tznext.save(T, ts['a'])
ok('stale lock replaced', tznext.claim(T, 'b')[0])
# hybrid: old low-priority task before recent high-priority one; recent ordered by prio
H2 = tempfile.mkdtemp()
tznext.add(H2, 'new1', 'recent low', prio=3); tznext.add(H2, 'new2', 'recent urgent', prio=0)
tznext.add(H2, 'old1', 'ancient work', prio=4)
o = tznext.load(H2)['old1']; o['created'] = int(time.time()) - 72 * 3600; tznext.save(H2, o)
ok('hybrid order', [t['id'] for t in tznext.ready(tznext.load(H2))] == ['old1', 'new2', 'new1'])

# tzmem
M = tempfile.mkdtemp(); db = os.path.join(M, 'mem.db')
os.makedirs(os.path.join(M, 'handoffs')); os.makedirs(os.path.join(M, 'docs'))
open(os.path.join(M, 'HANDOFF.md'), 'w').write('# top\nthe zebra crossing migration plan\n')
open(os.path.join(M, 'handoffs', '2026-01-01.md'), 'w').write('\n'.join(f'filler line {i} about nothing' for i in range(200)) + '\nquokka cache invalidation bug fixed\n')
open(os.path.join(M, 'docs', 'a.md'), 'w').write('some docs about lemurs\n')
ch = tzmem.chunks('\n'.join('l%d %s' % (i, 'w' * 60) for i in range(100)))
ok('chunk size', all(len(t) <= 1600 for _, t in ch) and len(ch) > 3)
ok('chunk overlap 2 lines', ch[0][1].splitlines()[-2:] == ch[1][1].splitlines()[:2])
ok('chunk id stable 16 hex', tzmem.cid('p', 1, 'x') == tzmem.cid('p', 1, 'x') and len(tzmem.cid('p', 1, 'x')) == 16)
f, n, gone = tzmem.index(M, db)
ok('index', f == 3 and n > 0)
ok('reindex no new', tzmem.index(M, db)[1] == 0)
r = tzmem.search('quokka invalidation', 3, db)
ok('search path:line', r and r[0][1].startswith('handoffs/2026-01-01.md:') and 'quokka' in r[0][2])
ok('search other', tzmem.search('zebra', 3, db)[0][1].startswith('HANDOFF.md:1'))
ok('search none', tzmem.search('nonexistentterm', 3, db) == [])
# BM25 fallback path
tzmem.USE_FTS = False
r2 = tzmem.search('quokka invalidation', 3, db)
tzmem.USE_FTS = True
ok('bm25 fallback', r2 and r2[0][1].startswith('handoffs/2026-01-01.md:'))
done()
