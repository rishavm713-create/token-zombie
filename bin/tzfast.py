#!/usr/bin/env python3
"""`tz fast`: profile the real workload, record a hot function's real calls, prove a rewrite behaves the same."""
# adapted from EL4CTEO/fast-anything src/python/runner.py, src/hotspot.rs, src/bench.rs
# (MIT, Copyright (c) 2025 Juan Peláez / 23blocks), see NOTICE. Python to Python only; no Rust toolchain.
import argparse, ast, base64, cProfile, dataclasses, hashlib, importlib, importlib.util, json, math, os, pstats
import random, re, runpy, shlex, shutil, signal, statistics, subprocess, sys, threading, time, _thread

STORE = '.tzfast'
WORTH_IT = 0.02  # a function under 2% of the run cannot make a visible difference
SKIP = {STORE, '.git', 'venv', '.venv', 'env', '.env', 'site-packages', 'dist-packages', 'node_modules',
        '__pycache__', 'build', 'dist', '.tox', '.nox'}
STATE_READS = {'os.environ', 'os.environb', 'sys.argv', 'sys.orig_argv', 'sys.stdin', 'sys.stdout', 'sys.stderr'}
IO_NAMES = {'print', 'open', 'input', 'exec', 'eval', 'compile', '__import__', 'breakpoint', 'exit', 'quit'}
IO_MODULES = set('os sys subprocess socket requests urllib http httpx aiohttp shutil pathlib logging sqlite3 '
                 'tempfile glob asyncio threading multiprocessing io'.split())
NONDET_MODULES = {'random', 'time', 'datetime', 'uuid', 'secrets'}
# Pure callables inside the modules above: they must not block a function.
PURE_CALLS = {'datetime.' + n for n in (
    'date datetime time timedelta timezone date.fromisoformat date.fromordinal date.fromisocalendar '
    'datetime.fromisoformat datetime.strptime datetime.combine time.fromisoformat').split()}
PURE_CALLS |= {'os.path.' + n for n in
               'join basename dirname split splitext normpath normcase isabs commonpath commonprefix'.split()}
PURE_CALLS |= set('io.StringIO io.BytesIO pathlib.PurePath pathlib.PurePosixPath pathlib.PureWindowsPath os.fspath '
                  'os.fsdecode os.fsencode uuid.UUID uuid.uuid3 uuid.uuid5 http.HTTPStatus http.HTTPMethod '
                  'secrets.compare_digest glob.escape glob.has_magic'.split())
EFFECTS = ('does I/O', 'not deterministic', 'writes global state')  # a caller inherits these from its helpers
NON_ASCII = ('é', '日本', '\U0001f44d\U0001f3fd', 'é')
SLICES = (0, 1, 2, 3, 5, 8, 13, 21, 34, 55)
PYTHON = re.compile(r'(python|pypy|py)[0-9.]*(\.exe)?$', re.I)  # an interpreter's file name


class Unsupported(Exception):
    """A value that cannot be recorded as plain data."""


# ------------------------------------------------------------------ values

def record_fields(v):
    """Field names of a dataclass or NamedTuple instance, None for anything else."""
    if isinstance(v, tuple) and isinstance(getattr(type(v), '_fields', None), tuple):
        return list(type(v)._fields)
    if dataclasses.is_dataclass(v) and not isinstance(v, type):
        return [f.name for f in dataclasses.fields(v)]
    return None


def enc(v):
    """A value as tagged JSON; exact types only, so a subclass is never silently flattened."""
    t = type(v)
    if v is None or t in (bool, int, str):
        return v
    if t is float:
        return v if math.isfinite(v) else {'$float': repr(v)}
    if t is list:
        return [enc(x) for x in v]
    if t in (bytes, bytearray):
        return {'$' + t.__name__: base64.b64encode(bytes(v)).decode('ascii')}
    if t is dict:
        return {'$dict': [[enc(k), enc(x)] for k, x in v.items()]}
    if t in (tuple, set, frozenset):
        return {'$' + t.__name__: [enc(x) for x in v]}
    fields = record_fields(v)
    if fields is not None and t.__module__ != '__main__' and '<locals>' not in t.__qualname__:
        return {'$obj': [t.__module__, t.__qualname__, [[f, enc(getattr(v, f))] for f in fields]]}
    raise Unsupported(t.__name__)


