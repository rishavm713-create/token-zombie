# tzdiag: post-edit diagnostics (idea from Continuous-Claude-v3, MIT).
import os, tempfile
from harness import ok, done
import tzdiag as D
d = tempfile.mkdtemp()
def w(n, s):
    p = os.path.join(d, n); open(p, 'w').write(s); return p
ok('py ok', D.check(w('a.py', 'x = 1\n')) == '')
ok('py bad', 'line 1' in D.check(w('b.py', 'def (:\n')))
ok('json ok', D.check(w('a.json', '{"a": 1}')) == '')
ok('json bad', D.check(w('b.json', '{a')) != '')
ok('sh bad', D.check(w('b.sh', 'if then\n')) != '')
ok('unknown passes', D.check(w('a.txt', '((')) == '')
ok('missing file', D.check(os.path.join(d, 'nope.py')) != '')
ok('main codes', D.main([os.path.join(d, 'a.py')]) == 0 and D.main([os.path.join(d, 'b.py')]) == 1)
done()
