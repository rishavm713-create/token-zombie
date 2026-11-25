# Compounding learnings loop (bin/tzcompound.py): capture/update/recall/check, review merge parity, fail-to-pass nudge.
import json, os, subprocess, sys, tempfile
from harness import ok, done, Z
import tzcompound as C

T = os.path.realpath(tempfile.mkdtemp())


def w(rel, text, base=None):
    p = os.path.join(base or R, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w').write(text)
    return p


def sh(*a):
    subprocess.run(['git', '-C', R, '-c', 'user.name=t', '-c', 'user.email=t@t.test', *a], check=True, capture_output=True)


R = os.path.join(T, 'repo'); os.makedirs(R); sh('init', '-q')
w('src/a.py', 'one\ntwo\n'); sh('add', '.'); sh('commit', '-qm', 'init')
F = {'title': 'Cache key ignores tenant: stale rows', 'symptom': 'tenant sees another tenant rows after cache hit',
     'cause': 'cache key built without tenant id', 'fix': 'add tenant id to the key in `src/a.py:1`', 'detect': 'two tenant test'}

# capture
ok('no root cause: skipped', C.capture(R, dict(F, cause=''))[0] == 'skipped')
ok('typo-size diff: skipped', C.capture(R, F, diff_lines=2)[2].startswith('not durable'))
ok('over 1.5 KB: skipped', C.capture(R, dict(F, fix='x ' * 900))[0] == 'skipped')
st, p, text = C.capture(R, F, diff_lines=9, today='2026-01-02')
ok('dry run writes nothing', st == 'create' and not os.path.exists(os.path.join(R, 'docs')))
ok('path under docs/solutions', p == os.path.join(R, 'docs', 'solutions', 'cache-key-ignores-tenant-stale-rows.md'))
ok('frontmatter is parser safe', C.check_frontmatter(text) == [])
C.capture(R, F, apply=True, today='2026-01-02')
open(p, 'a').write('\n## Notes\nkeep me\n')
st2, p2, t2 = C.capture(R, dict(F, title='Cache key lacks tenant', cause='key omits tenant and locale'), apply=True, today='2026-02-03')
ok('overlap updates the same file', st2 == 'update' and p2 == p and len(C.docs(R)) == 1)
ok('update replaces cause, keeps other text and date', 'tenant and locale' in t2 and 'built without' not in t2
   and 'keep me' in t2 and 'date: 2026-01-02' in t2 and 'last_updated: 2026-02-03' in t2)
ok('update twice: one last_updated', C.capture(R, F, today='2026-03-04')[2].count('last_updated') == 1)
w('docs/solutions/x/foreign.md', '---\ntitle: Queue retries forever\n---\n## Problem\nqueue worker retries forever on bad payload\n')
m = C.capture(R, {'title': 'Queue retries forever', 'symptom': 'queue worker retries forever on bad payload',
                  'cause': 'no cap', 'fix': 'cap'}, apply=True)
ok('differently shaped doc: manual, untouched', m[0] == 'manual' and 'no cap' not in open(m[1]).read())

# recall and docs_root
ok('recall ranks the tenant doc', C.recall(R, 'tenant cache')[0][1].endswith('stale-rows.md'))
ok('recall miss', C.recall(R, 'zebra') == [])
for bad in ('..', '/etc', '.', '.git/x'):
    w('.compound-engineering/config.yaml', f'docs_root: {bad}\n')
    try:
        C.solutions(R); ok(f'docs_root {bad} refused', False)
    except ValueError:
        ok(f'docs_root {bad} refused', True)
w('.compound-engineering/config.yaml', 'docs_root: "know"  # c\n')
ok('docs_root honoured', C.solutions(R) == os.path.join(R, 'know', 'solutions'))
os.remove(os.path.join(R, '.compound-engineering/config.yaml'))

# frontmatter validator parity
ok('no delimiter', C.check_frontmatter('title: x\n') != [])
ok('---- does not close', C.check_frontmatter('---\ntitle: x\n----\n') != [])
ok("unquoted ' #'", len(C.check_frontmatter('---\ntitle: PR #695 fix\n---\n')) == 1)
ok("unquoted ': '", len(C.check_frontmatter('---\ntitle: fix: the thing\n---\n')) == 1)
ok('quoted and nested pass', C.check_frontmatter('---\ntitle: "a: b #c"\ntags: [a]\nx:\n  - y: z\n---\n') == [])

# claim validator
d = w('docs/solutions/c.md', '---\nt: 1\n---\n`src/a.py:2` `src/a.py:9` `src/gone.py` `feat/some-branch` `path/to/x.py`\n'
      'fixed in deadbeef1 [bad](nope.md) [web](https://x.test) {{todo}} `{{ok}}`\n```\n{{fenced}}\n```\n')
fl = '\n'.join(C.check_claims(R, d))
ok('stale line, missing path, sha, link, scaffold', all(s in fl for s in ('src/a.py:9', 'src/gone.py', 'deadbeef1', 'nope.md', '{{todo}}')))
ok('exactly five flags', len(fl.split('\n')) == 5)
os.remove(os.path.join(R, 'src/a.py'))
ok('tracked but deleted', any('tracked at HEAD' in f for f in C.check_claims(R, d)))
sh('checkout', '-q', '--', 'src/a.py')

# review merge parity (upstream tests/ce-code-review-mechanics.test.ts)
base = {'title': 'Primary defect', 'severity': 'P1', 'file': 'src/worker.ts', 'line': 12, 'confidence': 75,
        'autofix_class': 'gated_auto', 'owner': 'downstream-resolver', 'requires_verification': True, 'pre_existing': False,
        'first_evidence': 'src/worker.ts:12 -- result = staleValue'}
ret = lambda r, fs, **k: dict({'reviewer': r, 'findings': fs, 'residual_risks': [], 'testing_gaps': []}, **k)
spec = {k: v for k, v in base.items() if k != 'first_evidence'}
spec.update(title='Speculative cleanup', severity='P3', line=2, confidence=50, autofix_class='advisory', owner='human')
o = C.merge([ret('correctness', [base]), ret('reliability', [dict(base, autofix_class='manual', owner='human'), spec])])
f = o['findings']
ok('dedup, gate, number', len(f) == 1 and f[0]['#'] == 1 and f[0]['confidence'] == 75 and o['suppressed_by_confidence'] == {'50': 1})
ok('cautious class and reviewers', f[0]['autofix_class'] == 'manual' and f[0]['owner'] == 'human'
   and f[0]['independent_reviewers'] == ['correctness', 'reliability'])
for verified, conf, n in ((True, 100, 3), (False, 75, 2)):
    g = C.merge([ret('correctness', [base]), ret('reliability', [base]),
                 ret('adversarial-codex', [base], independence_verified=verified)])['findings'][0]
    ok(f'peer verified={verified}', g['confidence'] == conf and len(g['independent_reviewers']) == n)
for bad in (dict(base, line=True), dict(base, confidence=True), dict(base, first_evidence=''),
            {k: v for k, v in base.items() if k != 'pre_existing'}):
    o = C.merge([ret('a', [bad])])
    ok('malformed or backfilled', o['malformed_findings'] == 1 or o['first_evidence_backfilled'] == 1)
o = C.merge([ret('a', [dict(spec, confidence=75, evidence=['quote'])]), 'junk'])
ok('evidence backfill', o['first_evidence_backfilled'] == 1 and o['findings'][0]['confidence'] == 75 and o['malformed_returns'] == 1)
ok('no evidence: capped to 50', C.merge([ret('a', [dict(spec, confidence=100)])])['findings'] == [])
ok('P0 and settled survive', len(C.merge([ret('a', [dict(spec, severity='P0'), dict(spec, line=3, settled_conflict='K')])])['findings']) == 2)
ok('fast-pass capped', C.merge([ret('fast-pass', [base])])['suppressed_by_confidence'] == {'50': 1})

# CLI through `tz learn`
TZ = os.path.join(Z, 'bin', 'tz')
run = lambda *a, **k: subprocess.run([sys.executable, TZ, 'learn', *a], cwd=R, capture_output=True, text=True, timeout=30, **k)
ok('cli recall', 'stale-rows.md' in run('recall', 'tenant').stdout)
r = run('check', d)
ok('cli check exit 1', r.returncode == 1 and 'need review' in r.stdout)
r = run('capture', '--title', 'x')
ok('cli capture skip signal', r.returncode == 0 and 'Documentation skipped' in r.stdout)
ok('cli review', json.loads(run('review', input=json.dumps([ret('a', [base])])).stdout)['findings'][0]['#'] == 1)
ok('cli bad json', run('review', input='{').returncode == 2)

# fail-to-pass nudge
os.environ['HOME'] = os.path.join(T, 'home')
sh('add', '-A'); sh('commit', '-qm', 'docs')


def ev(cmd, fail, sid='s'):
    return C.observe({'hook_event_name': 'PostToolUseFailure' if fail else 'PostToolUse', 'tool_name': 'Bash',
                      'tool_input': {'command': cmd}, 'cwd': R, 'session_id': sid, 'tool_response': {}})


os.environ.pop('TZ_FEAT_LEARN_LOOP', None)
ev('pytest -q', True); w('src/a.py', 'a\nb\nc\nd\n')
ok('off by default', ev('pytest -q', False) is None)
sh('checkout', '-q', '--', 'src/a.py')
os.environ['TZ_FEAT_LEARN_LOOP'] = '1'
ok('pass without prior fail', ev('pytest -q', False) is None)
w('wip.txt', 'a\nb\nc\nd\n')  # work already present at failure time must not count
ok('fail is silent', ev('pytest -q', True) is None)
ok('flaky rerun, no change', ev('pytest -q', False) is None)
ev('pytest -q', True); w('src/a.py', 'one\nTWO\n'); w('src/n.py', 'n1\nn2\n'); ev('pytest -q', True)
ok('piped pass not trusted', ev('pytest -q | tail', False) is None)
msg = ev('pytest -q', False)
ok('fix then pass nudges once', bool(msg) and '4 changed lines [actual]' in msg and ev('pytest -q', False) is None)
ev('npm test', True); sh('add', '-A'); sh('commit', '-qm', 'wip2'); w('src/a.py', 'x\ny\nz\n'); sh('commit', '-qam', 'fix')
ok('committed fix still counted', bool(ev('npm test', False)))
ev('ls /nope', True); w('src/a.py', '1\n2\n3\n4\n')
ok('non-check command ignored', ev('ls /nope', False) is None and not C.CHECK_CMD.search('grep -r pytest .'))
ok('check commands match', all(C.CHECK_CMD.search(c) for c in (
    'cd x && python3 -m pytest', 'python3 tests/v21/test_a.py', 'bash tests/run_all.sh', 'FOO=1 go test ./...', 'tz gate task')))

# skill refs
for n, word in (('learn', 'tz learn capture'), ('review', 'tz learn review')):
    p = os.path.join(Z, 'skills', 'tz-craft', 'references', n + '.md')
    ok(f'{n} ref names the command, <= 1100 B', word in open(p).read() and os.path.getsize(p) <= 1100)
ok('licence saved', 'Copyright (c) 2025 Every' in open(os.path.join(Z, 'third_party', 'compound-engineering', 'LICENSE')).read())
done()