def dec(v):
    """Inverse of enc; every call builds fresh objects."""
    if isinstance(v, list):
        return [dec(x) for x in v]
    if not isinstance(v, dict):
        return v
    ((tag, x),) = v.items()
    if tag == '$float':
        return float(x)
    if tag in ('$bytes', '$bytearray'):
        raw = base64.b64decode(x)
        return raw if tag == '$bytes' else bytearray(raw)
    if tag == '$dict':
        return {dec(k): dec(i) for k, i in x}
    if tag in ('$tuple', '$set', '$frozenset'):
        return {'$tuple': tuple, '$set': set, '$frozenset': frozenset}[tag](dec(i) for i in x)
    if tag != '$obj':
        raise ValueError('unknown tag ' + tag)
    module, qualname, fields = x
    cls = importlib.import_module(module)
    for part in qualname.split('.'):
        cls = getattr(cls, part)
    # WHY: an edited recording must not be able to call any importable function.
    if not (isinstance(cls, type) and (dataclasses.is_dataclass(cls) or hasattr(cls, '_fields'))):
        raise ValueError('not a record class: ' + qualname)
    values = {k: dec(i) for k, i in fields}
    try:
        return cls(**values)
    except TypeError:  # fields left out of __init__
        obj = cls.__new__(cls)
        for k, i in values.items():
            object.__setattr__(obj, k, i)
        return obj


def same(a, b):
    """Equal as a caller sees it: same types all the way down, floats within 1e-9."""
    if type(a) is not type(b):
        return False
    if isinstance(a, float):
        if math.isnan(a) or math.isnan(b):
            return math.isnan(a) and math.isnan(b)
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
    if isinstance(a, (set, frozenset)):
        return a == b and sorted(map(repr, a)) == sorted(map(repr, b))
    fields = record_fields(a)
    if fields is not None:
        return all(same(getattr(a, f), getattr(b, f)) for f in fields)
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(map(same, a, b))
    if isinstance(a, dict):
        return {(type(k), k) for k in a} == {(type(k), k) for k in b} and all(same(a[k], b[k]) for k in a)
    return a == b


def show(v, limit=100):
    """Short repr for a failure line."""
    text = repr(v)
    return text if len(text) <= limit else text[:limit - 3] + '...'


def pack(args, kwargs):
    """Arguments as one JSON value."""
    return [[enc(a) for a in args], {k: enc(v) for k, v in kwargs.items()}]


def unpack(p):
    """Fresh (args, kwargs) from a packed value."""
    return [dec(a) for a in p[0]], {k: dec(v) for k, v in p[1].items()}


# ------------------------------------------------------------------ static check

