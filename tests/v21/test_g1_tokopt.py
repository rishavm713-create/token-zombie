# Delta re-read (bin/tztokopt.py). Pure logic; temp HOME only, no network.
import os, tempfile, io, contextlib, stat
from harness import ok, done, Z

H = tempfile.mkdtemp()
os.environ['HOME'] = H
import tztokopt as T

F = os.path.join(H, 'a.py')
BASE = ['value_%03d = %d  # filler text' % (i, i) for i in range(200)]


def write(lines, p=F):
    with open(p, 'w') as f:
        f.write('\n'.join(lines) + '\n')


def pay(p=F, sid='s1', tool='Read', **ti):
    return dict(session_id=sid, tool_name=tool, tool_input=dict(file_path=p, **ti))


write(BASE)
ok('first read allowed', T.delta(pay()) is None)
ok('remember stores', T.remember(pay()))
ok('snapshot is private', stat.S_IMODE(os.stat(T._path('s1')).st_mode) == 0o600)
ok('unchanged left to other guards', T.delta(pay()) is None)
new = list(BASE)
for i in (5, 90, 180):
    new[i] = 'changed_%d = True' % i
write(new)
ok('other session unaffected', T.delta(pay(sid='s2')) is None)
ok('offset read allowed', T.delta(pay(offset=10)) is None)
ok('limit read allowed', T.delta(pay(limit=10)) is None)
ok('subagent allowed', T.delta(dict(pay(), agent_id='x')) is None)
ok('other tool ignored', T.delta(pay(tool='Edit')) is None)
r = T.delta(pay()) or ''
ok('3 changes give 3 hunks', sum(l.startswith('@@') for l in r.splitlines()) == 3)
ok('has new line', '+changed_90 = True' in r)
ok('unchanged lines left out', 'value_050' not in r)
ok('says how to get all', 'same Read again' in r)
ok('smaller than file', len(r) < os.path.getsize(F) / 2)
ok('repeat goes through', T.delta(pay()) is None)

write(['rewritten_%03d = None  # other' % i for i in range(200)])
ok('rewrite allows full read', T.delta(pay()) is None)

T.remember(pay())
write(['rewritten_%03d = None  # other' % i for i in range(199)])
ok('reset', T.reset('s1'))
ok('after reset allowed', T.delta(pay()) is None)

small = os.path.join(H, 'small.py')
write(['a = 1'], small)
ok('small not stored', not T.remember(pay(small)))
for name in ('.env', 'secrets.yaml', 'server.pem', 'id_rsa'):
    p = os.path.join(H, name)
    write(BASE, p)
    ok('secret not stored ' + name, not T.remember(pay(p)))
big = os.path.join(H, 'big.py')
write(BASE * 5, big)
ok('big not stored', not T.remember(pay(big)))
b = os.path.join(H, 'bin.dat')
with open(b, 'wb') as f:
    f.write(b'\xff\xfe' * 2000)
ok('binary not stored', not T.remember(pay(b)))
ok('partial read not stored', not T.remember(pay(offset=1)))

write(BASE)
T.remember(pay())
write(BASE * 5)
ok('grown past cap allowed', T.delta(pay()) is None)
write(BASE)
T.remember(pay())
os.remove(F)
ok('deleted file allowed', T.delta(pay()) is None)
ok('relative path ignored', T.delta(pay('a.py')) is None)
ok('empty payload', T.delta({}) is None)

for i in range(T.KEEP + 5):
    p = os.path.join(H, 'f%d.py' % i)
    write(BASE, p)
    T.remember(pay(p, sid='cap'))
ok('snapshots capped', len(T._load('cap')) == T.KEEP)

o, n = os.path.join(H, 'o'), os.path.join(H, 'n')
write(BASE, o)
write(new, n)
buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
    codes = [T.main(['diff', o, n]), T.main([]), T.main(['diff', o, o + 'missing'])]
ok('cli exit codes', codes == [0, 2, 2])
ok('cli diff output', '+changed_5 = True' in buf.getvalue())
done()
