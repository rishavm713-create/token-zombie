# tz spec (adapted from Fission-AI/OpenSpec): parser parity, validation, merge, archive, CLI.
import contextlib, io, os, tempfile
from harness import ok, done, Z
import tzspec as S


def fails(fn, part=''):
    try:
        fn()
    except S.SpecError as e:
        return part in str(e)
    return False


def req(name, scen='ok', body='The system SHALL work.'):
    return f'### Requirement: {name}\n{body}\n\n#### Scenario: {scen}\n- **WHEN** x\n- **THEN** y\n'


def cli(*a):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = S.main(list(a))
    return code, out.getvalue()


# --- parser parity (upstream parsers/*.test.ts) ---
d = S.parse_delta('﻿## ADDED Requirements\r\n' + req('A').replace('\n', '\r\n'))
ok('BOM and CRLF parse', [n for n, _ in d['added']] == ['A'])
d = S.parse_delta('## added requirements\n###requirement: low\nSHALL\n')
ok('mixed case, no space header', [n for n, _ in d['added']] == ['low'])
d = S.parse_delta('```\n## ADDED Requirements\n### Requirement: Fake\n```\n## REMOVED Requirements\n```\n- `### Requirement: Fenced`\n```\n'
                  '- `### Requirement: Real`\n## RENAMED Requirements\n~~~\nFROM: ### Requirement: no\n~~~\n')
ok('fenced content ignored', d['added'] == [] and d['removed'] == ['Real'] and d['renamed'] == [] and not d['errors'])
d = S.parse_delta('## ADDED Requirements\n<!--\n' + req('Hidden') + '-->\n' + req('Shown'))
ok('commented requirement never applied', [n for n, _ in d['added']] == ['Shown'])
ok('backtick info with backtick is not a fence', S.fence_mask(['``` a`b', 'x']) == [False, False])
ok('tilde fence with backtick opens', S.fence_mask(['~~~ a`b', 'x', '~~~', 'y']) == [True, True, True, False])
ok('closed ATX title', S.parse_delta('## ADDED Requirements ##\n### Requirement: T ###\n')['added'][0][0] == 'T')
d = S.parse_delta('## RENAMED Requirements\n- FROM: `### Requirement: Old`\n- TO: `### Requirement: New`\nFROM: ### Requirement: Lone\n')
ok('rename pair', d['renamed'] == [('Old', 'New')])
ok('unpaired rename is error', any('Lone' in e for e in d['errors']))
ok('orphan requirement is error', S.parse_delta('## Added\n' + req('O'))['errors'] != [])
names = [n for n, _ in S.scenarios('#### Scenario: a ###\n##### deeper\n```\n#### fenced\n```\n#### scenario: b\n')]
ok('scenario names', names == ['a', 'b'])

# --- block validation ---
e, w = S.block_issues('ADDED', 'x', req('x', body='It should work.'))
ok('SHALL/MUST required', any('SHALL' in i for i in e))
e, w = S.block_issues('ADDED', 'x', '### Requirement: x\nIt MUST.\n### Scenario: three\n')
ok('three-hash scenario rejected', any('Scenario' in i for i in e))
e, w = S.block_issues('ADDED', 'x', '### Requirement: x\nIt MUST.\n#### Scenario: s\n- AND z\n')
ok('missing steps warns', not e and len(w) == 1)
ok('SHALL only in scenario fails', S.block_issues('ADDED', 'x', req('x', body='nope') + 'SHALL\n')[0] != [])

# --- merge ---
MAIN = '# c Specification\n\n## Purpose\n\nP.\n\n## Requirements\n\n' + req('One') + '\n' + req('Two') + '\n## Notes\n\nkeep\n'
plan = lambda t: S.parse_delta(t)
text, w = S.merge(MAIN, plan('## RENAMED Requirements\nFROM: ### Requirement: One\nTO: ### Requirement: Uno\n'
                             '## MODIFIED Requirements\n' + req('Uno', body='It MUST change.') +
                             '## REMOVED Requirements\n### Requirement: Two\n## ADDED Requirements\n' + req('Three')))