def dotted(node):
    """['a', 'b'] for the expression a.b, else None."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    return [node.id] + parts[::-1] if isinstance(node, ast.Name) else None


def imports(nodes):
    """local name -> dotted origin for the import statements among `nodes`."""
    out = {}
    for n in nodes:
        if isinstance(n, ast.Import):
            for a in n.names:
                out[a.asname or a.name.split('.')[0]] = a.name if a.asname else a.name.split('.')[0]
        elif isinstance(n, ast.ImportFrom) and not n.level:
            for a in n.names:
                out[a.asname or a.name] = n.module + '.' + a.name
    return out


def effect(full):
    """Why a resolved dotted name makes a function unsafe to replay, or None."""
    name, head = '.'.join(full), full[0]
    if len(full) < 2 or name in PURE_CALLS or name.startswith('urllib.parse.'):
        return None
    if head in IO_MODULES:
        return 'does I/O: ' + name
    if head in NONDET_MODULES or (head in ('numpy', 'pandas', 'torch') and full[1] == 'random'):
        return 'not deterministic: ' + name
    return None


def inspect_function(node, module_imports, top):
    """(blockers, names of same-file functions called) for one function node."""
    inner = list(ast.walk(node))
    local = {n.arg for n in inner if isinstance(n, ast.arg)}
    local |= {n.id for n in inner if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    names = dict(module_imports, **imports(inner))
    blockers, calls = [], set()
    if isinstance(node, ast.AsyncFunctionDef):
        blockers.append('async')
    if any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in inner):
        blockers.append('generator (yield)')
    if any(isinstance(n, (ast.Global, ast.Nonlocal)) for n in inner):
        blockers.append('writes global state')
    for sub in inner:
        if isinstance(sub, (ast.Attribute, ast.Name)):
            read = dotted(sub)
            if read and read[0] in names and read[0] not in local:
                full = '.'.join([names[read[0]]] + read[1:])
                if full in STATE_READS:
                    blockers.append('does I/O: ' + full)
        if not isinstance(sub, ast.Call):
            continue
        target = dotted(sub.func)
        if not target or target[0] in local:
            continue
        if target[0] in names:
            why = effect(names[target[0]].split('.') + target[1:])
            if why:
                blockers.append(why)
        elif len(target) == 1 and target[0] in top:
            calls.add(target[0])
        elif len(target) == 1 and target[0] in IO_NAMES:
            blockers.append('does I/O: ' + target[0])
    return blockers, calls - {node.name}


def analyse(path):
    """first line -> {name, qualname, blockers, calls} for every function in a file (name-based check)."""
    try:
        with open(path, 'rb') as f:
            tree = ast.parse(f.read())
    except (OSError, SyntaxError, ValueError):
        return {}
    funcs = (ast.FunctionDef, ast.AsyncFunctionDef)
    top = {n.name for n in tree.body if isinstance(n, funcs)}
    module_imports = imports(tree.body)
    out = {}

    def visit(body, prefix, kind):
        for n in body:
            if isinstance(n, ast.ClassDef):
                visit(n.body, prefix + n.name + '.', 'method')
            elif isinstance(n, funcs):
                blockers, calls = inspect_function(n, module_imports, top)
                static = any(isinstance(d, ast.Name) and d.id == 'staticmethod' for d in n.decorator_list)
                if kind == 'method' and not static:
                    blockers.insert(0, 'method (only module-level functions and @staticmethods)')
                elif kind == 'nested':
                    blockers.insert(0, 'nested function')
                first = min([n.lineno] + [d.lineno for d in n.decorator_list])
                out[first] = {'name': n.name, 'qualname': prefix + n.name, 'kind': kind,
                              'blockers': blockers, 'calls': calls}
                visit(n.body, prefix + n.name + '.', 'nested')
            else:
                visit([c for c in ast.iter_child_nodes(n) if isinstance(c, (ast.stmt, ast.excepthandler))],
                      prefix, kind)

    visit(tree.body, '', 'function')
    pass_on(out)
    return out


def pass_on(infos):
    """A caller of a same-file helper with an effect gets that blocker too, through any number of helpers."""
    helpers = {i['name']: i for i in infos.values() if i['kind'] == 'function'}
    changed = True
    while changed:
        changed = False
        for info in infos.values():
            if any(b.startswith(EFFECTS) or ', which ' in b for b in info['blockers']):
                continue
            for called in sorted(info['calls']):
                bad = [b for b in helpers[called]['blockers'] if b.startswith(EFFECTS) or ', which ' in b] \
                    if called in helpers else []
                if bad:
                    info['blockers'].append('calls %s, which has: %s' % (called, bad[0].split(', which has: ')[-1]))
                    changed = True
                    break


# ------------------------------------------------------------------ ranking

def rank(rows):
    """Annotate rows {id,file,name,share,blockers,calls} with `why` (None = candidate); best first."""
    covers = [None] * len(rows)
    for i, h in enumerate(rows):
        if h['blockers']:
            continue
        outer = [j for j, g in enumerate(rows) if j != i and not g['blockers'] and g['file'] == h['file']
                 and h['name'] in g['calls'] and g['share'] >= 0.9 * h['share']]
        if outer:
            covers[i] = max(outer, key=lambda j: rows[j]['share'])
    # WHY: functions that call each other would all cover one another; keep the biggest of each ring open.
    for start in range(len(rows)):
        path, at = [], start
        while at is not None and at not in path:
            path.append(at)
            at = covers[at]
        if at is not None:
            ring = path[path.index(at):]
            covers[min(ring, key=lambda j: (-rows[j]['share'], j))] = None
    for h, c in zip(rows, covers):
        h['why'] = h['blockers'][0] if h['blockers'] else \
            'inside %s: change that one' % rows[c]['id'] if c is not None else \
            'too small: %.1f%% of the run, %d%% needed' % (h['share'] * 100, WORTH_IT * 100) \
            if h['share'] < WORTH_IT else None
    return sorted(rows, key=lambda h: (h['why'] is not None, bool(h['blockers']), -h['share']))


# ------------------------------------------------------------------ running the app

def prepare(workload):
    """Make sys.path look like a plain `python ...` run; returns (is_module, target, rest, entry, base)."""
    if not workload or (workload[0] == '-m' and len(workload) < 2) or \
            (workload[0].startswith('-') and workload[0] != '-m'):
        raise SystemExit('tz fast: give the workload after -- as: [python] script.py args | -m module args')
    module = workload[0] == '-m'
    target, rest = (workload[1], workload[2:]) if module else (workload[0], workload[1:])
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path[:] = [p for p in sys.path if os.path.abspath(p or '.') != here]
    base = os.getcwd() if module else os.path.dirname(os.path.abspath(target))
    sys.path.insert(0, base)
    entry = os.path.abspath(target)
    if module:
        spec = importlib.util.find_spec(target)
        if spec is not None and spec.submodule_search_locations:
            spec = importlib.util.find_spec(target + '.__main__')
        entry = os.path.abspath(spec.origin) if spec and spec.origin else ''
    return module, target, rest, entry, base


def interrupt():
    """Ctrl+C for the main thread; a real signal also wakes a blocked server."""
    if hasattr(signal, 'pthread_kill'):
        signal.pthread_kill(threading.main_thread().ident, signal.SIGINT)
    else:
        _thread.interrupt_main()


def run_target(module, target, rest, duration=0):
    """Run the app; after `duration` seconds interrupt it like Ctrl+C (servers). Returns its exit code."""
    sys.argv, fired = [target] + list(rest), []
    timer = threading.Timer(duration, lambda: (fired.append(1), interrupt())) if duration else None
    if timer:
        signal.signal(signal.SIGINT, signal.default_int_handler)  # background shells start with it ignored
        timer.daemon = True
        timer.start()
    try:
        if module:
            runpy.run_module(target, run_name='__main__', alter_sys=True)
        else:
            runpy.run_path(target, run_name='__main__')
    except SystemExit as e:
        return 0 if e.code in (None, 0) else e.code
    except KeyboardInterrupt:
        if not fired:
            raise
    finally:
        if timer:
            timer.cancel()
    return 0


def cmd_scan(opts, workload):
    """Profile the workload and rank this project's functions."""
    module, target, rest, entry, _ = prepare(workload)
    root, prof = os.getcwd(), cProfile.Profile()
    start = time.perf_counter()
    prof.enable()
    try:
        code = run_target(module, target, rest, opts.duration)
    finally:
        prof.disable()
    wall = time.perf_counter() - start
    if code:
        print('tz fast: the app exited with %s; fix the run before measuring' % code)
        return 1
    rows, files = [], {}
    for (path, line, name), (_cc, ncalls, tottime, cumtime, _c) in pstats.Stats(prof).stats.items():
        if name.startswith('<') or path.startswith(('<', '~')):
            continue
        try:
            rel = os.path.relpath(os.path.abspath(path), root)
        except ValueError:  # another Windows drive
            continue
        parts = rel.split(os.sep)
        if parts[0] == os.pardir or SKIP.intersection(parts[:-1]):
            continue
        if path not in files:
            files[path] = analyse(path)
        info = files[path].get(line)
        if not info or info['name'] != name:
            continue
        blockers = list(info['blockers'])
        if os.path.abspath(path) == entry:
            blockers.insert(0, 'lives in the entry script: move it to its own module')
        rel = rel.replace(os.sep, '/')
        rows.append({'id': rel + ':' + info['qualname'], 'file': rel, 'name': name, 'calls': info['calls'],
                     'share': min(cumtime / wall, 1.0) if wall else 0.0, 'blockers': blockers,
                     'ncalls': ncalls, 'tottime': tottime})
    print('run: %.3fs [MEASURED, under cProfile]' % wall)
    for h in rank(rows)[:opts.top]:
        print('%5.1f%% total  %7.3fs self  %8d calls  %s  %s' % (
            h['share'] * 100, h['tottime'], h['ncalls'], h['id'], 'skip: ' + h['why'] if h['why'] else 'CANDIDATE'))
    if not rows:
        print('no project functions seen under ' + root)
    return 0


