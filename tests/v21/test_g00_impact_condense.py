# repomap impact + OpenHands/mini-swe condenser ports (idea-only, independent code).
import os, subprocess, sys, tempfile
from harness import ok, done, Z
sys.path.insert(0, os.path.join(Z, 'bin'))
import tzimpact, tzcondense

T = tempfile.mkdtemp()
def w(rel, s):
    p = os.path.join(T, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'w').write(s)
w('a.py', 'def core():\n    return 1\n')
w('b.py', 'from a import core\ndef mid():\n    return core()\n')
w('c.py', 'from b import mid\nclass K:\n    def top(self):\n        return mid()\n')
w('tests/test_c.py', 'from c import K\ndef test_it():\n    K().top()\n')
r = tzimpact.impact(T, 'core')
ok('depth 1 caller', ('b.py', 'mid') in r['callers'][0])
ok('depth 2 caller', ('c.py', 'K.top') in r['callers'][1])
ok('depth 3 test fn', ('tests/test_c.py', 'test_it') in r['callers'][2])
ok('tests listed', r['tests'] == ['tests/test_c.py'])
ok('low risk small', r['risk'] == 'LOW')
ok('depth limit', len(tzimpact.impact(T, 'core', 1)['callers']) == 1)
ok('unknown symbol', tzimpact.impact(T, 'nope')['count'] == 0)
for i in range(20):
    w('m%d.py' % i, 'def f%d():\n    return core()\n' % i)
ok('high risk', tzimpact.impact(T, 'core')['risk'] == 'HIGH')
o = subprocess.run([sys.executable, os.path.join(Z, 'bin', 'tzimpact.py'), 'core'], cwd=T, capture_output=True, text=True)
ok('cli output', 'tests to run: tests/test_c.py' in o.stdout and o.returncode == 0)

ev = [{'role': 'user', 'text': 'U' * 5000}] + [{'role': 'tool', 'text': 'x' * 3000} for _ in range(30)] + [{'role': 'tool', 'text': 'short'}]
new, saved = tzcondense.condense(ev, 2, 5)
ok('first kept', new[1]['text'] == 'x' * 3000)
ok('user never masked', new[0]['text'] == 'U' * 5000)
ok('middle masked', new[10]['text'] == '[tz: 3000 chars of old tool output elided]')
ok('last kept', all(e['text'] == 'x' * 3000 for e in new[-5:-1]) and new[-1]['text'] == 'short')
ok('saved count', saved == sum(3000 - len(new[i]['text']) for i in range(2, 27)))
ok('input untouched', ev[10]['text'] == 'x' * 3000)
ok('short middle kept', tzcondense.condense([{'role': 't', 'text': 'a'}] * 40, 1, 1)[1] == 0)
c = tzcondense.cut('a' * 100 + 'b' * 9000 + 'c' * 100, 100, 100)
ok('cut head/tail', c.startswith('a' * 100) and c.endswith('c' * 100) and '9000 chars elided' in c)
ok('cut short unchanged', tzcondense.cut('hi') == 'hi')
import json
f = os.path.join(T, 'h.jsonl'); open(f, 'w').write('\n'.join(json.dumps(e) for e in ev))
o = subprocess.run([sys.executable, os.path.join(Z, 'bin', 'tzcondense.py'), f, '--keep-last', '5'], capture_output=True, text=True)
ok('cli stats', o.returncode == 0 and 'saves' in o.stdout)
done()
