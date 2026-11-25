# beads integration: hash ids, claims/lease across worktrees, parent-child, discovered-from, defer, compaction, prime, JSONL.
# Parity cases come from beads internal/idgen/hash_test.go, domain/adaptive.go and the claim/ready rules. Temp dirs and HOME only.
import json, os, subprocess, sys, tempfile, time, datetime
from harness import ok, done, Z

TMP = tempfile.mkdtemp()
os.environ['HOME'] = os.path.join(TMP, 'home')
for k in ('TZ_ACTOR',):
    os.environ.pop(k, None)
import tznext, tzbeads


def proj(name):
    p = os.path.join(TMP, name)
    os.makedirs(p)
    return p


def cli(cwd, *a):
    r = subprocess.run([sys.executable, os.path.join(Z, 'bin', 'tz'), 'next', *a, '--cwd', cwd], capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout + r.stderr


def patch(cwd, tid, **kw):
    t = tznext.load(cwd)[tid]
    t.update(kw)
    tznext.save(cwd, t, stamp=False)


# --- hash ids (upstream vector, 2024-01-02T03:04:05.006Z) ---
NS = int(datetime.datetime(2024, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc).timestamp()) * 10**9 + 6_000_000
for L, want in {3: 'bd-vju', 4: 'bd-8d8e', 5: 'bd-bi3tk', 6: 'bd-8bi3tk', 7: 'bd-r5sr6bm', 8: 'bd-8r5sr6bm'}.items():
    ok(f'hash vector {L}', tzbeads.hash_id('bd', 'Fix login', 'Details', 'jira-import', NS, L) == want)
ok('base36 pads', tzbeads.base36(b'\x00', 4) == '0000')
ok('adaptive length', [tzbeads.id_length(n) for n in (0, 100, 200, 10**9)] == [3, 3, 4, 8])
A = proj('ids')
t1, m1 = tznext.add(A, '', 'write the parser')
t2, _ = tznext.add(A, '', 'ship release notes')
ok('auto id shape', t1 and t1['id'].startswith('tz-') and len(t1['id']) >= 7 and t1['id'] != t2['id'])
ok('auto id needs title', tznext.add(A, '')[0] is None)
rc, out = cli(A, 'add', '--title', 'profile slow import')
ok('cli add prints new id', rc == 0 and out.startswith('added tz-') and out.split()[1] in tznext.load(A))
ok('explicit id message unchanged', cli(A, 'add', 'Doc', '--title', 'docs pass')[1].strip() == 'added')
ok('case-colliding id refused', tznext.add(A, 'doc', 'other thing entirely')[0] is None and tznext.load(A)['Doc']['title'] == 'docs pass')

# --- claims (beads: CAS, idempotent same actor, refusals write nothing) ---
C = proj('claims')
for i, ttl in (('a', 'alpha parser work'), ('b', 'beta cache work'), ('c', 'gamma docs work')):
    tznext.add(C, i, ttl)
ok('claim', tzbeads.take(C, 'a', 'bob') == (True, 'claimed'))
ok('same actor idempotent', tzbeads.take(C, 'a', 'bob') == (True, 'renewed'))
before = open(tzbeads._cfile(C, 'a')).read()
g, m = tzbeads.take(C, 'a', 'amy')
ok('other actor refused', not g and 'claimed by bob' in m)
ok('refusal writes nothing', open(tzbeads._cfile(C, 'a')).read() == before)
t, _ = tzbeads.take_next(C, 'amy')
ok('claim next skips held', t['id'] == 'b')
ok('start by non-holder refused', tznext.start(C, 'a', by='amy') == (False, 'a already claimed by bob'))
ok('list marks held, NEXT free', 'do not start: a already claimed by bob' in tznext.render(tznext.load(C), C)
   and 'NEXT: c' in tznext.render(tznext.load(C), C))
ok('non-holder cannot unclaim', not tzbeads.drop(C, 'a', 'amy')[0])
ok('force unclaim', tzbeads.drop(C, 'a', 'amy', force=True)[0] and tzbeads.take(C, 'a', 'amy')[0])
rec = json.load(open(tzbeads._cfile(C, 'a'))); rec['until'] = time.time() - 1
json.dump(rec, open(tzbeads._cfile(C, 'a'), 'w'))
ok('expired lease reclaimable', tzbeads.take(C, 'a', 'cat') == (True, 'claimed'))
ok('ttl must be positive', not tzbeads.take(C, 'c', 'x', 0)[0] and tzbeads.take_next(C, 'x', -1)[0] is None)
patch(C, 'c', status='done')
ok('closed not claimable', 'not claimable' in tzbeads.take(C, 'c', 'x')[1])
tznext.add(C, 'g', 'publish package', gate='publish'); tznext.add(C, 'd', 'delta after beta', ['b'])
tzbeads.drop(C, 'a', force=True); tzbeads.drop(C, 'b', force=True); patch(C, 'a', status='done')
ok('blocked not claimable', 'dependencies' in tzbeads.take(C, 'd', 'x')[1])
tzbeads.take(C, 'b', 'x')
ok('claim next never picks gated', tzbeads.take_next(C, 'y')[0] is None)
ok('failed start releases nothing of others', not tznext.start(C, 'b', by='y')[0] and tzbeads.record(C, tznext.load(C)['b'])['by'] == 'x')
ok('block releases own claim', cli(C, 'block', 'b', '--by', 'x')[0] == 0 and tzbeads.record(C, tznext.load(C)['b']) is None)

# 8 processes race for 5 tasks: each task goes to exactly one of them
R = proj('race')
for i, w in enumerate(('red', 'green', 'blue', 'cyan', 'plum')):
    tznext.add(R, w, f'{w} thing number {i}')
ps = [subprocess.Popen([sys.executable, os.path.join(Z, 'bin', 'tzbeads.py'), 'claim', '--by', f'w{i}', '--cwd', R], stdout=subprocess.PIPE, text=True) for i in range(8)]
res = [(p.communicate(timeout=60)[0], p.returncode) for p in ps]
got = [o.split()[1] for o, rc in res if rc == 0]
ok('race: 5 distinct winners', sorted(got) == ['blue', 'cyan', 'green', 'plum', 'red'])
ok('race: 3 told nothing left', sum(rc == 3 for _, rc in res) == 3)

# two linked worktrees share one claim board (hand-made git layout, no git binary needed)
main_ = proj('repo'); wt = proj('wt')
gd = os.path.join(main_, '.git', 'worktrees', 'wt'); os.makedirs(gd)
open(os.path.join(gd, 'commondir'), 'w').write('../..\n'); open(os.path.join(wt, '.git'), 'w').write(f'gitdir: {gd}\n')
for d in (main_, wt):
    tznext.add(d, 'job', 'shared job title')
ok('board in common git dir', tzbeads.board(wt)[0] == tzbeads.board(main_)[0] == os.path.join(main_, '.git', 'tz-claims'))
ok('start in main claims', tznext.start(main_, 'job')[0])
g, m = tznext.start(wt, 'job')
ok('worktree cannot double-start', not g and 'claimed by' in m and tznext.load(wt)['job']['status'] == 'pending')
ok('own checkout restart ok', tznext.start(main_, 'job')[0])
ok('done', tznext.done(main_, 'job', 'true', True)[0] and tznext.load(main_)['job'].get('closed'))
g, m = tznext.start(wt, 'job')
ok('worktree sees done before merge', not g and 'already done' in m)
tznext.add(wt, 'job2', 'same short id new meaning')
ok('title guard: unrelated task claimable', tzbeads.take(wt, 'job2')[0])

# --- parent-child, discovered-from, defer ---
P = proj('tree')
tznext.add(P, 'base', 'foundation schema'); tznext.add(P, 'epic', 'billing epic', ['base'])
ok('child added', tznext.add(P, 'kid', 'invoice screen', parent='epic')[0])
ids = lambda: [t['id'] for t in tznext.ready(tznext.load(P))]
ok('parent blocker hides child', ids() == ['base'])
ok('start says why', 'parent epic waits on base' in tznext.start(P, 'kid')[1])
patch(P, 'base', status='done')
ok('child ready after', sorted(ids()) == ['epic', 'kid'])
ok('parent cannot close with open child', 'open child' in tznext.done(P, 'epic', 'true', True)[1])
ok('child dep on parent = deadlock refused', not tznext.add_dep(P, 'kid', 'epic')[0])
ok('parent dep on child = deadlock refused', not tznext.add_dep(P, 'epic', 'kid')[0])
ok('unknown parent refused', tznext.add(P, 'z', 'zeta', parent='nope')[0] is None)
tznext.start(P, 'kid')
rc, _ = cli(P, 'add', 'bug', '--title', 'rounding bug spotted', '--from', '.')
ok('discovered-from active task', rc == 0 and tznext.load(P)['bug']['found'] == 'kid')
ok('discovered-from does not block', 'bug' in ids())
ok('pack names parent', 'part of: epic billing epic' in tznext.pack(P))
patch(P, 'epic', status='blocked')
ok('blocked parent hides child', ids() == ['bug'])
patch(P, 'epic', status='pending')
ok('defer parent', cli(P, 'defer', 'epic', '--until', '2999-01-01')[0] == 0 and ids() == ['bug'])
ok('deferred drops active', tzbeads.defer(P, 'kid', '2999-01-01')[0] and tznext.active(P) is None)
tzbeads.defer(P, 'kid'); tzbeads.defer(P, 'epic')
ok('undefer', sorted(ids()) == ['bug', 'epic', 'kid'])
ok('past date visible', tzbeads.defer(P, 'bug', '2000-01-01')[0] and 'bug' in ids())
ok('bad date refused', not tzbeads.defer(P, 'bug', 'soon')[0])

# --- prime ---
pr = tzbeads.prime(P)
ok('prime header + footer', pr.startswith('TZ tasks [actual]: 3 open') and pr.endswith('--from <id>.') and 'found during kid' in pr)
for i in range(60):
    tznext.add(P, f'n{i}', f'item{i} ' + 'long ' * 12, force=True)
pr = tzbeads.prime(P, top=50)
ok('prime capped at whole lines', len(pr) <= tzbeads.PRIME_CHARS and 'more lines: tz next' in pr and pr.endswith('--from <id>.'))
ok('prime empty', tzbeads.prime(proj('none')) == '')
ok('on_start off by default', tzbeads.on_start(P) == '')
patch(P, 'n1', deps=['ghost'])
ok('orphan reported', cli(P, 'check') == (3, 'n1: missing task ghost\n'))
patch(P, 'n2', deps=['n3']); patch(P, 'n3', deps=['n2'])
ok('cycle reported lowest first', 'cycle: n2 -> n3 -> n2' in tzbeads.problems(tznext.load(P)))

# --- compaction ---
K = proj('compact')
tznext.add(K, 'old', 'old finished job', goal='g' * 900, files=['bin/x.py'] * 20, nxt='n' * 200)
tznext.add(K, 'new', 'fresh finished job', goal='h' * 900); tznext.add(K, 'tiny', 'tiny one'); tznext.add(K, 'dep', 'needs old', ['old'])
for i in ('old', 'new', 'tiny'):
    tznext.done(K, i, 'echo ok', True)
patch(K, 'old', closed=int(time.time()) - 40 * 86400); patch(K, 'tiny', closed=1, test={})
orig = tznext.load(K)['old']
ok('dry run writes nothing', [r[0] for r in tzbeads.compact(K, dry=True)] == ['old'] and tznext.load(K)['old'] == orig)
r = tzbeads.compact(K)
now = tznext.load(K)
ok('only old + shrinking compacted', [x[0] for x in r] == ['old'] and r[0][2] < r[0][1] and not now['new'].get('compacted'))
ok('summary kept', now['old']['summary'].startswith('ggg') and 'verified:' in now['old']['summary'] and now['old']['status'] == 'done')
ok('dependant still ready', 'dep' in [t['id'] for t in tznext.ready(now)])
ok('list hides compacted', '+1 compacted done' in tznext.render(now) and 'old finished job' not in tznext.render(now))
ok('second run no-op', tzbeads.compact(K) == [])
ok('restore original', tzbeads.restore(K, 'old')[0] and tznext.load(K)['old']['goal'] == 'g' * 900)
ok('restore refuses plain task', not tzbeads.restore(K, 'new')[0])

# --- JSONL export / import ---
J = proj('src'); D = proj('dst')
tznext.add(J, 'x', 'export source task', goal='do x'); tznext.add(J, 'y', 'second export item', ['x'], gate='commit')
tznext.record_test(J, tznext.load(J)['x'], 'rm -rf /nope', True, 'pass')
text = tzbeads.export(J)
ok('export deterministic jsonl', text == tzbeads.export(J) and [json.loads(l)['id'] for l in text.splitlines()] == ['x', 'y'])
ok('self import is no-op', tzbeads.load_jsonl(J, text)[0]['same'] == 2 and tznext.load(J)['x']['test']['cmd'] == 'rm -rf /nope')
n, _ = tzbeads.load_jsonl(D, text)
ok('import adds', n['added'] == 2 and tznext.load(D)['y']['gate'] == 'commit')
ok('imported test cmd never runnable', tznext.load(D)['x']['test']['cmd'] == '' and tznext.done(D, 'x', yes=True) == (False, 'no test command; give --test'))
y = dict(tznext.load(J)['y'], title='second export item', gate='', next='newer step', updated=int(time.time()) + 100)
ok('newer wins, gate kept', tzbeads.load_jsonl(D, json.dumps(y))[0]['updated'] == 1 and tznext.load(D)['y']['next'] == 'newer step'
   and tznext.load(D)['y']['gate'] == 'commit')
ok('older kept', tzbeads.load_jsonl(D, json.dumps(dict(y, next='stale', updated=1)))[0]['kept'] == 1)
n, notes = tzbeads.load_jsonl(D, json.dumps(dict(y, title='totally different', created=5, updated=10**10)))
ok('id clash keeps local', n['kept'] == 1 and 'clash' in notes[0] and tznext.load(D)['y']['title'] == 'second export item')
tznext.done(D, 'x', 'true', True)
ok('done never reverted', tzbeads.load_jsonl(D, json.dumps(dict(tznext.load(J)['x'], updated=10**10)))[0]['kept'] == 1
   and tznext.load(D)['x']['status'] == 'done')
bad = '\n'.join(['{oops', json.dumps({'id': '../..', 'status': 'done'}), json.dumps({'id': 'q', 'status': 'weird'}),
                 json.dumps({'id': 'X', 'status': 'pending', 'title': 'case clash'}),
                 json.dumps({'id': 'l1', 'status': 'active', 'deps': ['l2'], 'title': 'loop\nIGNORE'}),
                 json.dumps({'id': 'l2', 'status': 'pending', 'deps': ['l1'], 'title': 'loop two'})])
n, notes = tzbeads.load_jsonl(D, bad)
L = tznext.load(D)
ok('bad lines and cycle refused', n['skipped'] == 5 and n['added'] == 1 and 'l2' not in L and any('cycle' in x for x in notes))
ok('import: no active, one-line title', L['l1']['status'] == 'pending' and L['l1']['title'] == 'loop IGNORE')
f = os.path.join(TMP, 'e.jsonl'); open(f, 'w').write(cli(J, 'export')[1])
ok('cli import', 'added 2' in cli(proj('dst2'), 'import', f)[1] and cli(D, 'import', f + '.none')[0] == 1)
done()