# ------------------------------------------------------------------ record

class Recorder:
    """Keeps a uniform sample of up to `limit` calls to the wrapped function (reservoir sampling)."""

    def __init__(self, limit):
        self.limit, self.rng = limit, random.Random(0xFA57)
        self.kept, self.calls, self.skipped = [], 0, set()

    def wrap(self, original):
        """The original, observed."""
        def recorder(*args, **kwargs):
            self.calls += 1
            slot = len(self.kept) if len(self.kept) < self.limit else self.rng.randrange(self.calls)
            case = None
            if slot < self.limit:
                try:  # encode before the call, in case the function mutates its arguments
                    case = {'in': pack(args, kwargs)}
                except (Unsupported, RecursionError) as e:
                    self.skipped.add(str(e))
            try:
                result = original(*args, **kwargs)
            except Exception as e:
                self.keep(slot, case, args, kwargs, raises=type(e).__name__)
                raise
            self.keep(slot, case, args, kwargs, result=result)
            return result
        return recorder

    def keep(self, slot, case, args, kwargs, **outcome):
        """Store a finished call, noting argument mutation."""
        if case is None:
            return
        try:
            after = pack(args, kwargs)
            case.update({k: v if k == 'raises' else enc(v) for k, v in outcome.items()})
        except (Unsupported, RecursionError) as e:
            self.skipped.add(str(e))
            return
        if after != case['in']:
            case['after'] = after
        if slot < len(self.kept):
            self.kept[slot] = case
        elif len(self.kept) < self.limit:
            self.kept.append(case)


