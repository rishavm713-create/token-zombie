#!/usr/bin/env python3
"""tz tbench: check, run and score LOCAL Terminal-Bench style task dirs (task.yaml, run-tests.sh, solution.sh, tests/).
Parsing, resolve rule, pass@k and defaults adapted from terminal-bench terminal_bench/{parsers,harness,handlers}
(Apache-2.0, laude-institute/terminal-bench contributors), ported to stdlib Python and changed, see NOTICE.
`run` is NOT Docker and NOT isolation: the task's scripts run as you, with your files, network and environment.
Do not allow-list `tz tbench run` in Claude Code permissions. Nothing is installed or downloaded here."""
import json, math, os, re, shutil, signal, subprocess, sys, tempfile

REQUIRED = ('instruction', 'difficulty')
# upstream CI (scripts_bash/validate-task-fields.sh) also wants these in published tasks
PUBLISH = ('author_name', 'author_email', 'category', 'tags', 'parser_name',
           'expert_time_estimate_min', 'junior_time_estimate_min')
DEFAULTS = {'author_name': 'unknown', 'author_email': 'unknown', 'category': 'software_engineering', 'tags': [],
            'parser_name': 'pytest', 'max_agent_timeout_sec': 360.0, 'max_test_timeout_sec': 60.0,
            'run_tests_in_same_shell': False}
DIFFICULTY = ('easy', 'medium', 'hard', 'unknown')
# A lint that stops accidental installs/downloads. It is easy to bypass, so it is no safety control.
NET = re.compile(r'\b(apt-get|apt|apk|yum|dnf|brew|curl|wget|pip3? install|uv (?:pip|add|venv|run)|npm (?:i|install|ci)|'
                 r'git clone|docker)\b')
SUMMARY = re.compile(r'=+\s*short test summary info\s*=+', re.I)
STATUS = {'PASSED': 'passed', 'XFAIL': 'passed', 'SKIPPED': 'passed', 'FAILED': 'failed', 'XPASS': 'failed',
          'ERROR': 'failed'}
CAP = 5_000_000  # bytes of test output kept, from the end where the summary is


def _uncomment(s):
    """Drop a trailing YAML comment from a one-line value."""
    s = s.strip()
    if s[:1] in ('"', "'"):
        m = re.match(r'("(?:[^"\\]|\\.)*"|\'(?:[^\']|\'\')*\')\s*(?:#.*)?$', s)
        if not m:
            raise ValueError('unsupported quoted value: %s' % s[:60])
        return m.group(1)
    return re.split(r'(?:^|\s)#', s)[0].strip()


def _scalar(s):
    """One YAML scalar or flow list (subset)."""
    if s[:1] == '"':
        return json.loads(s)
    if s[:1] == "'":
        return s[1:-1].replace("''", "'")
    if s[:1] == '[':
        if not s.endswith(']'):
            raise ValueError('multi-line list is not supported')
        parts = re.findall(r'\s*("(?:[^"\\]|\\.)*"|\'(?:[^\']|\'\')*\'|[^,]+)\s*(?:,|$)', s[1:-1])
        return [_scalar(p.strip()) for p in parts if p.strip()]
    if s[:1] in ('{', '&', '*', '!'):
        raise ValueError('unsupported YAML: %s' % s[:60])
    low = s.lower()
    if low in ('', '~', 'null'):
        return None
    if low in ('true', 'false'):
        return low == 'true'
    if re.match(r'[-+]?(\d+(\.\d*)?|\.\d+)$', s):
        return float(s) if '.' in s else int(s)
    return s


def _indented(lines, i):
    """Lines from i that belong to the key above: blank or indented. Returns (block, next index)."""
    j = i
    while j < len(lines) and (not lines[j].strip() or lines[j][0] in ' \t'):
        j += 1
    return lines[i:j], j


def _block(style, body):
    """A `|` or `>` block scalar with its chomping rule."""
    pad = next((len(x) - len(x.lstrip(' ')) for x in body if x.strip()), 0)
    explicit = re.search(r'\d', style)
    pad = int(explicit.group()) if explicit else pad
    if any(x.strip() and len(x) - len(x.lstrip(' ')) < pad for x in body):
        raise ValueError('bad indentation in block text')
    text = '\n'.join(x[pad:] for x in body)
    core = text.rstrip('\n')
    if style[0] == '>':  # folded: single newline between flush lines becomes a space
        core = re.sub(r'(?m)^(\S.*)\n(?=\S)', r'\1 ', core)
        core = re.sub(r'(?m)^(\S.*)\n(\n+)(?=\S)', r'\1\2', core)
    if '-' in style:
        return core
    return text + '\n' if '+' in style else core + '\n' if core else ''


