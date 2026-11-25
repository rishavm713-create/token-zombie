# ast-grep integration (bin/tzsg.py): parity cases from upstream meta_var.rs / match_tree/mod.rs, translated to
# Python, plus the B-repo-intel spec cases and the CLI. Temp dir and temp HOME only.
import contextlib, io, os, subprocess, sys, tempfile, textwrap
from harness import ok, done, Z
import tzsg

TMP = tempfile.mkdtemp()
os.environ['HOME'] = TMP


def lines(pattern, src):
    return [h[0] for h in tzsg.search_source(tzsg.compile_pattern(pattern), textwrap.dedent(src))]


def hit(pattern, src):
    return bool(lines(pattern, src))


def caps(pattern, src):
    return tzsg.search_source(tzsg.compile_pattern(pattern), src)[0][2]


def bad(pattern):
    try:
        tzsg.compile_pattern(pattern)
    except tzsg.PatternError:
        return True
    return False


# meta_var.rs test_match_var / test_not_meta_var
for tok, want in [('$$$', ('multi', None)), ('$ABC', ('single', 'ABC')), ('$$ABC', ('single', 'ABC')),
                  ('$MATCH1', ('single', 'MATCH1')), ('$$$ABC', ('multi', 'ABC')), ('$_', ('single', None)),
                  ('$_123', ('single', None)), ('$$_', ('single', None)), ('$$$_A', ('multi', None)),
                  ('$123', None), ('$$$123', None), ('$', None), ('$$', None), ('abc', None), ('$abc', None)]:
    ok(f'meta_var {tok}', tzsg.meta_var(tok) == want)
for p in ['f($123)', 'f($$$123)', 'f($abc)', 'f($Ab)', 'x$A', 'def (', '', '   ']:
    ok(f'bad pattern {p!r}', bad(p))

# match_tree/mod.rs: (pattern, source, expected)
CASES = [
    ('foo($$$)', 'foo(a, b, c)', True), ('foo($$$)', 'foo()', True),
    ('foo($$$A, c)', 'foo(a, b, c)', True), ('foo($$$A, b, c)', 'foo(a, b, c)', True),
    ('foo($$$A, a, b, c)', 'foo(a, b, c)', True), ('foo($$$A, a, b, c)', 'foo(b, c)', False),
    ('foo($$$, c)', 'foo(a, b, c)', True), ('foo($$$, a, b, c)', 'foo(b, c)', False),
    ('foo(a, $$$)', 'foo(a, b, c)', True), ('foo(a, b, $$$)', 'foo(a, b, c)', True),
    ('foo(a, b, c, $$$)', 'foo(b, c)', False),
    ('return $A', 'return 123', True), ('return $_', 'return 123', True),
    ('return $A', 'return', False), ('return $_', 'return', False),
    ('$A($$$)', 'test(123)', True), ('$A($B)', 'test(123)', True), ('$A($A)', 'test(aaa)', False),
    ('$A($A)', 'test(123)', False), ('$A($A, $A)', 'test(123, 456)', False), ('$A($A)', 'test(test)', True),
    ('$A($A)', 'foo(bar)', False), ('foo($A, $B)', 'foo(a, b,)', True), ('$A($B)', 'foo(  # c\n bar)', True),
    ('from a import $$$A, B, $$$C', 'from a import x, B, y, z', True),
    ('from a import $$$A, B, $$$C', 'from a import x, y', False),
    ('lambda $P: $F($P)', 'g = lambda x: bar(x)', True), ('lambda $P: $F($P)', 'g = lambda x: bar(y)', False),
    ('def _():\n    $$$A\n    $P = g()\n    $Q = h()\n    $$$B',
     'def _():\n    a = 0\n    p = g()\n    q = h()\n    c = 1', True),
]
for p, s, want in CASES:
    ok(f'parity {p!r} {s!r}', hit(p, s) is want)

# B-repo-intel section 4 spec cases
SRC = 'print(x)\nprint(x, y)\nprint()\n'
ok('single arg', lines('print($A)', SRC) == [1])
ok('multi args', lines('print($$$A)', SRC) == [1, 2, 3])
ok('repeat var', lines('$A == $A', 'a = x == x\nb = x == y\n') == [1])
ok('repeat var arithmetic', lines('$A + $A', 'x + x\nx + y\n') == [1])
ok('repeat var across load/store', hit('$A = $A', 'x = x') and not hit('$A = $A', 'x = y'))
ok('one-line return funcs', lines('def $F($$$P): return $X',
   'def a(): return 1\ndef b(x, *y, z=2, **k): return x\ndef c():\n    x = 1\n    return x\n') == [1, 2])
ok('subscript only', lines('os.environ[$K]', 'os.environ["A"]\nos.environ.get("A")\nos.environ\n') == [1])
ok('dollar-dollar as single', hit('f($$A)', 'f(1)'))
ok('unnamed dropped differs', hit('f($_, $_)', 'f(1, 2)'))