def edges(value):
    """Inputs where rewrites and originals tend to part ways, same type as the recorded value."""
    t = type(value)
    if t is int:
        return [x for x in (0, 1, -1) if x != value]
    if t is float:
        return [math.nan, math.inf, -math.inf, -0.0, 0.0, 1e308, 5e-324]
    if t is str:
        mid = len(value) // 2
        return [value[:mid] + NON_ASCII[0] + value[mid:], value + NON_ASCII[1], NON_ASCII[2] + value,
                value + NON_ASCII[3], '']
    if t is bytes:
        return [b'', value + b'\x00', b'\xff' + value]
    if t in (list, tuple) and value:
        return [t()] + [t([e]) + value[1:] if t is tuple else [e] + value[1:] for e in edges(value[0])[:4]]
    return []


def resized(value, rng):
    """Empty, tiny, random-slice and repeated (up to 4096) versions of a sequence."""
    if type(value) not in (list, tuple, str, bytes) or not value:
        return []
    n = len(value)
    out = [value[s:s + k] for k in SLICES if k < n for s in [rng.randrange(n - k + 1)]]
    return out + [value * f for f in (4, 16) if n * f <= 4096]


def derive(original, cases, budget=3.0, limit=200):
    """Extra cases from a sample of real calls, answered by the original; inputs it rejects are skipped."""
    rng, out, seen, start = random.Random(0xFA57), [], set(), time.perf_counter()
    for case in [c for c in cases if 'raises' not in c][:20]:
        args, kwargs = unpack(case['in'])
        for key in list(range(len(args))) + list(kwargs):
            value = args[key] if isinstance(key, int) else kwargs[key]
            short = value[:64] if type(value) in (list, tuple, str, bytes) else value
            for new in edges(short) + resized(value, rng):
                if len(out) >= limit or time.perf_counter() - start > budget:
                    return out
                a, k = list(args), dict(kwargs)
                if isinstance(key, int):
                    a[key] = new
                else:
                    k[key] = new
                try:
                    before = pack(a, k)
                    mark = json.dumps(before, sort_keys=True)
                    if mark in seen:
                        continue
                    seen.add(mark)
                    a, k = unpack(before)
                    got = {'in': before, 'result': enc(original(*a, **k)), 'derived': True}
                    if pack(a, k) != before:
                        got['after'] = pack(a, k)
                    out.append(got)
                except Exception:
                    continue  # outside the function's domain: not a fair test
    return out


