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
done()
