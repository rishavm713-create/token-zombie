# tzsym (serena, behaviour only): name-path matching, symbol trees for py/js/ts/sh, code-only references, CLI.
import os, subprocess, sys, tempfile, time
from harness import ok, done, Z
import tzsym as S


def parts(*names):
    return tuple((n, None) if isinstance(n, str) else n for n in names)


# name-path parity table: (pattern, symbol parts, substring, expected)
for pat, p, sub, want in [
    ('foo', ('foo',), 0, True), ('foo/', ('foo',), 0, True), ('foo', ('path', 'to', 'foo'), 0, True),
    ('foo', ('foobar',), 0, False), ('foo', ('bar', 'foobar'), 0, False), ('foo', ('bar', 'my_foobar_func'), 1, True),
    ('foo', ('bar', 'baz'), 1, False), ('/foo', ('foo',), 0, True), ('/foo', ('bar', 'foo'), 0, False),
    ('/foo', ('foo', 'bar'), 0, False), ('/foo/', ('foobar',), 1, True), ('/foo', ('bar', 'foo'), 1, False),
    ('bar/foo', ('mod', 'bar', 'foo'), 0, True), ('bar/foo', ('bar', 'foo', 'baz'), 0, False),
    ('bar/foo', ('foo',), 0, False), ('bar/foo', ('other', 'foo'), 0, False), ('bar/fo', ('bar', 'foo'), 1, True),
    ('bar/foo', ('baz', 'foobar'), 1, False), ('ba/foo', ('bar', 'foo'), 1, False), ('/bar/foo', ('bar', 'foo'), 0, True),
    ('/bar/foo', ('baz', 'bar', 'foo'), 0, False), ('bar/foo[1]', ('bar', ('foo', 0)), 0, False),
    ('bar/foo', (('bar', 0), ('foo', 1)), 0, True), ('bar[0]/foo', (('bar', 0), 'foo'), 0, True),
    ('bar[0]/foo[1]', (('bar', 0), ('foo', 1)), 0, True), ('bar[0]/foo[1]', (('bar', 1), ('foo', 0)), 0, False),
    ('', ('foo',), 1, False), ('/', ('foo',), 1, False)]:
    ok('match %r %r substr=%d' % (pat, p, sub), S.matches(pat, parts(*p), bool(sub)) is want)


def paths(tree):
    return [S.name_path(s) for s in S.flatten(tree, 'f')]


PY = '''import os
LIMIT = 3
LIMIT = 4


class MyClass:
    attr: int = 0

    @property
    def my_method(self):
        def inner():
            local = 1
            return local
        return inner


if os:
    def guarded():
        pass


class C:
    def f(self):
        pass

    def f(self, x):
        pass
'''
t = S.py_tree(PY)
ok('py: paths', paths(t) == ['LIMIT', 'MyClass', 'MyClass/attr', 'MyClass/my_method', 'MyClass/my_method/inner',
                             'guarded', 'C', 'C/f[0]', 'C/f[1]'])
flat = S.flatten(t, 'f')
m = flat[3]
ok('py: decorator inside range', (m['start'], m['line'], m['end'], m['kind']) == (9, 10, 14, 'method'))
ok('py: broken file is None, not empty', S.py_tree('def (:\n') is None)

TS = '''import type { X } from './x';
// class Ghost {}
const s = "function fake() {}";
export class UserService<T> extends Base {
  private cache: Map<string, T> = new Map();
  constructor(
    private readonly db: Db,
  ) { super(); }
  async getUser(id: string): { ok: boolean } {
    const local = 1;
    if (id) { return this.load(`u-${fmt(id)} text`); }
  }
  static create() { return /}/g; }
}
interface Shape {
  area(): number
  name: string
}
export const handler = async (e) => {
  function nested() {}
};
export function render() {
  return <p>Don't {go()} </p>;
}
'''
t = S.js_tree(TS)
got = paths(t)
ok('ts: paths ' + str(got), got == [
    's', 'UserService', 'UserService/cache', 'UserService/constructor', 'UserService/getUser', 'UserService/create',
    'Shape', 'Shape/area', 'Shape/name', 'handler', 'handler/nested', 'render'])
rng = {S.name_path(s): (s['start'], s['end']) for s in S.flatten(t, 'f')}
ok('ts: class range', rng.get('UserService') == (4, 14))
ok('ts: type-literal return keeps the body', rng.get('UserService/getUser') == (9, 12))
ok('ts: arrow const range', rng.get('handler') == (19, 21))
masked = S.mask_js(TS)
ok('mask: same shape', len(masked) == len(TS) and masked.count('\n') == TS.count('\n'))
ok('mask: strings and comments gone, template code kept', 'Ghost' not in masked and 'fake' not in masked
   and 'fmt(id)' in masked and 'text' not in masked and 'go()' in masked)
ok('mask: unterminated quote fails open', 'after' in S.mask_js('x = "oops\nafter()\n'))

SH = 'foo() {\n  echo "}"\n}\nfunction bar { :; }\n  baz () {\n    foo # foo\n  }\n'
t = S.sh_tree(SH)
ok('sh: functions and ranges', [(s['name'], s['start'], s['end']) for s in t]
   == [('foo', 1, 3), ('bar', 4, 4), ('baz', 5, 7)])