def per_call_ns(fn, cases, budget=0.5):
    """Fastest replay of the recorded calls, per call; arguments are rebuilt outside the timed part."""
    best, spent, passes = math.inf, 0.0, 0
    while passes < 3 or (spent < budget and passes < 200):
        calls = [unpack(c['in']) for c in cases]
        start = time.perf_counter()
        for args, kwargs in calls:
            try:
                fn(*args, **kwargs)
            except Exception:
                pass
        took = time.perf_counter() - start
        best, spent, passes = min(best, took), spent + took, passes + 1
    return best / len(cases) * 1e9


def lookup(module, qualname):
    """(owner object, attribute name) for qualname inside a module."""
    owner, parts = module, qualname.split('.')
    for part in parts[:-1]:
        owner = getattr(owner, part)
    return owner, parts[-1]


def cmd_record(opts, workload):
    """Run the workload with the target wrapped; save real calls plus derived edge cases."""
    path, sep, qualname = opts.target.rpartition(':')
    if not sep or not path.endswith('.py') or not os.path.isfile(path):
        print('tz fast: record takes file.py:function (or file.py:Class.staticmethod)')
        return 2
    path = os.path.abspath(path)
    module, target, rest, entry, base = prepare(workload)
    infos = [i for i in analyse(path).values() if i['qualname'] == qualname]
    if not infos:
        print('tz fast: no function %s in %s' % (qualname, path))
        return 2
    blockers = infos[0]['blockers']
    if path == entry:
        print('tz fast: %s lives in the entry script: move it to its own module' % qualname)
        return 2
    if blockers and not opts.force:
        # WHY: replaying a function with side effects repeats them
        print('tz fast: not safe to replay: %s (--force records anyway, without edge cases)' % '; '.join(blockers))
        return 2
    rel = os.path.relpath(path, base)[:-3].split(os.sep)
    if rel[0] == os.pardir:
        print('tz fast: %s cannot be imported from %s' % (path, base))
        return 2
    name = '.'.join(rel[:-1] if rel[-1] == '__init__' else rel)
    owner, attr = lookup(importlib.import_module(name), qualname)
    raw = vars(owner)[attr]
    original = getattr(owner, attr)
    recorder = Recorder(opts.limit)
    wrapped = recorder.wrap(original)
    setattr(owner, attr, staticmethod(wrapped) if isinstance(raw, staticmethod) else wrapped)
    try:
        code = run_target(module, target, rest, opts.duration)
    finally:
        setattr(owner, attr, raw)
    if code or not recorder.kept:
        print('tz fast: nothing saved: app exit %s, %d calls seen%s' % (
            code, recorder.calls, ', unsupported: ' + ', '.join(sorted(recorder.skipped)) if recorder.skipped else ''))
        return 1
    real = recorder.kept
    extra = [] if opts.no_edges or blockers else derive(original, real)
    ident = name + '.' + qualname
    folder = os.path.join(STORE, ident)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(STORE, '.gitignore'), 'w') as f:
        f.write('*\n')  # recordings hold real app data: never commit them
    data = ''.join(json.dumps(c) + '\n' for c in real + extra).encode('ascii')
    with open(os.path.join(folder, 'calls.jsonl'), 'wb') as f:
        f.write(data)
    meta = {'module': name, 'qualname': qualname, 'base': os.path.relpath(base), 'python': sys.executable,
            'recorded': len(real), 'sha256': hashlib.sha256(data).hexdigest(),
            'original_ns': per_call_ns(original, real)}
    with open(os.path.join(folder, 'meta.json'), 'w') as f:
        json.dump(meta, f, indent=1)
    print('recorded %d of %d calls + %d derived [actual] -> %s' % (len(real), recorder.calls, len(extra), folder))
    if recorder.skipped:
        print('skipped unsupported values: ' + ', '.join(sorted(recorder.skipped)))
    print('now change the code, then: tz fast verify ' + ident)
    return 0


# ------------------------------------------------------------------ verify

def load(spec):
    """The callable named by file.py:name or module:name."""
    where, _, qualname = spec.rpartition(':')
    if where.endswith('.py'):
        sys.path.insert(0, os.path.dirname(os.path.abspath(where)))
        found = importlib.util.spec_from_file_location('_tzfast_candidate', where)
        module = importlib.util.module_from_spec(found)
        sys.modules[found.name] = module
        found.loader.exec_module(module)
    else:
        module = importlib.import_module(where)
    return getattr(*lookup(module, qualname))


