# tztbench (terminal-bench, Apache-2.0): task load, pytest parse, resolve rule, pass@k.
import os, tempfile
from harness import ok, done
import tztbench as B
d = tempfile.mkdtemp()
open(os.path.join(d, 'task.yaml'), 'w').write('instruction: |-\n  do x\ndifficulty: easy\n')
t = B.load_task(d)
ok('load', t['instruction'] == 'do x' and t['difficulty'] == 'easy')
open(os.path.join(d, 'task.yaml'), 'w').write('difficulty: easy\n')
try: B.load_task(d); bad = False
except ValueError: bad = True
ok('missing instruction refused', bad)
r = B.parse_pytest('== short test summary info ==\nPASSED t.py::a\nFAILED t.py::b - x\n')
ok('parse', r == {'a': 'passed', 'b': 'failed'})
ok('resolved', B.is_resolved({'a': 'passed'}) and not B.is_resolved(r) and not B.is_resolved({}))
rows = [dict(task_id='t', is_resolved=v) for v in (1, 0)]
ok('pass@2', B.pass_at_k(rows) == {2: 1.0})
done()