# project on disk
T = tempfile.mkdtemp()


def put(rel, text):
    p = os.path.join(T, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w') as f:
        f.write(text)


put('src/cfg.py', 'class MyClass:\n    def my_method(self):\n        return parse_config(1)\n\n\ndef parse_config(p):\n    return p\n')
put('src/app.py', 'from cfg import parse_config\n# parse_config here\ns = "parse_config"\nx = parse_config(1)\n')
put('tests/test_cfg.py', 'def test_it():\n    assert parse_config(2)\n')
put('src/u.ts', 'export function load() {}\n// load()\nconst a = "load";\nload();\n')
put('bin/tool', '#!/usr/bin/env python3\ndef from_script():\n    pass\n')
put('bin/run.sh', 'deploy() {\n  :\n}\n# deploy\ndeploy\n')
put('src/broken.py', 'def oops(:\n    parse_config(3)\n')
put('node_modules/x/y.js', 'function parse_config() {}\n')


def run(*args):
    r = subprocess.run([sys.executable, os.path.join(Z, 'bin', 'tzsym.py')] + list(args), cwd=T,
                       capture_output=True, text=True, timeout=30)
    return r.returncode, r.stdout


for pat, hit in [('my_method', True), ('MyClass/my_method', True), ('/my_method', False), ('/MyClass/my_method', True)]:
    c, o = run(pat)
    ok('cli: ' + pat, ('MyClass/my_method  method  src/cfg.py:2-3' in o) is hit and c == (0 if hit else 1))
c, o = run('my_meth')
ok('cli: no substr by default, hint given', c == 1 and '--substr' in o)
c, o = run('my_meth', '--substr')
ok('cli: --substr', c == 0 and 'MyClass/my_method' in o)
c, o = run('MyClass', '--depth', '1')
ok('cli: --depth lists members', '  MyClass/my_method' in o)
ok('cli: depth 0 does not', 'my_method' not in run('MyClass')[1])
c, o = run('--in', 'src/cfg.py')
ok('cli: overview of one file', c == 0 and 'MyClass  class' in o and 'parse_config  function' in o and 'app.py' not in o)
c, o = run('parse_config', '--body')
ok('cli: --body prints exact lines', '    6  def parse_config(p):' in o and '    7      return p' in o and 'class MyClass' not in o)
c, o = run('parse_config', '--in', 'tests')
ok('cli: --in limits definitions', c == 1)
c, o = run('parse_config', '--refs')
ok('refs: real use with holder', c == 0 and 'x = parse_config(1)' in o and '3 in MyClass/my_method:' in o)
ok('refs: comment and string lines excluded', '# parse_config here' not in o and 's = "parse_config"' not in o)
ok('refs: def line excluded', 'def parse_config' not in o.split('references to', 1)[1])
ok('refs: tests flagged', 'tests/test_cfg.py [test]' in o and 'tests among them: tests/test_cfg.py' in o)
ok('refs: unparsed file still searched and reported', 'src/broken.py' in o and '1 unparsed' in o)
ok('refs: skipped dirs stay out', 'node_modules' not in o)
c, o = run('load', '--refs')
ok('refs: ts comment/string excluded', '  4: load();' in o and '1 line(s) in 1 file(s) [actual]' in o)
c, o = run('deploy', '--refs')
ok('refs: sh', '  5: deploy' in o and '1 line(s)' in o)
ok('cli: shebang script found', 'from_script  function  bin/tool:2-3' in run('from_script')[1])
c, o = run('print', '--refs')
ok('refs: nothing anywhere', c == 1 and 'no code references' in o)
ok('cli: usage error', run()[0] == 2 and run('x', '--refs', '--body')[0] == 2 and run('--in', 'src', '--refs')[0] == 2)
put('many.py', ''.join('class K%d:\n    def dup(self):\n        dup()\n' % i for i in range(100)))
c, o = run('dup')
ok('cap: listing at most 60 lines + note', len([x for x in o.splitlines() if not x.startswith('not fully')]) == 60 and 'more line(s)' in o)
c, o = run('dup', '--refs')
ok('cap: refs capped', 'more reference line(s)' in o and len(o.splitlines()) < 100)
c, o = run('dup', '--body')
ok('cap: body capped', len(o.splitlines()) <= 90 and 'more match(es)' in o)
put('big.js', 'function hugefn() {}\n' + ' ' * (S.MAX_BYTES + 1))
c, o = run('hugefn')
ok('cap: large file skipped and said so', c == 1 and '1 file(s) over 1 MB skipped' in o)
wide = 'class A {\n  x "' + 'a' * 200000 + '" y\n  ' + ' ' * 200000 + '+\n  go() {}\n}\n'
t0 = time.time()
ok('ts: long blank runs stay fast', 'A/go' in paths(S.js_tree(wide)) and time.time() - t0 < 5)
put('bin/rb', '#!/usr/local/share/ruby\ndeploy\n')
ok('lang: shebang interpreter, not substring', S.lang_of(os.path.join(T, 'bin/rb')) is None
   and S.lang_of(os.path.join(T, 'bin/tool')) == 'py')
done()