def _value(head, body):
    """The value of one top-level key from its first line and its indented lines."""
    if re.match(r'[|>][-+\d]*\s*(#.*)?$', head):
        return _block(head.split()[0], body)
    rest = [x.strip() for x in body if x.strip() and not x.strip().startswith('#')]
    if head[:1] in ('"', "'") and rest:
        raise ValueError('multi-line quoted value is not supported')
    head = _uncomment(head)
    if not head and rest:
        if not all(x == '-' or x.startswith('- ') for x in rest):
            raise ValueError('nested maps are not supported')
        return [_scalar(_uncomment(x[1:])) for x in rest]
    if head and rest:
        # YAML folds a plain value or flow list that continues on indented lines
        if head[:1] in ('"', "'"):
            raise ValueError('text after a quoted value')
        head = _uncomment(' '.join([head] + rest))
    return _scalar(head)


def read_yaml(text):
    """Parse the flat YAML subset task.yaml files use; raise ValueError on anything else."""
    lines, out, i = text.lstrip('﻿').splitlines(), {}, 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip() or line.lstrip().startswith('#') or line.rstrip() == '---':
            continue
        m = re.match(r'([A-Za-z_][\w-]*):(?:\s+(.*))?$', line.rstrip())
        if not m:
            raise ValueError('line %d: unsupported YAML' % i)
        key, head = m.group(1), (m.group(2) or '').strip()
        body, i = _indented(lines, i)
        # a list may sit at column 0 under its key
        while not _uncomment_safe(head) and i < len(lines) and re.match(r'-(\s|$)', lines[i]):
            more, j = _indented(lines, i + 1)
            body, i = body + ['  ' + lines[i]] + more, j
        out[key] = _value(head, body)
    return out


def _uncomment_safe(head):
    """The key's first line without comment; quoted heads count as non-empty."""
    return head if head[:1] in ('"', "'") else _uncomment(head)


def _read(path):
    """File text, tolerant of bad bytes."""
    with open(path, encoding='utf-8', errors='replace') as f:
        return f.read()


def load_task(d):
    """task.yaml plus upstream defaults and type checks; raises ValueError."""
    raw = read_yaml(_read(os.path.join(d, 'task.yaml')))
    miss = [k for k in REQUIRED if raw.get(k) in (None, '')]
    if miss:
        raise ValueError('missing required field(s): ' + ', '.join(miss))
    t = dict(DEFAULTS, **{k: v for k, v in raw.items() if v is not None})
    if t['difficulty'] not in DIFFICULTY:
        raise ValueError('invalid difficulty: %r' % t['difficulty'])
    for k in ('max_agent_timeout_sec', 'max_test_timeout_sec'):
        if isinstance(t[k], bool) or not isinstance(t[k], (int, float)) or t[k] <= 0:
            raise ValueError('%s must be a positive number' % k)
    if not isinstance(t['instruction'], str) or not isinstance(t['tags'], list):
        raise ValueError('instruction must be text and tags a list')
    return t


def check(d, publish=False):
    """Validate one task dir; returns {'task', 'errors', 'warnings'}."""
    errs, warns = [], []
    if not os.path.isfile(os.path.join(d, 'task.yaml')):
        return {'task': d, 'errors': ['no task.yaml'], 'warnings': []}
    try:
        t = load_task(d)
        if t['parser_name'] != 'pytest':
            warns.append('parser %s: only pytest results can be read here' % t['parser_name'])
        if publish:
            raw = read_yaml(_read(os.path.join(d, 'task.yaml')))
            errs += ['missing publish field: ' + k for k in PUBLISH if k not in raw]
    except (OSError, ValueError) as e:
        errs.append(str(e))
    has = lambda n: os.path.isfile(os.path.join(d, n))
    if not has('run-tests.sh'):
        errs.append('no run-tests.sh')
    if not (has('solution.sh') or has('solution.yaml')):
        errs.append('no solution.sh or solution.yaml')
    if not os.path.isdir(os.path.join(d, 'tests')):
        warns.append('no tests/ directory')
    for n in ('run-tests.sh', 'solution.sh'):
        hit = has(n) and net_use(_read(os.path.join(d, n)))
        if hit:
            warns.append('%s needs network/install/Docker (%s): `run` refuses it' % (n, ', '.join(hit)))
    return {'task': d, 'errors': errs, 'warnings': warns}


def net_use(script):
    """Install/network commands named on non-comment lines."""
    return sorted({m for line in script.splitlines() if not line.lstrip().startswith('#') for m in NET.findall(line)})


