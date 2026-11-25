# Tiny check harness for v2.1 integration tests: ok(name, cond); done() prints "pass N fail M" (run_all.sh parses it).
import os, sys, json, subprocess, tempfile
Z = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(Z, 'bin'))
P = [0, 0]


def ok(name, cond):
    if cond:
        P[0] += 1
    else:
        P[1] += 1
        print('FAIL:', name)


def done():
    print(f'pass {P[0]} fail {P[1]}')
    sys.exit(1 if P[1] else 0)


def guard(payload, env=None, home=None):
    """Run the single hook dispatcher once; returns (parsed stdout json or {}, ms)."""
    import time
    e = dict(os.environ, **(env or {}))
    if home:
        e['HOME'] = home
    t = time.perf_counter()
    r = subprocess.run([sys.executable, os.path.join(Z, 'bin', 'tz-guard.py')], input=json.dumps(payload),
                       capture_output=True, text=True, env=e, timeout=30)
    ms = (time.perf_counter() - t) * 1000
    try:
        return json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {}, ms
    except Exception:
        return {'_raw': r.stdout}, ms
