# tree-sitter integration (bin/tzts.py): stdlib fallback with the packages absent, tag rules against a stub, real package if present.
import contextlib, io, os, sys, tempfile, types
from harness import ok, done, Z
import tzts, tzmap

NAMES = ['tree_sitter'] + ['tree_sitter_' + x for x in ('python', 'javascript', 'typescript', 'ruby', 'go', 'bash', 'php')]
REAL = {n: sys.modules.get(n) for n in NAMES}


def absent():
    """Make every optional package raise ImportError."""
    for n in NAMES:
        sys.modules[n] = None


def restore():
    """Put the real import state back."""
    for n in NAMES:
        sys.modules.pop(n, None)
        if REAL[n] is not None:
            sys.modules[n] = REAL[n]


D = tempfile.mkdtemp()


def put(name, text):
    """Write a fixture file."""
    p = os.path.join(D, name)
    open(p, 'w').write(text)
    return p


def cli(*args):
    """(exit code, stdout) of main()."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        rc = tzts.main(list(args))
    return rc, out.getvalue()


def names(found, role='def'):
    return [t['qual'] for t in found if t['role'] == role]


# --- packages absent: stdlib fallback ---
absent()
ok('absent: parse returns None', tzts.parse('x = 1', 'python') is None)
py = put('a.py', 'class MyClass(Base):\n    def my_method(self):\n        def inner(): pass\n        return helper("ghost()")\n\ndef my_function():  # comment_word\n    return MyClass().my_method()\n')
e, t = tzts.tags(py)
ok('py ast engine', e == 'ast')
ok('py defs qualified', names(t) == ['MyClass', 'MyClass.my_method', 'MyClass.inner', 'my_function'])
ok('py nested def is local', [x['local'] for x in t if x['name'] == 'inner'] == [True])
ok('py refs', {'Base', 'helper', 'MyClass', 'my_method'} <= set(names(t, 'ref')))
ok('py string is not a ref', 'ghost' not in names(t, 'ref'))
ok('defs() equals tzmap when absent', tzts.defs(py) == tzmap.defs_methods(py))
w = tzts.words(open(py).read(), 'python')
ok('words skip strings and comments', w['my_method'] == 2 and not w['ghost'] and not w['comment_word'])
js = put('b.ts', '// function fake() {}\nexport interface Shape { a: number }\nexport function area(s: Shape) { return scale(s, "bogus(1)") }\nexport const twice = (x) => x * 2\nclass Box {\n  open() { area(this) }\n}\n')
e, t = tzts.tags(js)
ok('ts regex engine', e == 'regex')
ok('ts defs', names(t) == ['Shape', 'area', 'twice', 'Box'])
ok('ts calls, not method defs/strings', sorted(names(t, 'ref')) == ['area', 'scale'])
w = tzts.words(open(js).read(), 'typescript')
ok('ts words masked', w['area'] == 2 and not w['fake'] and not w['bogus'])
sh = put('c.sh', '# old() { :; }\nrun() {\n  echo hi\n}\nfunction stop_it {\n  :\n}\n')
ok('sh defs', names(tzts.tags(sh)[1]) == ['run', 'stop_it'])
bad = put('d.py', 'def good():\n    pass\ndef broken(:\n')
e, t = tzts.tags(bad)
ok('broken py still tagged', e == 'regex' and names(t) == ['good', 'broken'])
e, errs = tzts.errors(bad)
ok('broken py error line', e == 'ast' and errs and errs[0][0] == 3)
ok('clean py', tzts.errors(py) == ('ast', []))
ok('clean ts scanner', tzts.errors(js) == ('scanner', []))
ok('unbalanced js', tzts.errors('x.js', 'function a() { (')[1] != [])
ok('unterminated js', tzts.errors('x.js', 'const s = "abc\n')[1] != [])
go = put('e.go', 'package m\nfunc A() { b() }\n')
ok('go absent: none', tzts.tags(go) == ('none', []) and tzts.errors(go) == ('none', []))
ok('go absent: skeleton unchanged', tzts.skeleton(open(go).read(), 'go') == (open(go).read(), False))
flat = put('g.py', 'class C:\n    def my_method(self):\n        return "ghost"\n')
sk, good = tzts.skeleton(open(flat).read(), 'python')
ok('py skeleton via tzcompress', good and 'def my_method' in sk and 'ghost' not in sk)
sk, good = tzts.skeleton('function a(x) { return x + 41 }\n', 'javascript')
ok('js skeleton via scanner', good and '41' not in sk)
ok('unknown ext / missing file', tzts.tags(put('f.zzz', 'x'))[0] == 'none' and tzts.tags(D + '/no.py')[0] == 'none')
ok('oversize skipped', tzts.tags('big.py', 'x=1\n' * 300000)[0] == 'none')
rc, out = cli('ts', 'tags', py)
ok('cli tags', rc == 0 and 'L2 def.method MyClass.my_method' in out and '[actual]' in out and 'ref.' not in out)
ok('cli refs', 'ref.call helper' in cli('tags', py, '--refs')[1])
ok('cli check codes', cli('check', py)[0] == 0 and cli('check', bad)[0] == 1 and cli('check', go)[0] == 2)
ok('cli skel', cli('skel', flat)[0] == 0 and cli('skel', go)[0] == 1)
rc, out = cli('doctor')
ok('cli doctor says absent', rc == 0 and 'not installed' in out and 'python      tags: ast' in out)
ok('cli usage', cli()[0] == 2 and cli('tags', D + '/no.py')[0] == 2)


# --- stub package: tag rules and both query APIs (parity: upstream docs/src/4-code-navigation.md Ruby example) ---
class N:
    def __init__(s, src, text, start=0, end=None, type_='identifier', kids=(), has_error=False, missing=False):
        a = src.index(text, start)
        s.start_byte, s.end_byte = a, end if end is not None else a + len(text)
        s.start_point = (src[:a].count('\n'), 0)
        s.end_point = (src[:s.end_byte].count('\n'), 0)
        s.type, s.children, s.has_error, s.is_missing, s.body = type_, list(kids), has_error, missing, None

    def child_by_field_name(s, f):
        return s.body


RB = 'module Foo\n  class Bar\n    def baz\n      qux\n    end\n  end\nend\n'
A = lambda kw, end: N(RB, kw, end=end)
foo, bar, baz, qux = (N(RB, x) for x in ('Foo', 'Bar', 'baz', 'qux'))
mod_n, cls_n, def_n = A('module', len(RB)), A('class', RB.rindex('end')), A('def', RB.index('  end'))
MATCHES = [(2, {'name': [baz], 'definition.function': [def_n]}),
           (0, {'name': [foo], 'definition.module': [mod_n]}),
           (1, {'name': [bar], 'definition.class': [cls_n]}),
           (1, {'name': [baz], 'definition.method': [def_n]}),
           (3, {'name': [qux], 'reference.call': [qux]}),
           (4, {'name': [N(RB, 'end', has_error=True)], 'definition.function': [def_n]}),
           (5, {'doc': [foo]})]
root = N(RB, 'module', end=len(RB), type_='program')


def stub(new_api, matches, tree=root):
    """Install a fake tree_sitter plus a ruby grammar returning `matches`."""
    ts = types.ModuleType('tree_sitter')
    ts.Language = lambda raw: types.SimpleNamespace(query=lambda q: types.SimpleNamespace(
        matches=lambda r: [(i, {k: v[0] for k, v in c.items()}) for i, c in matches]))
    ts.Parser = lambda lang: types.SimpleNamespace(parse=lambda b: types.SimpleNamespace(root_node=tree))
    if new_api:
        ts.Query = lambda lang, q: q
        ts.QueryCursor = lambda q: types.SimpleNamespace(matches=lambda r: matches)
    g = types.ModuleType('tree_sitter_ruby')
    g.language, g.TAGS_QUERY = (lambda: 1), '(x) @name'
    absent()
    sys.modules['tree_sitter'], sys.modules['tree_sitter_ruby'] = ts, g


rb = put('test.rb', RB)
for api in (True, False):
    stub(api, MATCHES)
    e, t = tzts.tags(rb)
    label = 'new api' if api else 'old api'
    ok(label + ': engine', e == 'tree-sitter')
    got = [(x['name'], x['kind'], x['line']) for x in t if x['role'] == 'def']
    ok(label + ': upstream parity, earliest pattern wins, error name skipped',
       got == [('Foo', 'module', 1), ('Bar', 'class', 2), ('baz', 'method', 3)])
    ok(label + ': qualified', names(t) == ['Foo', 'Foo.Bar', 'Foo.Bar.baz'])
    ok(label + ': reference', names(t, 'ref') == ['qux'])
    ok(label + ': defs()', tzts.defs(rb) == ['Foo', 'Foo.Bar', 'Foo.Bar.baz'])
stub(True, MATCHES + [(0, {'ignore': [qux]})])
ok('@ignore drops the tag', names(tzts.tags(rb)[1], 'ref') == [])
stub(True, MATCHES)
sys.modules['tree_sitter'].QueryCursor = lambda q: 1 / 0
ok('query failure falls back', tzts.tags(rb) == ('none', []))
ok('query failure: defs() = tzmap', tzts.defs(rb) == tzmap.defs_methods(rb))
err = N(RB, 'qux', type_='ERROR', has_error=True)
miss = N(RB, 'baz', type_='end', missing=True)
stub(True, [], N(RB, 'module', end=len(RB), type_='program', kids=[err, miss], has_error=True))
ok('ERROR and MISSING nodes reported', tzts.errors(rb) == ('tree-sitter', [(3, 'missing end'), (4, 'syntax error')]))
ok('errored tree: no skeleton', tzts.skeleton(RB, 'ruby') == (RB, False))
leaves = [N(RB, 'Foo', type_='constant'), N(RB, 'qux'), N(RB, 'baz', type_='comment')]
stub(True, [], N(RB, 'module', end=len(RB), type_='program', kids=leaves))
ok('identifier leaves counted, comments not', dict(tzts.words(RB, 'ruby')) == {'Foo': 1, 'qux': 1})
GO = 'func A() { b() }\n'
fn = N(GO, 'func', end=len(GO) - 1, type_='function_declaration')
fn.body = N(GO, '{', end=len(GO) - 1, type_='block')
stub(True, [], N(GO, 'func', type_='source_file', end=len(GO), kids=[fn]))
sys.modules['tree_sitter_go'] = sys.modules['tree_sitter_ruby']
ok('brace body cut', tzts.skeleton(GO, 'go') == ('func A() { ... }\n', True))
sys.modules['tree_sitter'].Language = lambda raw: 1 / 0
ok('ABI error falls back', tzts.parse(GO, 'go') is None)

# --- real packages, only if the user already has them ---
restore()
if tzts.parse('def f(): pass', 'python') and tzts._queries('python'):
    e, t = tzts.tags(py)
    ok('real: engine and method', e == 'tree-sitter' and 'MyClass.my_method' in names(t))
    ok('real: error found', tzts.errors(bad)[1] != [])
else:
    print('SKIP: real tree_sitter + tree_sitter_python not installed')
done()