ok('ops applied', 'Uno' in text and 'MUST change' in text and 'Requirement: Two' not in text and 'Requirement: Three' in text)
ok('order kept, tail kept', text.index('Uno') < text.index('Three') < text.index('## Notes') and 'keep' in text and 'P.' in text)
add = plan('## ADDED Requirements\n' + req('Three'))
once = S.merge(MAIN, add)[0]
ok('re-apply is idempotent', S.merge(once, add)[0] == once)
ok('ADDED clash', fails(lambda: S.merge(MAIN, plan('## ADDED Requirements\n' + req('One', 'other'))), 'already exists'))
ok('ADDED case near miss', fails(lambda: S.merge(MAIN, plan('## ADDED Requirements\n' + req('one'))), 'spells it'))
ok('MODIFIED missing', fails(lambda: S.merge(MAIN, plan('## MODIFIED Requirements\n' + req('Nine'))), 'not found'))
ok('MODIFIED scenario loss', fails(lambda: S.merge(MAIN, plan('## MODIFIED Requirements\n' + req('One', 'renamed'))), 'drops scenario'))
t2, w = S.merge(MAIN, plan('## REMOVED Requirements\n### Requirement: Gone\n'))
ok('REMOVED absent warns', len(w) == 1)
ok('conflict across sections', fails(lambda: S.merge(MAIN, plan('## ADDED Requirements\n' + req('One') +
   '## REMOVED Requirements\n### Requirement: One\n')), 'both ADDED and REMOVED'))
ok('duplicate in section', fails(lambda: S.merge(MAIN, plan('## ADDED Requirements\n' + req('Z') + req('Z'))), 'duplicate'))
ok('new spec: ADDED only', fails(lambda: S.merge(None, plan('## MODIFIED Requirements\n' + req('One'))), 'only ADDED'))
new = S.merge(None, plan('## Purpose\nWhy it exists.\n## ADDED Requirements\n' + req('N')), 'auth', 'c1')[0]
ok('new spec skeleton', new.startswith('# auth Specification') and 'Why it exists.' in new and 'Requirement: N' in new)
hidden = MAIN.replace('\n## Notes', '\n### Foreign\nprecious\n\n## Notes')
ok('foreign ### not dropped', fails(lambda: S.merge(hidden, plan('## REMOVED Requirements\n### Requirement: Two\n')), 'lost'))
ok('delta header in main spec refused', fails(lambda: S.merge('## ADDED Requirements\n', add), 'delta headers'))

# --- tasks ---
t = S.tasks('- [ ] 1.1 a\n* [x] b\n1. [X] c\n- [link](u)\n```\n- [ ] fenced\n```\n<!-- - [ ] hid -->\n')
ok('checkbox parse', [x[0] for x in t] == [False, True, True])
ok('templates count as unfilled', not any(S.filled(v) for v in S.TEMPLATES.values()))

