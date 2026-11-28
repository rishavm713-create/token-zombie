# tzout re-read stub (idea from lean-ctx, Apache-2.0): unchanged big file re-read in one session -> stub.
import os, tempfile
H = tempfile.mkdtemp(); os.environ['HOME'] = H
for k in [k for k in os.environ if k.startswith('TZ_')]:
    del os.environ[k]
from harness import ok, done
import tzout as O
O.STATE = tempfile.mkdtemp()
big = 'line of text\n' * 300
ok('first read: no stub', O._reread('s1', '/f.py', big) == '')
st = O._reread('s1', '/f.py', big)
ok('same bytes again: stub', 'unchanged' in st and len(st) < len(big))
ok('changed content: no stub', O._reread('s1', '/f.py', big + 'x') == '')
ok('other session: no stub', O._reread('s2', '/f.py', big) == '')
ok('small file never stubbed', O._reread('s1', '/g.py', 'tiny') == '' and O._reread('s1', '/g.py', 'tiny') == '')
# tz read modes
import contextlib, io
import tzread as R
D = tempfile.mkdtemp()
def put(name, text):
    p = os.path.join(D, name); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w', newline='').write(text); return p
def run(*a):
    o = io.StringIO()
    with contextlib.redirect_stdout(o):
        rc = R.main(list(a))
    return rc, o.getvalue()
src = 'import os\nfrom sys import (\n    argv,\n)\nX = 1\n\ndef alpha(a):\n    """Doc."""\n    return a + 12345\n\nclass Beta:\n    def gamma(self):\n        return "needle_word"\n' + ''.join(f'v{i} = {i}\n' for i in range(40))
f = put('m.py', src)
ok('diff without state: full + reason', run(f, 'diff')[1].endswith(src) and 'no earlier' in run(put('n.py', src), 'diff')[1])
ok('full: exact bytes', run(f, 'full') == (0, src))
ok('crlf kept', run(put('c.txt', 'a\r\nb'), 'full')[1] == 'a\r\nb')
o = run(f, 'signatures')[1]
ok('signatures: body cut and said', 'def alpha(a)' in o and '12345' not in o and 'bodies omitted' in o)
o = run(f, 'map')[1]
ok('map: imports + top-level with numbers', 'L1: import os' in o and 'L3:     argv,' in o and 'L7: def alpha' in o and 'L11: class Beta' in o and 'gamma' not in o and 'omitted' in o)
o = run(put('m.js', "import a from 'a';\nfunction top() {\n  function inner() {}\n}\n"), 'map')[1]
ok('map js', 'L1: import' in o and 'L2: function top' in o and 'inner' not in o)
run(f, 'full')
ok('diff unchanged says omitted', 'unchanged' in run(f, 'diff')[1])
put('m.py', src.replace('X = 1', 'X = 2'))
o = run(f, 'diff')[1]
ok('diff shows change', '-X = 1' in o and '+X = 2' in o and 'v39' not in o)
o = run(f, 'lines', '7-9')[1]
ok('lines: slice + omitted', 'def alpha' in o and 'import os' not in o and 'omitted: 1-6, 10-53' in o)
ok('bad range: full', 'import os' in run(f, 'lines', '900-999')[1] and 'v39 = 39' in run(f, 'lines', '9-2')[1])
o = run(f, 'task', 'find needle_word')[1]
ok('task: window + omitted ranges', 'L13:' in o and '[omitted lines 1-7]' in o and '[omitted lines 19-53]' in o)
o = run(f, 'task', 'zzzzqq')[1]
ok('task no match: full', 'no line matches' in o and 'v39 = 39' in o)
ok('auto small: full, no header', run(f)[1] == open(f).read())
big_py = put('big.py', 'def f():\n' + '    y = 1\n' * 1500)
ok('auto big: signatures', 'bodies omitted' in run(big_py)[1])
bad = 'def (:\n' * 2000
o = run(put('bad.py', bad), 'auto')[1]
ok('unparseable: fail open', 'full text follows' in o and o.endswith(bad))
ok('map unparseable: fail open', run(os.path.join(D, 'bad.py'), 'map')[1].endswith(bad))
for n in ('.env', 'my dir/.env', 'my dir/k.pem', 'U.PEM', os.path.join(H, '.ssh', 'my key')):
    p = put(n, 'TOPSECRET')
    rc, o = run(p, 'full')
    ok('secret refused ' + n, rc == 2 and 'TOPSECRET' not in o and not os.path.exists(R._snap(p)))
os.symlink(os.path.join(D, '.env'), os.path.join(D, 'link.txt'))
ok('symlink to secret refused', run(os.path.join(D, 'link.txt'))[0] == 2)
# shortcut: Windows has no POSIX mode bits, so owner-only is checked on POSIX only
ok('state under HOME, owner-only', R._snap(f).replace('\\', '/').startswith(H.replace('\\', '/') + '/.claude/token-zombie/') and (os.name == 'nt' or os.stat(R._snap(f)).st_mode & 0o77 == 0))
ok('missing file / bad mode', run(f + '.no')[0] == 1 and run(f, 'nope')[0] == 2 and run(f, 'lines')[0] == 2)
done()
