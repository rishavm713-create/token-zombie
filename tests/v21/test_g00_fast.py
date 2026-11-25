# tz fast (bin/tzfast.py): profile a workload, record real calls, prove or reject a rewrite.
import os, sys, json, subprocess, tempfile, textwrap
from harness import ok, done, Z
import tzfast

TOOL = os.path.join(Z, 'bin', 'tzfast.py')


def run(cwd, *args):
    r = subprocess.run([sys.executable, TOOL] + list(args), cwd=cwd, capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout + r.stderr


def write(cwd, name, text):
    with open(os.path.join(cwd, name), 'w') as f:
        f.write(textwrap.dedent(text))


# values: exact types round-trip, subclasses and look-alikes are not flattened
for v in (None, True, 3, 1.5, float('inf'), 'é', b'\x00', bytearray(b'a'), [1, (2,)], {1: {2}}, frozenset([1])):
    ok('roundtrip %r' % (v,), tzfast.same(v, tzfast.dec(json.loads(json.dumps(tzfast.enc(v))))))
ok('nan same', tzfast.same(float('nan'), tzfast.dec(tzfast.enc(float('nan')))))
ok('types differ', not tzfast.same(1, True) and not tzfast.same([1], (1,)) and not tzfast.same({1}, {True}))
ok('dict key type differs', not tzfast.same({1: 'a'}, {True: 'a'}))
try:
    tzfast.enc(type('S', (str,), {})('x'))
    ok('subclass unsupported', False)
except tzfast.Unsupported:
    ok('subclass unsupported', True)
try:
    tzfast.dec({'$obj': ['subprocess', 'Popen', []]})
    ok('edited recording cannot call arbitrary class', False)
except ValueError:
    ok('edited recording cannot call arbitrary class', True)

with tempfile.TemporaryDirectory() as d:
    d = os.path.realpath(d)
    good = '''
        def total(xs):
            out = 0
            for _ in range(40):
                out = 0
                for x in xs:
                    out += x
            return out
        '''
    write(d, 'hot.py', good + '''
        def logged(x):
            print(x)
            return x

        def wraps(x):
            return logged(x)
        ''')
    write(d, 'app.py', '''
        import hot

        def local():
            return [hot.total(list(range(n, n + 300))) for n in range(150)]

        print(sum(local()))
        hot.wraps(1)
        ''')

    # static check: effects propagate to callers
    infos = {i['name']: i for i in tzfast.analyse(os.path.join(d, 'hot.py')).values()}
    ok('pure has no blockers', infos['total']['blockers'] == [])
    ok('io blocked', any('does I/O' in b for b in infos['logged']['blockers']))
    ok('io inherited', any('calls logged' in b for b in infos['wraps']['blockers']))

    # profile
    code, out = run(d, 'scan', '--', 'app.py')
    line = {ln.split()[-2] if ln.endswith('CANDIDATE') else ln: ln for ln in out.splitlines()}
    ok('scan exit 0', code == 0 and 'run:' in out)
    ok('scan candidate', 'hot.py:total' in line)
    ok('scan skips entry script', any('app.py:local' in l and 'entry script' in l for l in out.splitlines()))
    code, out = run(d, 'scan', '--', os.path.basename(sys.executable), 'app.py')
    ok('scan accepts interpreter prefix', code == 0 and 'hot.py:total' in out)
    write(d, 'bad.py', 'raise SystemExit(4)\n')
    code, out = run(d, 'scan', '--', 'bad.py')
    ok('scan fails on failing app', code == 1 and 'exited with 4' in out)

    # record
    code, out = run(d, 'record', 'hot.py:logged', '--', 'app.py')
    ok('record refuses unsafe', code == 2 and 'not safe to replay' in out)
    code, out = run(d, 'record', 'hot.py:logged', '--force', '--', 'app.py')
    ok('force records without edges', code == 0 and '+ 0 derived' in out)
    code, out = run(d, 'record', 'hot.py:total', '--limit', '20', '--', 'app.py')
    ok('record ok', code == 0 and 'recorded 20 of 150 calls' in out)
    folder = os.path.join(d, '.tzfast', 'hot.total')
    with open(os.path.join(folder, 'meta.json')) as f:
        meta = json.load(f)
    with open(os.path.join(folder, 'calls.jsonl')) as f:
        cases = [json.loads(x) for x in f]
    ok('meta count', meta['recorded'] == 20 and meta['original_ns'] > 0)
    ok('derived edges', len(cases) > 20 and all(c.get('derived') for c in cases[20:]))
    ok('empty edge derived', any(c['in'] == [[[]], {}] for c in cases[20:]))
    with open(os.path.join(d, '.tzfast', '.gitignore')) as f:
        ok('recordings ignored by git', f.read() == '*\n')

    # prove: separate candidate file
    write(d, 'fast.py', 'def total(xs):\n    return sum(xs)\n')
    code, out = run(d, 'verify', 'hot.total', 'fast.py:total')
    ok('equivalent faster accepted', code == 0 and out.rstrip().endswith('PASS'))
    ok('all identical', '%d/%d calls identical' % (len(cases), len(cases)) in out)
    # wrong only on an input the app never sent: the derived edge cases must catch it
    write(d, 'wrong.py', 'def total(xs):\n    return sum(xs) if xs else None\n')
    code, out = run(d, 'verify', 'hot.total', 'wrong.py:total')
    ok('non-equivalent rejected', code == 1 and 'FAIL: do not keep' in out and 'expected 0' in out)
    write(d, 'float.py', 'def total(xs):\n    return float(sum(xs))\n')
    code, out = run(d, 'verify', 'hot.total', 'float.py:total', '--any-speed')
    ok('type change rejected', code == 1)
    write(d, 'mutate.py', 'def total(xs):\n    r = sum(xs)\n    xs.append(1)\n    return r\n')
    code, out = run(d, 'verify', 'hot.total', 'mutate.py:total', '--any-speed')
    ok('argument mutation rejected', code == 1 and 'arguments left as' in out)
    write(d, 'exits.py', 'def total(xs):\n    raise SystemExit(0)\n')
    code, out = run(d, 'verify', 'hot.total', 'exits.py:total')
    ok('candidate SystemExit rejected', code == 1 and 'raised SystemExit' in out)
    write(d, 'slow.py', 'import time\ndef total(xs):\n    time.sleep(0.005)\n    return sum(xs)\n')
    code, out = run(d, 'verify', 'hot.total', 'slow.py:total')
    ok('slower is exit 3', code == 3 and 'NOT faster' in out)
    code, out = run(d, 'verify', 'hot.total', 'slow.py:total', '--any-speed')
    ok('any-speed accepts slower', code == 0)

    # prove: in-place rewrite, same size, right after the original (no stale bytecode)
    write(d, 'hot.py', 'def total(xs):\n    return sum(xs) + 1\n')
    code, out = run(d, 'verify', 'hot.total')
    ok('in-place wrong rejected', code == 1)
    write(d, 'hot.py', 'def total(xs):\n    return sum(xs)\n')
    code, out = run(d, 'verify', 'hot.total')
    ok('in-place right accepted', code == 0)

    # tamper, missing
    with open(os.path.join(folder, 'calls.jsonl'), 'a') as f:
        f.write('\n')
    code, out = run(d, 'verify', 'hot.total')
    ok('edited recording fails', code == 1 and 'edited' in out)
    ok('missing recording', run(d, 'verify', 'nope')[0] == 2)

    # recorded exceptions and dataclass values must be reproduced
    write(d, 'rec.py', '''
        from dataclasses import dataclass

        @dataclass
        class P:
            x: int

        class K:
            @staticmethod
            def half(p):
                if p.x % 2:
                    raise ValueError('odd')
                return P(p.x // 2)
        ''')
    write(d, 'app2.py', '''
        from rec import P, K
        for n in range(6):
            try:
                K.half(P(n))
            except ValueError:
                pass
        ''')
    code, out = run(d, 'record', 'rec.py:K.staticmethod_missing', '--', 'app2.py')
    ok('unknown function', code == 2 and 'no function' in out)
    code, out = run(d, 'record', 'rec.py:K.half', '--', 'app2.py')
    ok('record staticmethod', code == 0 and 'recorded 6 of 6' in out)
    code, out = run(d, 'verify', 'rec.K.half', '--any-speed')
    ok('exceptions and dataclass replay', code == 0)
    write(d, 'swallow.py', 'from rec import P\ndef half(p):\n    return P(p.x // 2)\n')
    code, out = run(d, 'verify', 'rec.K.half', 'swallow.py:half', '--any-speed')
    ok('lost exception rejected', code == 1 and 'raises ValueError' in out)

    # bench
    code, out = run(d, 'bench', '--runs', '2', '--vs', '"%s" -c "print(1)"' % sys.executable,
                    '--', sys.executable, '-c', 'print(1)')
    ok('bench identical', code == 0 and 'output: identical' in out and 'speedup' in out)
    code, out = run(d, 'bench', '--runs', '1', '--vs', '"%s" -c "print(2)"' % sys.executable,
                    '--', sys.executable, '-c', 'print(1)')
    ok('bench differs', code == 1 and 'DIFFERS, line 1' in out)
    code, out = run(d, 'bench', '--runs', '1', '--', sys.executable, '-c', 'raise SystemExit(3)')
    ok('bench failing command', code != 0 and 'failed (3)' in out)

done()