def find_tasks(paths):
    """Task dirs: each path itself, or its subdirectories that hold a task.yaml."""
    out = []
    for p in paths:
        subs = []
        if os.path.isdir(p) and not os.path.isfile(os.path.join(p, 'task.yaml')):
            subs = [os.path.join(p, n) for n in sorted(os.listdir(p))]
            subs = [s for s in subs if os.path.isfile(os.path.join(s, 'task.yaml'))]
        out += subs or [p]
    return out


def parse_pytest(text):
    """{test name: 'passed'|'failed'} from `pytest -rA` output; ValueError without a short summary."""
    parts = SUMMARY.split(text, maxsplit=1)
    if len(parts) < 2:
        raise ValueError('No short test summary info found')
    out = {}
    for line in parts[1].splitlines():
        if line.startswith('FAILED') and ' - ' in line:
            line = line.rsplit(' - ', 1)[0]
        bits = line.split(maxsplit=1)
        status = STATUS.get(bits[0].strip(':')) if len(bits) == 2 else None
        name = bits[1].strip().split('::', 1)[-1] if status else ''
        # changed from upstream: same name in two files, a failure is never overwritten by a pass
        if name and out.get(name) != 'failed':
            out[name] = status
    return out


def is_resolved(results):
    """All tests passed. Changed from upstream: zero parsed tests is not a pass."""
    return bool(results) and all(v == 'passed' for v in results.values())


def pass_at_k(rows):
    """{k: mean chance that k attempts contain a pass} over tasks with enough attempts."""
    tasks = {}
    for r in rows:
        tasks.setdefault(r['task_id'], []).append(1 if r.get('is_resolved') else 0)
    if not tasks:
        return {}
    low = min(map(len, tasks.values()))
    ks = {2 ** i for i in range(1, low.bit_length())} | {k for k in (5, 10) if low >= k}
    miss = lambda c, k: math.comb(len(c) - sum(c), k) / math.comb(len(c), k)
    return {k: sum(1 - miss(c, k) for c in tasks.values()) / len(tasks) for k in sorted(ks)}


def score(doc):
    """Summary of a results.json ({'results': [trial, ...]}); every number comes from that file."""
    rows = doc.get('results') if isinstance(doc, dict) else None
    if not isinstance(rows, list) or not all(isinstance(r, dict) and 'task_id' in r for r in rows):
        raise ValueError('not a results.json: need "results" rows with task_id')
    won = [r['task_id'] for r in rows if r.get('is_resolved')]
    modes = {}
    for r in rows:
        m = str(r.get('failure_mode') or 'unset')
        modes[m] = modes.get(m, 0) + 1
    out = {'trials': len(rows), 'n_resolved': len(won), 'accuracy': len(won) / len(rows) if rows else 0.0,
           'resolved_ids': won, 'unresolved_ids': [r['task_id'] for r in rows if not r.get('is_resolved')],
           'failure_modes': modes, 'pass_at_k': pass_at_k(rows)}
    for k in ('total_input_tokens', 'total_output_tokens'):
        have = [r[k] for r in rows if isinstance(r.get(k), (int, float))]
        out[k] = sum(have) if have else None
        out[k + '_rows'] = len(have)  # partial token data must stay visible
    return out


def _kill(p):
    """Stop the script and anything it left running."""
    try:
        os.killpg(p.pid, signal.SIGKILL) if hasattr(os, 'killpg') else p.kill()
    except OSError:
        pass