# Python-shape behaviour
ok('multi covers keywords and stars', all(hit('foo($$$A)', s) for s in ['foo(k=1)', 'foo(*a, **b)', 'foo(1, k=2)']))
ok('keyword then rest', hit('foo(t=$T, $$$)', 'foo(t=1, u=2)') and not hit('foo(t=$T, $$$)', 'foo(u=2)'))
ok('single arg matches keyword', hit('foo($A)', 'foo(k=1)'))
ok('keyword name var', caps('foo($K=1)', 'foo(bar=1)') == {'K': 'bar'})
ok('attribute var', caps('self.$ATTR = $V', 'self.name = "n"') == {'ATTR': 'name', 'V': '"n"'})
ok('multi capture text', caps('f($$$ARGS)', 'f(1, k = 2)') == {'ARGS': '1, k = 2'})
ok('string literal stays literal', hit('f("$A")', 'f("$A")') and not hit('f("$A")', 'f("b")'))
ok('constant types differ', not hit('f(1)', 'f(True)') and not hit('f(1)', 'f(1.0)'))
ok('decorated and annotated assign', lines('def $F(): $$$', '@d\ndef a(): pass\n') == [2] and hit('$A: int = 1', 'self.x: int = 1'))
ok('decorator required', not hit('@d\ndef $F(): $$$', 'def a(): pass'))
ok('one param vs two', hit('def $F($A): $$$', 'def a(x: int): pass') and not hit('def $F($A): $$$', 'def a(x, y): pass'))
ok('param then rest', hit('def $F(self, $$$): $$$B', 'def a(self, x=1): pass') and hit('def $F(a=1, $$$P): $$$', 'def f(a=1, b=2): pass'))
ok('class bases', hit('class $C(Base, $$$): $$$', 'class X(Base, metaclass=M):\n    pass') and not hit('class $C: $$$', 'class X(B): pass'))
ok('dict pairs', hit('{"a": $V, $$$}', 'd = {"a": 1, "b": 2}') and not hit('{"a": $V}', 'd = {"a": 1, "b": 2}'))
ok('statement var', hit('if $C:\n    $S', 'if x:\n    return 1') and not hit('if $C:\n    $S', 'if x:\n    a\n    b'))
ok('multi statement window', lines('$X = open($P)\n$X.close()', 'def f():\n    a = 1\n    h = open(p)\n    h.close()\n    b()\n') == [3])
ok('multi statement binding', not hit('$X = open($P)\n$X.close()', 'h = open(p)\ng.close()'))
ok('bare var is expressions', lines('$A', 'pass\nx\n') == [2])
ok('async is distinct', not hit('def $F(): $$$', 'async def a(): pass'))

# files, cap, skips, CLI
root = os.path.join(TMP, 'repo')
os.makedirs(os.path.join(root, 'node_modules'))
os.makedirs(os.path.join(root, 'sub'))


def put(rel, text):
    with open(os.path.join(root, rel), 'w', encoding='utf-8') as f:
        f.write(text)


put('a.py', 'print(1)\nprint(2); print(3)\n')
put('sub/b.py', 'x = 1\nprint(x)\n')
put('sub/tool', '#!/usr/bin/env python3\nprint(9)\n')
put('sub/notes.txt', 'print(1)\n')
put('node_modules/c.py', 'print(1)\n')
put('broken.py', 'def (:\n')
rows, more, skipped = tzsg.search('print($A)', [root])
names = [(os.path.relpath(r[0], root).replace(os.sep, '/'), r[1]) for r in rows]
ok('walk + dedupe by line + skip dirs', names == [('a.py', 1), ('a.py', 2), ('sub/b.py', 2), ('sub/tool', 2)])
ok('unparseable counted', skipped == 1 and not more)
rows, more, _ = tzsg.search('print($A)', [root], cap=2)
ok('cap', len(rows) == 2 and more)
ok('exact cap is not more', tzsg.search('print($A)', [root], cap=4)[1] is False)
ok('duplicate paths once', len(tzsg.search('print($A)', [root, os.path.join(root, 'a.py')])[0]) == 4)


def cli(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = tzsg.main(list(args))
    return rc, out.getvalue(), err.getvalue()


one = os.path.join(root, 'sub', 'b.py')
rc, out, _ = cli('print($A)', one, '--captures')
ok('cli output', rc == 0 and out.splitlines()[0].endswith('b.py:2: print(x)  {A=x}') and '1 matching line(s) [actual]' in out)
rc, out, _ = cli('print($A)', '--max', '1', root)
ok('cli cap note', rc == 0 and 'capped at 1' in out and len(out.splitlines()) == 2)
ok('cli no match exit 1', cli('nothing($A)', root)[0] == 1)
rc, _, err = cli('def (', root)
ok('cli bad pattern exit 2', rc == 2 and 'not valid Python' in err)
ok('cli missing path exit 2', cli('x', os.path.join(root, 'nope'))[0] == 2)
r = subprocess.run([sys.executable, os.path.join(Z, 'bin', 'tzsg.py'), 'print($A)', 'sub'], cwd=root,
                   capture_output=True, text=True, timeout=60)
ok('script run, relative paths', r.returncode == 0 and r.stdout.startswith('sub/b.py:2: print(x)'))

# non-Python languages: only through an installed binary
path = os.environ.get('PATH', '')
os.environ['PATH'] = os.path.join(TMP, 'empty')
rc, _, err = cli('f($A)', root, '--lang', 'js')
ok('no binary unsupported', rc == 2 and 'UNSUPPORTED' in err)
if os.name == 'posix':
    bindir = os.path.join(TMP, 'fakebin')
    os.makedirs(bindir)

    def fake(name, version):
        p = os.path.join(bindir, name)
        with open(p, 'w') as f:
            f.write(f'#!{sys.executable}\nimport sys, json\nif sys.argv[1] == "--version": print("{version}")\n'
                    'else: print(json.dumps([{"file": "x.js", "lines": "f(1)", "range": {"start": {"line": 4}},'
                    ' "text": " ".join(sys.argv[1:])}]))\n')
        os.chmod(p, 0o755)

    os.environ['PATH'] = bindir
    fake('sg', 'sg from shadow-utils')
    ok('unrelated sg ignored', tzsg.find_binary() is None)
    fake('sg', 'ast-grep 0.0.0')
    rc, out, _ = cli('f($A)', root, '--lang', 'js')
    ok('pass-through 1-based line', rc == 0 and out.startswith('x.js:5: f(1)'))
os.environ['PATH'] = path

done()
