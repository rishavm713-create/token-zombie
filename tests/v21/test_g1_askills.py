import contextlib, io, json, os, tempfile
from harness import ok, done, Z
import tzaskills as A


def doc(fm, body='x\n'):
    return f'---\n{fm}\n---\n{body}'


def check(fm, want, label, strict=True):
    v, m = A.validate_text(fm if fm.startswith(('---', '#')) else doc(fm), strict)
    ok(f'{label}: {m}', (v and want == 'valid') or (not v and want in m))


# parity with upstream quick_validate.py, one case per rule
base = 'name: my-skill\ndescription: Does a thing.'
check(base, 'valid', 'minimal')
check(base + '\nlicense: x\nallowed-tools:\n- Read\n- Bash\nmetadata:\n  a: b\ncompatibility: py3', 'valid', 'all allowed keys')
check('# no frontmatter', 'No YAML frontmatter found', 'none')
check('---\nname: a\n', 'Invalid frontmatter format', 'unclosed')
check('just text', 'Invalid YAML', 'not a mapping')
check('# only a comment', 'No YAML', 'comment')
check(base + '\nfoo: 1', 'Unexpected key(s) in SKILL.md frontmatter: foo', 'extra key')
check('description: d', "Missing 'name'", 'no name')
check('name: a', "Missing 'description'", 'no desc')
check('name: 12\ndescription: d', 'Name must be a string', 'int name')
check('name:\ndescription: d', 'Name must be a string', 'null name')
check('name: My_Skill\ndescription: d', 'kebab-case', 'case')
for n in ('-a', 'a-', 'a--b'):
    check(f'name: {n}\ndescription: d', 'consecutive hyphens', n)
check(f'name: {"a" * 64}\ndescription: d', 'valid', 'name 64')
check(f'name: {"a" * 65}\ndescription: d', 'Name is too long (65', 'name 65')
check('name: a\ndescription: [x]', 'Description must be a string', 'list desc')
check('name: a\ndescription: use <tag>', 'angle brackets', 'brackets')
check(f'name: a\ndescription: {"d" * 1024}', 'valid', 'desc 1024')
check(f'name: a\ndescription: {"d" * 1025}', 'Description is too long (1025', 'desc 1025')
check(base + '\ncompatibility: ' + 'c' * 501, 'Compatibility is too long', 'compat long')
check(base + '\ncompatibility: 5', 'Compatibility must be a string', 'compat type')

# stdlib frontmatter reader
check('name: a\ndescription: Use when: asked', 'Invalid YAML', 'unquoted colon')
check('name: a\ndescription: "Use when: asked"', 'valid', 'quoted colon')
check('name: a\ndescription: "open', 'Invalid YAML', 'open quote')
check('name: a\ndescription: [x', 'Invalid YAML', 'open list')
p = A.parse_frontmatter
ok('folded', p('description: >-\n  one\n  two')['description'] == 'one two')
ok('literal', p('description: |\n  one: x\n  two')['description'] == 'one: x\ntwo')
ok('multi-line plain', p('description: one\n  two')['description'] == 'one two')
ok('single quote', p("d: 'it''s'")['d'] == "it's")
ok('comment', p('# c\nname: a # c')['name'] == 'a')
ok('url and hash', p('d: see http://x.y/a#b')['d'] == 'see http://x.y/a#b')

cc = base + '\ndisable-model-invocation: true'
check(cc, 'Unexpected key', 'strict rejects Claude Code key')
check(cc, 'valid', 'default accepts Claude Code key', strict=False)

with tempfile.TemporaryDirectory() as t:
    def put(name, text):
        os.makedirs(os.path.join(t, name))
        f = os.path.join(t, name, 'SKILL.md')
        open(f, 'w', newline='').write(text)
        return f

    def run(*a):
        o = io.StringIO()
        with contextlib.redirect_stdout(o), contextlib.redirect_stderr(o):
            c = A.main(list(a))
        return c, o.getvalue()

    good = put('good', doc('name: good\ndescription: ' + 'd' * 386).replace('\n', '\r\n'))
    r = A.inspect(good)
    ok('crlf + cost', not r['error'] and r['desc'] == 386 and r['tokens'] == 100)
    hidden = put('hidden', doc('name: hidden\ndescription: dd\ndisable-model-invocation: true'))
    ok('hidden skill costs 0', A.inspect(hidden)['tokens'] == 0)
    c, o = run(t)
    ok('clean exit 0', c == 0 and '2 skills, 0 invalid' in o and '~100 tok per chat' in o)
    ok('budget equal passes', run(t, '--budget', '100')[0] == 0)
    c, o = run(t, '--budget', '99')
    ok('budget fails', c == 1 and 'OVER BUDGET' in o)
    c, o = run(t, '--max-desc', '100')
    ok('max desc', c == 1 and 'LONG good' in o)
    big = put('big', doc('name: big\ndescription: d', 'line\n' * 501))
    c, o = run(big)
    ok('body warn only', c == 0 and 'WARN big: body 501 lines' in o)
    broken = put('broken', 'no frontmatter')
    c, o = run(t)
    ok('invalid exit 1', c == 1 and 'INVALID' in o and '4 skills, 1 invalid' in o)
    c, o = run(t, '--json')
    ok('json', c == 1 and len(json.loads(o)['skills']) == 4)
    ok('bad usage', run('--budget', 'x')[0] == 2 and run('--nope')[0] == 2 and run(os.path.join(t, 'none'))[0] == 2)
    raw = os.path.join(t, 'broken', 'SKILL.md')
    open(raw, 'wb').write(b'\xff\xfe\x00bad')
    ok('unreadable', A.inspect(raw)['error'].startswith('unreadable'))

    def ed(f, tool='Write'):
        return A.check_edit({'tool_name': tool, 'tool_input': {'file_path': f}})
    ok('advice clean', ed(good) is None)
    ok('advice invalid', 'unreadable' in ed(broken, 'Edit'))
    ok('advice long body', '501 lines' in ed(big))
    ok('advice ignores', ed(big, 'Read') is None and ed(os.path.join(t, 'x.py')) is None and A.check_edit({}) is None
       and A.check_edit({'tool_name': 'Write', 'tool_input': None}) is None)
done()