def check(fn, case):
    """None if fn behaves like the recording, else (expected, got) as text."""
    args, kwargs = unpack(case['in'])
    try:
        got, err = fn(*args, **kwargs), None
    except KeyboardInterrupt:
        raise
    except BaseException as e:
        got, err = None, e
    if 'raises' in case:
        if not (isinstance(err, Exception) and type(err).__name__ == case['raises']):
            return 'raises ' + case['raises'], show(got) if err is None else 'raised ' + type(err).__name__
    else:
        want = dec(case['result'])
        if err is not None:
            return show(want), 'raised %s: %s' % (type(err).__name__, show(str(err)))
        if not same(want, got):
            return show(want), show(got)
    want_args, want_kw = unpack(case.get('after', case['in']))
    if not same([want_args, want_kw], [list(args), kwargs]):
        return 'arguments left as ' + show([want_args, want_kw]), show([list(args), kwargs])
    return None


def cmd_verify(opts, _workload):
    """Replay every recorded call against the new code. 0 same and faster, 1 differs, 3 same but not faster."""
    folder = os.path.join(STORE, opts.id)
    try:
        with open(os.path.join(folder, 'meta.json')) as f:
            meta = json.load(f)
        with open(os.path.join(folder, 'calls.jsonl'), 'rb') as f:
            data = f.read()
    except (OSError, ValueError):
        print('tz fast: no recording at %s (run: tz fast record)' % folder)
        return 2
    if hashlib.sha256(data).hexdigest() != meta['sha256']:
        print('tz fast: FAIL, the recording was edited; record again from the original code')
        return 1
    if meta['python'] != sys.executable and os.path.isfile(meta['python']) \
            and PYTHON.match(os.path.basename(meta['python'])):
        return subprocess.call([meta['python'], os.path.abspath(__file__)] + opts.argv)
    cases = [json.loads(line) for line in data.splitlines()]
    # WHY: a quick same-size edit must not be answered by a stale .pyc; look for bytecode where none exists
    sys.pycache_prefix = os.path.abspath(os.path.join(folder, 'no-cache'))
    sys.path.insert(0, os.path.abspath(meta['base']))
    recorded_spec = meta['module'] + ':' + meta['qualname']
    candidate = load(opts.candidate or recorded_spec)
    failures = [(i, c, r) for i, c in enumerate(cases) for r in [check(candidate, c)] if r]
    print('%d/%d calls identical (%d real, %d derived) [actual]' % (
        len(cases) - len(failures), len(cases), meta['recorded'], len(cases) - meta['recorded']))
    for i, case, (want, got) in failures[:8]:
        args, kwargs = unpack(case['in'])
        print('  case %d %s(%s)\n    expected %s\n    got      %s' % (
            i, meta['qualname'], ', '.join([show(a, 60) for a in args] +
                                           ['%s=%s' % (k, show(v, 60)) for k, v in kwargs.items()]), want, got))
    if failures:
        print('FAIL: do not keep this change')
        return 1
    real = cases[:meta['recorded']]
    before, how = meta['original_ns'], 'record-time baseline, separate runs'
    if opts.candidate and opts.candidate != recorded_spec:
        original = load(recorded_spec)
        if original is not candidate:
            before, how = per_call_ns(original, real), 'original timed in this run'
    after = per_call_ns(candidate, real)
    print('per call: %.0f ns -> %.0f ns, %.2fx [MEASURED, %s]' % (before, after, before / max(after, 1e-9), how))
    if after >= before and not opts.any_speed:
        print('PASS on behaviour, but NOT faster: revert it (--any-speed for a pure refactor)')
        return 3
    print('PASS')
    return 0


# ------------------------------------------------------------------ bench

def stats(xs):
    """median/mean/min/max/stddev (population); zeros for no samples."""
    if not xs:
        return dict.fromkeys(('median', 'mean', 'min', 'max', 'stddev'), 0.0)
    return {'median': statistics.median(xs), 'mean': statistics.mean(xs), 'min': min(xs), 'max': max(xs),
            'stddev': statistics.pstdev(xs)}