def _bash(script, cwd, env, timeout):
    """Run one bash script; returns (output tail, exit code or None on timeout)."""
    with tempfile.TemporaryFile() as log:
        p = subprocess.Popen([shutil.which('bash'), script], cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                             stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            rc = p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            rc = None
        finally:
            _kill(p)
            p.wait()
        log.seek(max(0, log.seek(0, os.SEEK_END) - CAP))
        return log.read().decode('utf-8', 'replace'), rc


def _refusal(d, oracle):
    """Why this task cannot run on the host, or ''."""
    bad = check(d)['errors']
    if bad:
        return '; '.join(bad)
    if load_task(d)['parser_name'] != 'pytest':
        return 'only the pytest parser is supported'
    if not shutil.which('bash'):
        return 'bash not found'
    for n in ['run-tests.sh'] + (['solution.sh'] if oracle else []):
        path = os.path.join(d, n)
        if not os.path.isfile(path):
            return 'no %s' % n
        if net_use(_read(path)):
            return '%s needs network/install/Docker: %s' % (n, ', '.join(net_use(_read(path))))
    return ''


def run(d, oracle=False, workdir=None):
    """One local trial on the host: optional oracle, then tests. status is pass | fail | error (harness)."""
    res = {'task_id': os.path.basename(os.path.abspath(d)), 'is_resolved': False, 'failure_mode': 'unset',
           'parser_results': None, 'status': 'error', 'detail': ''}
    why = _refusal(d, oracle)
    if why:
        return dict(res, failure_mode='refused', detail=why)
    t = load_task(d)
    with tempfile.TemporaryDirectory(prefix='tz-tbench-') as tmp:
        # copies keep the task dir untouched, like upstream copying tests into its container
        tdir = os.path.join(tmp, 'tests')
        src = os.path.join(d, 'tests')
        shutil.copytree(src, tdir) if os.path.isdir(src) else os.mkdir(tdir)
        for n in ['run-tests.sh'] + (['solution.sh'] if oracle else []):
            shutil.copy(os.path.join(d, n), os.path.join(tdir, n))
        work = os.path.abspath(workdir) if workdir else os.path.join(tmp, 'work')
        os.makedirs(work, exist_ok=True)
        env = dict(os.environ, TEST_DIR=tdir)
        if oracle:
            out, rc = _bash(os.path.join(tdir, 'solution.sh'), work, env, t['max_agent_timeout_sec'])
            if rc != 0:
                return dict(res, failure_mode='oracle_error', detail=out[-500:])
        out, rc = _bash(os.path.join(tdir, 'run-tests.sh'), work, env, t['max_test_timeout_sec'])
    if rc is None:
        return dict(res, failure_mode='test_timeout', detail=out[-500:])
    try:
        got = parse_pytest(out)
    except ValueError as e:
        return dict(res, failure_mode='parse_error', detail='%s\n%s' % (e, out[-500:]))
    if not got:
        return dict(res, failure_mode='parse_error', detail='summary lists no tests\n' + out[-500:])
    ok = is_resolved(got)
    return dict(res, parser_results=got, is_resolved=ok, status='pass' if ok else 'fail')


USAGE = '''usage: tz tbench check DIR... [--publish]     validate task dirs (runs nothing)
       tz tbench parse LOG|-                    per-test results from `pytest -rA` output
       tz tbench run DIR... --host [--oracle] [--workdir D]
            runs task scripts ON THIS MACHINE (no Docker, no isolation); --oracle runs solution.sh first
       tz tbench score RESULTS.json             accuracy and pass@k from a results file'''


def _cmd_check(args, publish):
    """Print one line per task; 1 if any has errors."""
    reps = [check(d, publish) for d in find_tasks(args)]
    for r in reps:
        print('%s %s' % ('FAIL' if r['errors'] else 'ok  ', r['task']))
        for kind in ('errors', 'warnings'):
            for m in r[kind]:
                print('  %s: %s' % (kind[:-1], m))
    bad = sum(bool(r['errors']) for r in reps)
    print('[actual] %d task(s), %d with errors' % (len(reps), bad))
    return 1 if bad else 0


def _cmd_run(args, argv):
    """Run tasks on the host and print a results.json document."""
    work = None
    if '--workdir' in args:
        i = args.index('--workdir')
        if i + 1 >= len(args):
            print(USAGE)
            return 2
        work = args[i + 1]
        args = args[:i] + args[i + 2:]
    dirs = find_tasks(args)
    if '--host' not in argv:
        print('refused: task scripts would run on this machine without isolation. Read them, then add --host.')
        return 2
    if work and len(dirs) > 1:
        print('--workdir takes exactly one task')
        return 2
    rows = [run(d, '--oracle' in argv, work) for d in dirs]
    print(json.dumps({'results': rows}, indent=1))
    return 0 if all(r['status'] == 'pass' for r in rows) else 1


def main(argv):
    """CLI entry: check | parse | run | score."""
    flags = ('--publish', '--host', '--oracle')
    cmd = argv[0] if argv else ''
    args = [a for a in argv[1:] if a not in flags]
    if not args:
        print(USAGE)
        return 2
    try:
        if cmd == 'check':
            return _cmd_check(args, '--publish' in argv)
        if cmd == 'run':
            return _cmd_run(args, argv)
        if cmd == 'parse':
            got = parse_pytest(sys.stdin.read() if args[0] == '-' else _read(args[0]))
            print(json.dumps({'parser_results': got, 'is_resolved': is_resolved(got)}, indent=1))
            return 0 if is_resolved(got) else 1
        if cmd == 'score':
            print('[actual] from ' + args[0], file=sys.stderr)
            print(json.dumps(score(json.loads(_read(args[0]))), indent=1))
            return 0
    except (OSError, ValueError) as e:
        print('tbench: %s' % e)
        return 1
    print(USAGE)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