# --- CLI end to end ---
root = tempfile.mkdtemp()
o = os.path.join(root, 'openspec')
D = ['--dir', root]
ok('new', cli('new', 'add-login', *D)[0] == 0)
ok('new twice refused', cli('new', 'add-login', *D)[0] == 1)
ok('bad names refused', all(cli('new', n, *D)[0] == 1 for n in ('../x', 'Bad', 'archive')))
ok('bad capability refused', cli('add', 'add-login', 'specs', '../../x', *D)[0] == 1)
c, out = cli('status', 'add-login', *D)
ok('status: proposal first', 'next: write proposal' in out and 'tasks blocked' in out)
cdir = os.path.join(o, 'changes', 'add-login')
S.write(os.path.join(cdir, 'proposal.md'), '## Why\n\nUsers need login.\n')
ok('status: specs next', 'next: write specs' in cli('status', 'add-login', *D)[1])
ok('check without deltas fails', cli('check', 'add-login', *D)[0] == 1)
ok('add specs', cli('add', 'add-login', 'specs', 'identity/auth', *D)[0] == 0)
spec = os.path.join(cdir, 'specs', 'identity', 'auth', 'spec.md')
ok('no overwrite', cli('add', 'add-login', 'specs', 'identity/auth', *D)[0] == 1)
S.write(spec, '## ADDED Requirements\n' + req('Login'))
S.write(os.path.join(cdir, 'tasks.md'), '- [x] 1.1 model\n- [ ] 1.2 endpoint\n')
c, out = cli('status', 'add-login', *D)
ok('status prints only next task', 'tasks 1/2 [actual]' in out and 'next: 1.2 endpoint' in out and 'model' not in out)
c, out = cli('check', 'add-login', '--strict', *D)
ok('check passes strict', c == 0 and 'PASS' in out)
ok('list', 'add-login  tasks 1/2 [actual]' in cli('list', *D)[1])
c, out = cli('archive', 'add-login', *D)
ok('open tasks block archive', c == 1 and not os.path.exists(os.path.join(o, 'specs')))
S.write(os.path.join(cdir, 'tasks.md'), '- [x] 1.1 model\n- [x] 1.2 endpoint\n')
S.write(os.path.join(cdir, 'specs', 'zz', 'spec.md'), '## MODIFIED Requirements\n' + req('No'))
ok('one bad delta writes nothing', cli('archive', 'add-login', *D)[0] == 1 and not os.path.exists(os.path.join(o, 'specs')))
os.remove(os.path.join(cdir, 'specs', 'zz', 'spec.md'))
S.write(os.path.join(cdir, 'specs', 'loose.md'), 'x')
ok('stray spec file is error', 'ignored' in cli('check', 'add-login', *D)[1])
os.remove(os.path.join(cdir, 'specs', 'loose.md'))
ok('archive', cli('archive', 'add-login', *D)[0] == 0)
ok('spec written', 'Requirement: Login' in (S.read(os.path.join(o, 'specs', 'identity', 'auth', 'spec.md')) or ''))
ok('change moved', not os.path.exists(cdir) and os.listdir(os.path.join(o, 'changes', 'archive'))[0].endswith('-add-login'))
out = cli('list', '--specs', *D)[1]
ok('spec overview is names only', 'identity/auth' in out and '- Login' in out and 'SHALL' not in out)

cli('new', 'drop-it', *D)
S.write(os.path.join(o, 'changes', 'drop-it', 'proposal.md'), 'Retire login.\n')
cli('add', 'drop-it', 'specs', 'identity/auth', *D)
ok('template delta not done', 'next: write specs' in cli('status', 'drop-it', *D)[1])
S.write(os.path.join(o, 'changes', 'drop-it', 'specs', 'identity', 'auth', 'spec.md'), '## REMOVED Requirements\n### Requirement: Login\n')
ok('removal-only delta is done', 'specs done' in cli('status', 'drop-it', *D)[1])
main_spec = os.path.join(o, 'specs', 'identity', 'auth', 'spec.md')
open(main_spec, 'ab').write(b'\xff')
ok('non-UTF8 spec refused untouched', cli('archive', 'drop-it', *D)[0] == 1 and open(main_spec, 'rb').read().endswith(b'\xff'))

# symlinked capability must not write outside openspec/
away = tempfile.mkdtemp()
cli('new', 'evil', *D)
os.symlink(away, os.path.join(o, 'specs', 'out'))
S.write(os.path.join(o, 'changes', 'evil', 'specs', 'out', 'spec.md'), '## ADDED Requirements\n' + req('E'))
ok('symlink escape refused', cli('archive', 'evil', *D)[0] == 1 and os.listdir(away) == [])
S.write(os.path.join(o, 'changes', 'evil', '.openspec.yaml'), 'skip_specs: true\n')
ok('skip_specs conflicts with deltas', 'skip_specs' in cli('check', 'evil', *D)[1])
ok('usage exit 2', cli()[0] == 2 and cli('bogus', *D)[0] == 2 and cli('list', '--nope')[0] == 2)
ok('plan ref points at tz spec', 'tz spec status' in open(os.path.join(Z, 'skills/tz-craft/references/plan.md')).read())
ok('licence kept', 'FISSION AI' in open(os.path.join(Z, 'third_party/openspec/LICENSE')).read())
done()
