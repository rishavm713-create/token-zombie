# Repo intel: tzrank budget/mention/methods, tzfind2 BM25 find, tzops.impact_diff.
import os, subprocess, tempfile
from harness import ok, done, Z
import tzrank, tzmap, tzfind2, tzops

# budget parity from docs/research/B-repo-intel.md: 100 tags x 40 chars, budget 250 -> 26 tags
items = [f'{i:039d}' for i in range(100)]
text, n, t = tzrank.fit_budget(items, 250, lambda ts: ''.join(x + '\n' for x in ts))
ok('budget 26 tags within 15%', n == 26 and abs(t - 250) / 250 < 0.15)
ok('budget empty list', tzrank.fit_budget([], 100, lambda ts: '')[1] == 0)

T = tempfile.mkdtemp()
def w(rel, s):
    p = os.path.join(T, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'w').write(s)
w('lib/core.py', 'class MyClass:\n    def my_method(self):\n        return 1\n\ndef my_function():\n    return 2\n')
w('lib/user.py', 'from core import MyClass\nx = MyClass().my_method()\ny = my_function()\nz = my_method\n')
w('lib/other.py', 'def solo_helper_unused():\n    return 3\n')
w('notes.py', 'VALUE = 1\n')
ok('defs_methods adds methods', 'MyClass.my_method' in tzmap.defs_methods(T + '/lib/core.py'))
ok('defs unchanged', tzmap.defs(T + '/lib/core.py') == ['class MyClass', 'my_function'])
base = tzrank.ranked(T)
ok('default ranking has no methods', all('.' not in i for _, _, i in base))
rm = tzrank.ranked(T, methods=True)
ok('methods ranked as Class.method', any(i == 'MyClass.my_method' for _, _, i in rm))
rs = tzrank.ranked(T, (), {'solo_helper_unused'}, set(), tagless=True)
ok('tagless file appended last', rs[-1][1] == 'notes.py' and rs[-1][2] == '')
a = tzrank.ranked(T, ())
ok('mentioned file seeds personalization', tzrank.ranked(T, (), (), {'lib/other.py'})[0][1] == 'lib/other.py' and a[0][1] == 'lib/core.py')
idents, files = tzrank.extract_mentions('change lib/other.py and my_function', T)
ok('extract mentions', 'my_function' in idents and files == {'lib/other.py'})
sa = {i: v for v, f, i in a}; sb = {i: v for v, f, i in tzrank.ranked(T, (), {'MyClass'})}
ok('mentioned ident boosted x10 edge', sb['MyClass'] / sum(sb.values()) > sa['MyClass'] / sum(sa.values()))
r = subprocess.run(['python3', os.path.join(Z, 'bin', 'tzrank.py'), '--tokens', '60', '--mention', 'my_function', T], capture_output=True, text=True)
ok('cli --tokens prints budget line', 'tag(s)' in r.stdout and 'lib/core.py' in r.stdout)

# find: path + definition + text head
w('bin/billing_report.py', 'def make_invoice_total():\n    pass\n')
w('docs/readme.md', 'unrelated words about gardening\n')
fs = tzfind2.find(T, 'fix invoice total in billing report', 5)
ok('find ranks billing file first', fs and fs[0][1] == 'bin/billing_report.py')
ok('find no match -> empty', tzfind2.find(T, 'zzzqqq', 5) == [])
ok('toks splits camel and snake', {'invoice', 'total', 'invoicetotal'} <= set(tzfind2.toks('InvoiceTotal')))

# impact --diff in a scratch git repo
G = tempfile.mkdtemp()
def g(*a): return subprocess.run(['git', '-C', G] + list(a), capture_output=True, text=True).stdout
g('init', '-q'); g('config', 'user.email', 'a@b.c'); g('config', 'user.name', 'a')
open(G + '/lib.py', 'w').write('def compute_total(x):\n    return x\n\ndef other_thing():\n    return 0\n')
open(G + '/app.py', 'w').write('from lib import compute_total\ndef run_app():\n    return compute_total(1)\n')
open(G + '/main_cli.py', 'w').write('from app import run_app\nrun_app()\n')
os.makedirs(G + '/tests'); open(G + '/tests/test_lib.py', 'w').write('from lib import compute_total\nassert compute_total(1) == 1\n')
g('add', '.'); g('commit', '-qm', 'init')
ok('no diff -> NONE', tzops.impact_diff(G)['grade'] == 'NONE')
open(G + '/lib.py', 'w').write('def compute_total(x):\n    return x + 1\n\ndef other_thing():\n    return 0\n')
d = tzops.impact_diff(G)
ok('changed symbol found', [s['symbol'] for s in d['symbols']] == ['compute_total'])
ok('depth 1 users', d['symbols'][0]['d1'] == ['app.py', 'tests/test_lib.py'])
ok('depth 2 users', d['symbols'][0]['d2'] == ['main_cli.py'])
ok('tests listed', d['tests'] == ['tests/test_lib.py'])
ok('grade MEDIUM', d['grade'] == 'MEDIUM' and d['lines'][0].startswith('impact --diff: MEDIUM'))
done()