def first_difference(a, b):
    """The first line that differs between two outputs, or None."""
    if a == b:
        return None
    x, y = [s.decode('utf-8', 'replace').splitlines() for s in (a, b)]
    for n in range(max(len(x), len(y))):
        left = x[n] if n < len(x) else '(no line)'
        right = y[n] if n < len(y) else '(no line)'
        if left != right:
            return 'line %d: %s became %s' % (n + 1, show(left, 80), show(right, 80))
    return 'the outputs differ only in line endings or a final newline'


def time_once(cmd):
    """(seconds, stdout) for one successful run."""
    start = time.perf_counter()
    try:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True)
    except OSError as e:
        raise SystemExit('tz fast: cannot run %s: %s' % (cmd[0], e))
    took = time.perf_counter() - start
    if r.returncode:
        raise SystemExit('tz fast: %s failed (%d)\n%s' % (
            ' '.join(cmd), r.returncode, r.stderr.decode('utf-8', 'replace')[-1500:]))
    return took, r.stdout


def cmd_bench(opts, workload):
    """Time a command, or two interleaved so drift hits both, and compare their output."""
    if not workload or opts.runs < 1:
        print('tz fast: bench [--runs N] [--vs "new command"] -- command args')
        return 2
    vs = (opts.vs or '').replace('\\', '/') if os.name == 'nt' else opts.vs  # shlex eats Windows backslashes
    cmds = [workload] + ([shlex.split(vs)] if vs else [])
    warm = [time_once(c)[1] for c in cmds]  # warm-up runs, not counted
    times = [[] for _ in cmds]
    for i in range(opts.runs):
        order = list(range(len(cmds)))
        for j in order if i % 2 == 0 else order[::-1]:
            times[j].append(time_once(cmds[j])[0])
    results = [stats(t) for t in times]
    for label, s in zip(('before', 'after') if opts.vs else ('run',), results):
        print('%-6s median %.4fs mean %.4fs min %.4fs max %.4fs stddev %.4fs (n=%d) [MEASURED]' % (
            label, s['median'], s['mean'], s['min'], s['max'], s['stddev'], opts.runs))
    if not opts.vs:
        return 0
    print('speedup %.2fx by median [MEASURED]' % (results[0]['median'] / max(results[1]['median'], 1e-9)))
    diff = first_difference(*warm)
    print('output: ' + ('DIFFERS, ' + diff if diff else 'identical'))
    return 1 if diff else 0


# ------------------------------------------------------------------ cli

def main(argv=None):
    """tz fast scan|record|verify|bench."""
    argv = list(sys.argv[1:] if argv is None else argv)
    cut = argv.index('--') if '--' in argv else len(argv)
    head, workload = argv[:cut], argv[cut + 1:]
    p = argparse.ArgumentParser(prog='tz fast', description=__doc__)
    sub = p.add_subparsers(dest='cmd')
    s = sub.add_parser('scan', help='-- script.py args: rank hot functions')
    s.add_argument('--top', type=int, default=15)
    s.add_argument('--duration', type=float, default=0)
    r = sub.add_parser('record', help='file.py:func -- script.py args: save real calls')
    r.add_argument('target')
    r.add_argument('--limit', type=int, default=500)
    r.add_argument('--duration', type=float, default=0)
    r.add_argument('--no-edges', action='store_true')
    r.add_argument('--force', action='store_true')
    v = sub.add_parser('verify', help='id [file.py:func]: replay the calls against the new code')
    v.add_argument('id')
    v.add_argument('candidate', nargs='?')
    v.add_argument('--any-speed', action='store_true')
    b = sub.add_parser('bench', help='[--vs "cmd"] -- cmd: time whole runs')
    b.add_argument('--runs', type=int, default=5)
    b.add_argument('--vs')
    opts = p.parse_args(head)
    if not opts.cmd:
        p.print_help()
        return 2
    opts.argv = argv
    sys.dont_write_bytecode = True
    if opts.cmd in ('scan', 'record') and workload and PYTHON.match(os.path.basename(workload[0])):
        python, workload = shutil.which(workload[0]) or workload[0], workload[1:]
        if os.path.abspath(python) != os.path.abspath(sys.executable):  # honour the app's own interpreter / venv
            return subprocess.call([python, os.path.abspath(__file__)] + head + ['--'] + workload)
    return {'scan': cmd_scan, 'record': cmd_record, 'verify': cmd_verify, 'bench': cmd_bench}[opts.cmd](opts, workload)


if __name__ == '__main__':
    sys.exit(main())
