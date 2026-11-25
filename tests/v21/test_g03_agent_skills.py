# tz skills check (tzskillcheck) + new tz-craft references. Fixtures are synthetic; nothing from upstream.
import io, json, os, re, subprocess, sys, tempfile, contextlib
from harness import ok, done, Z
import tzskillcheck as S

T = tempfile.mkdtemp()


def put(rel, text):
    p = os.path.join(T, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', newline='') as f:
        f.write(text)


def skill(name, desc='Does X. Use when testing.', body='# t\n', head=None):
    put(f'{name}/SKILL.md', (head if head is not None else f'---\nname: {name}\ndescription: {desc}\n---\n') + body)
    return os.path.join(T, name)


def codes(d):
    return sorted(f['code'] for f in S.check(d)['findings'])


def run(argv):
    o = io.StringIO()
    with contextlib.redirect_stdout(o):
        rc = S.main(argv)
    return rc, o.getvalue()


good = skill('good', body='See [a](references/a.md) and `scripts/run.sh`.\n')
put('good/references/a.md', '# a\n')
put('good/scripts/run.sh', 'true\n')
put('good/README.md', 'for people\n')
ok('clean skill has no findings', codes(good) == [])
r = S.check(good)
ok('three tiers counted', r['listed_tok_est'] > 0 and r['load_tok_est'] > 0 and r['ondemand_tok_est'] == 1)

ok('no frontmatter', 'no-frontmatter' in codes(skill('nofm', head='')))
ok('desc missing', 'desc-missing' in codes(skill('nodesc', head='---\nname: nodesc\n---\n')))
ok('desc long', codes(skill('long', desc='Use when x. ' + 'y' * 300)) == ['desc-long'])
ok('desc over limit', 'desc-over-limit' in codes(skill('huge', desc='Use when x. ' + 'y' * 1100)))
ok('no trigger', codes(skill('notrig', desc='Handles things.')) == ['desc-no-trigger'])
ok('name format', 'name-format' in codes(skill('bad', head='---\nname: Bad_Name\ndescription: Use when x.\n---\n')))
ok('name vs dir', codes(skill('dirx', head='---\nname: other\ndescription: Use when x.\n---\n')) == ['name-dir'])

fold = skill('fold', head='---\nname: fold\ndescription: >-\n  Use when ' + 'a' * 150 + '\n  ' + 'b' * 150 + '\nlicense: x\n---\n')
fm, _ = S.frontmatter(S.read(os.path.join(fold, 'SKILL.md')))
ok('folded description joined', fm['description'].startswith('Use when') and len(fm['description']) > 300)
ok('folded description flagged', codes(fold) == ['desc-long'])
fm, body = S.frontmatter('---\nname: q\ndescription: "Use when q."\nmetadata:\n  version: "1"\n---\nB\n')
ok('quotes stripped, nested key kept apart', fm['description'] == 'Use when q.' and body == 'B\n')
crlf = skill('crlf', head='---\r\nname: crlf\r\ndescription: Use when x.\r\n---\r\n')
ok('CRLF and no false findings', codes(crlf) == [])
hid = skill('hid', head='---\nname: hid\ndescription: Use when x.\ndisable-model-invocation: true\n---\n')
ok('hidden skill lists 0', S.check(hid)['listed_tok_est'] == 0)

ok('body long', 'body-long' in codes(skill('tall', body='x\n' * 501)))
ok('body at limit ok', codes(skill('edge', body='x\n' * 500)) == [])
br = skill('broke', body='[m](references/missing.md) `rules/gone.md` [w](https://x.invalid/a.md) [h](#top)\n'
           '[p](rules/<name>.md)\n```\n[ex](references/example.md)\n```\n')
ok('broken links only the two real ones', codes(br) == ['broken-link', 'broken-link'])

orph = skill('orph', body='nothing here\n')
put('orph/references/lost.md', '# lost\n')
ok('orphan found', codes(orph) == ['orphan'])
for name, body in (('byfolder', 'Open rules/<topic>.md as needed.\n'), ('byglob', 'Open rules/async-*.md\n'),
                   ('byname', 'Open async-a.md\n')):
    d = skill(name, body=body)
    put(f'{name}/rules/async-a.md', '# a\n')
    ok(f'{name} reaches rule', codes(d) == [])
nest = skill('nest', body='[a](references/a.md)\n')
put('nest/references/a.md', 'then [b](b.md)\n')
put('nest/references/b.md', '# b\n')
ok('nested note', codes(nest) == ['nested'])
big = skill('big', body='[a](references/a.md)\n')
put('big/references/a.md', 'z' * 9000)
ok('big ref note', codes(big) == ['ref-big'])
bulk = skill('bulk', body='[a](references/a.md)\n')
put('bulk/references/a.md', '# a\n')
put('bulk/references/c.md', '# c\n')
put('bulk/AGENTS.md', 'references/c.md\n' + 'z' * 9000)
ok('bulk doc flagged, not a route', codes(bulk) == ['bulk-doc', 'orphan'])

outer = skill('outer')
put('outer/inner/SKILL.md', '---\nname: inner\ndescription: Use when x.\n---\n')
put('outer/inner/references/z.md', 'z\n')
ok('nested skill owns its files', codes(outer) == [] and len(S.skill_dirs(outer)) == 2)

rc, out = run(['check', good])
ok('cli ok rc 0 and labelled', rc == 0 and '[est]' in out and '1 skill(s)' in out)
ok('cli error rc 1', run([br])[0] == 1)
ok('cli warn rc 0, strict rc 1', run([orph])[0] == 0 and run([orph, '--strict'])[0] == 1)
rc, out = run([good, '--json'])
ok('cli json', rc == 0 and json.loads(out)[0]['name'] == 'good')
ok('cli usage', run([])[0] == 2 and run([good, '--nope'])[0] == 2)
ok('cli empty dir', run([tempfile.mkdtemp()])[0] == 2)
p = subprocess.run([sys.executable, os.path.join(Z, 'bin', 'tzskillcheck.py'), good], capture_output=True, text=True)
ok('script entry', p.returncode == 0 and 'good:' in p.stdout)

rc, out = run([os.path.join(Z, 'skills'), '--json'])
ok('TZ own skills have no errors', rc == 0)

R = os.path.join(Z, 'skills', 'tz-craft', 'references')
for n in 'react-server component-api web-ui writing react-native view-transitions skill-authoring'.split():
    t = S.read(os.path.join(R, n + '.md'))
    ok(f'ref {n} 400..1100 bytes', 400 <= len(t.encode()) <= 1100 and t.startswith('# '))
done()
