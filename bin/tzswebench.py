#!/usr/bin/env python3
"""Test-log parsers and FAIL_TO_PASS / PASS_TO_PASS grading, no Docker or dataset.

adapted from SWE-bench/SWE-bench swebench/harness/grading.py and
swebench/harness/log_parsers/{python,go,rust,javascript,java}.py (MIT,
Copyright (c) 2023 Carlos E Jimenez, John Yang, Alexander Wettig, Shunyu Yao,
Kexin Pei, Ofir Press, Karthik R Narasimhan), see NOTICE
"""
import argparse
import json
import re
import sys

PASSED, FAILED, SKIPPED, ERROR, XFAIL = 'PASSED', 'FAILED', 'SKIPPED', 'ERROR', 'XFAIL'
STATUSES = (FAILED, PASSED, SKIPPED, ERROR, XFAIL)
F2P, P2P = 'FAIL_TO_PASS', 'PASS_TO_PASS'
FULL, PARTIAL, NO, INVALID = 'RESOLVED_FULL', 'RESOLVED_PARTIAL', 'RESOLVED_NO', 'INVALID'

BAD_MARKERS = ('>>>>> Patch Apply Failed', '>>>>> Reset Failed',
               '>>>>> Tests Errored', '>>>>> Tests Timed Out')
START, END = '>>>>> Start Test Output', '>>>>> End Test Output'
EXIT_RE = re.compile(r'>>>>> Test Exit Code:\s*(-?\d+)')
# WHY non-zero counts: a runner that dies at start still prints "Executed 0 of 0".
SUITE_RAN = re.compile(
    r"Executed [1-9]\d* of \d+|TOTAL: [1-9]\d* (?:SUCCESS|FAILED)|[1-9]\d* passing"
    r"|Tests:\s+[1-9]\d*|Test Suites:\s+(?:\d+ \w+, )*[1-9]\d* total|^# tests [1-9]\d*"
    r"|[1-9]\d* specs?, \d+ failures?|': ok$", re.M)


# ---- Python runners ----
def _pytest_rows(log):
    """Yield (status, tokens) for lines that start with a pytest status word."""
    for line in log.split('\n'):
        if not line.startswith(STATUSES):
            continue
        if line.startswith(FAILED):
            line = line.replace(' - ', ' ')
        tok = line.split()
        # "SKIPPED [2] path:line: reason" is a count, not a test id
        if len(tok) > 1 and not _skip_summary(tok):
            yield tok[0], tok


def _skip_summary(tok):
    """True for pytest's `SKIPPED [N] ...` summary row."""
    return tok[0] == SKIPPED and bool(re.match(r'^\[\d+\]$', tok[1]))


def parse_pytest(log):
    """pytest -rA summary lines."""
    return {tok[1]: st for st, tok in _pytest_rows(log)}


def parse_pytest_options(log):
    """pytest where parametrize ids hold absolute paths; keep only the basename."""
    out = {}
    for st, tok in _pytest_rows(log):
        name = tok[1]
        m = re.search(r'(.*?)\[(.*)\]', name)
        if m:
            main_, opt = m.groups()
            if opt.startswith('/') and not opt.startswith('//') and '*' not in opt:
                opt = '/' + opt.split('/')[-1]
            name = f'{main_}[{opt}]'
        out[name] = st
    return out


def parse_pytest_v2(log):
    """Newer pytest (ids may contain spaces, colour codes) plus old trailing-status lines."""
    out = {}
    ctrl = str.maketrans('', '', ''.join(map(chr, range(1, 32))))
    for line in log.split('\n'):
        line = re.sub(r'\[(\d+)m', '', line).translate(ctrl)
        if line.startswith(STATUSES):
            if line.startswith(FAILED):
                line = line.split(' - ', 1)[0]
            tok = line.split()
            if len(tok) >= 2 and not _skip_summary(tok):
                out[' '.join(tok[1:])] = tok[0]
        elif line.endswith(STATUSES):
            tok = line.split()
            if len(tok) >= 2:
                out[' '.join(tok[:-1])] = tok[-1]
    return out


def parse_matplotlib(log):
    """pytest with matplotlib's MouseButton reprs normalised."""
    return parse_pytest(log.replace('MouseButton.LEFT', '1').replace('MouseButton.RIGHT', '3'))


def parse_seaborn(log):
    """seaborn's mixed `id PASSED` / `PASSED id` lines."""
    out = {}
    for line in log.split('\n'):
        tok = line.split()
        if len(tok) < 2:
            continue
        if line.startswith(FAILED):
            out[tok[1]] = FAILED
        elif f' {PASSED} ' in line and tok[1] == PASSED:
            out[tok[0]] = PASSED
        elif line.startswith(PASSED):
            out[tok[1]] = PASSED
    return out


def parse_sympy(log):
    """sympy bin/test output."""
    out = {f'{m[1]}.py:{m[2]}': FAILED
           for m in re.findall(r'(_*) (.*)\.py:(.*) (_*)', log)}
    for line in map(str.strip, log.split('\n')):
        if line.startswith('test_'):
            for end, st in ((' E', ERROR), (' F', FAILED), (' ok', PASSED)):
                if line.endswith(end):
                    out[line.split()[0]] = st
    return out


def _django_line(line, out):
    """Apply one stripped django/unittest line to the status map."""
    for suffix in (' ... ok', ' ... OK', ' ...  OK'):
        if line.endswith(suffix):
            # upstream special case: migration noise printed on the same line
            if line.startswith('Applying sites.0002_alter_domain_unique...test_no_migrations'):
                line = line.split('...', 1)[-1].strip()
            out[line.rsplit(suffix, 1)[0]] = PASSED
            break
    if ' ... skipped' in line:
        out[line.split(' ... skipped')[0]] = SKIPPED
    for word, st in (('FAIL', FAILED), ('ERROR', ERROR)):
        if line.endswith(f' ... {word}'):
            out[line.split(f' ... {word}')[0]] = st
        # upstream indexes split()[1] unguarded; a bare "FAIL:" would crash
        if line.startswith(word + ':') and len(line.split()) > 1:
            out[line.split()[1]] = st


def parse_django(log):
    """Django runner and `python -m unittest -v`."""
    out, prev = {}, None
    for line in map(str.strip, log.split('\n')):
        if '--version is equivalent to version' in line:
            out['--version is equivalent to version'] = PASSED
        if ' ... ' in line:
            prev = line.split(' ... ')[0]
        _django_line(line, out)
        # "ok" printed lines after "...": test emitted output in between
        if line.startswith('ok') and prev is not None:
            out[prev] = PASSED
    for pat in (r'^(.*?)\s\.\.\.\sTesting against Django installed in ((?s:.*?)) silenced\)\.\nok$',
                r'^(.*?)\s\.\.\.\sInternal Server Error: /(.*)/\nok$',
                r'^(.*?)\s\.\.\.\sSystem check identified no issues \(0 silenced\)\nok$'):
        for m in re.finditer(pat, log, re.M):
            out[m.group(1)] = PASSED
    return out


# ---- other runners ----
def _by_regex(log, pattern, table, status=1, name=2):
    """Map each matching stripped line to a status through `table`."""
    out = {}
    for line in log.split('\n'):
        m = re.match(pattern, line.strip())
        if m and m.group(status) in table:
            out[m.group(name).strip()] = table[m.group(status)]
    return out


def parse_gotest(log):
    """go test -v."""
    return _by_regex(log, r'^--- (PASS|FAIL|SKIP): (.+) \((.+)\)$',
                     {'PASS': PASSED, 'FAIL': FAILED, 'SKIP': SKIPPED})


def parse_cargo(log):
    """cargo test."""
    return _by_regex(log, r'^test\s+(\S+)\s+\.\.\.\s+(\w+)$',
                     {'ok': PASSED, 'FAILED': FAILED}, status=2, name=1)


def parse_jest(log):
    """jest --verbose."""
    return _by_regex(log, r'^\s*(✓|✕|○)\s(.+?)(?:\s\((\d+\s*m?s)\))?$',
                     {'✓': PASSED, '✕': FAILED, '○': SKIPPED})


def parse_jest_json(log):
    """jest --json after SWE-bench's jq transform (`[PASSED] name`)."""
    return _by_regex(log, r'^\[(PASSED|FAILED)\]\s(.+)$', {PASSED: PASSED, FAILED: FAILED})


def parse_vitest(log):
    """vitest --reporter=verbose."""
    return _by_regex(log, r'^\s*(✓|×|↓)\s(.+?)(?:\s(\d+\s*m?s?|\[skipped\]))?$',
                     {'✓': PASSED, '×': FAILED, '↓': SKIPPED})


def parse_tap(log):
    """TAP `ok N name` / `not ok N name`."""
    return _by_regex(log, r'^(ok|not ok) (\d+) (.+)$',
                     {'ok': PASSED, 'not ok': FAILED}, name=3)


def parse_karma(log):
    """karma spec reporter; suite path comes from indentation."""
    out, depth, suite, started = {}, -1, [], False
    for line in log.split('\n'):
        if line.startswith('SUMMARY:'):
            break
        if 'Starting browser' in line:
            started = True
            continue
        m = re.match(r'^(\s*)?([✔✖])?\s(.*)$', line) if started else None
        if not m:
            continue
        indent, mark, name = m.groups()
        if indent and not mark:
            if len(indent) > depth:
                depth = len(indent)
                suite.append(name)
            elif len(indent) < depth:
                depth = len(indent)
                if suite:
                    suite.pop()
                continue
        if mark:
            out[' > '.join(suite + [name])] = PASSED if mark == '✔' else FAILED
    return out


def parse_maven(log):
    """`mvn test -Dtest=X` run under set -x; results pair with commands FIFO."""
    out, pending, early = {}, [], []
    table = {'SUCCESS': PASSED, 'FAILURE': FAILED}
    for line in map(str.strip, log.split('\n')):
        m = re.match(r'^.*-Dtest=(\S+).*$', line)
        if m:
            pending.append(m.group(1))
        m = re.match(r'^.*BUILD (SUCCESS|FAILURE)$', line)
        if m:
            if pending:
                out[pending.pop(0)] = table[m.group(1)]
            else:
                early.append(m.group(1))
    for name, res in zip(pending, early):
        out[name] = table[res]
    return out


def parse_ant(log):
    """ant junit `[junit] [PASS] name`."""
    return _by_regex(log, r'^\s*\[junit\]\s+\[(PASS|FAIL|ERR)\]\s+(.*)$',
                     {'PASS': PASSED, 'FAIL': FAILED, 'ERR': FAILED})


def parse_gradle(log):
    """gradle test; a status may land on a later line than its test name."""
    out, pending = {}, None
    for line in map(str.strip, log.split('\n')):
        full = re.match(r'^([^>].+)\s+(PASSED|FAILED)$', line)
        name = re.match(r'^([^>]\S*\s+>\s+\S+)$', line)
        if full:
            out[full.group(1)], pending = full.group(2), None
        elif name:
            pending = name.group(1)
        elif pending and line in (PASSED, FAILED):
            out[pending], pending = line, None
    return out


PARSERS = {
    'pytest': parse_pytest, 'pytest-options': parse_pytest_options,
    'pytest-v2': parse_pytest_v2, 'matplotlib': parse_matplotlib,
    'seaborn': parse_seaborn, 'sympy': parse_sympy, 'django': parse_django,
    'unittest': parse_django, 'gotest': parse_gotest, 'cargo': parse_cargo,
    'jest': parse_jest, 'jest-json': parse_jest_json, 'vitest': parse_vitest,
    'tap': parse_tap, 'karma': parse_karma, 'maven': parse_maven,
    'ant': parse_ant, 'gradle': parse_gradle,
}


def read_status(content, parser):
    """Return (status_map, '') or ({}, reason) when the log cannot be trusted."""
    for bad in BAD_MARKERS:
        if bad in content:
            return {}, bad.lstrip('> ')
    body = content
    # WHY optional markers (upstream requires them): users grade plain runner logs too;
    # one marker without the other still means a cut-off run.
    if START in content or END in content:
        if START not in content or END not in content:
            return {}, 'test output markers incomplete'
        body = content.split(START)[1].split(END)[0]
    parse = PARSERS[parser]
    sm = parse(body) or (parse(content) if body is not content else {})
    if not sm and not SUITE_RAN.search(content):
        return {}, 'no test results and no sign the suite ran'
    m = EXIT_RE.search(content)
    # a patch can print fake PASSED lines; a non-zero exit with no failure exposes it
    if m and int(m.group(1)) != 0 and sm and not {FAILED, ERROR} & set(sm.values()):
        return {}, f'exit code {m.group(1)} but no failure reported'
    return sm, ''


# ---- grading ----
def _lookup(case, sm):
    """Status for a case, prefix-matching only ids truncated inside `[` (upstream #290)."""
    if case in sm:
        return sm[case]
    if case.count('[') > case.count(']'):
        hits = [v for k, v in sm.items() if k.startswith(case)]
        if hits and len({v in (PASSED, XFAIL) for v in hits}) == 1:
            return hits[0]
    return None


def _outcome(case, sm, kind, fail_only):
    """True success, False failure, None when upstream counts neither."""
    if fail_only:
        return sm.get(case) != FAILED
    st = _lookup(case, sm)
    if st in (PASSED, XFAIL) or (kind == P2P and st == SKIPPED):
        return True
    # missing or skipped F2P is not a resolution
    return False if st in (None, FAILED, ERROR, SKIPPED) else None


def eval_report(sm, gold, eval_type='pass_and_fail'):
    """{FAIL_TO_PASS|PASS_TO_PASS: {success, failure}} for the gold id lists."""
    rep = {}
    for kind in (F2P, P2P):
        rep[kind] = {'success': [], 'failure': []}
        for case in gold.get(kind, []):
            res = _outcome(case, sm, kind, eval_type == 'fail_only')
            if res is not None:
                rep[kind]['success' if res else 'failure'].append(case)
    return rep


def resolution(rep):
    """FULL if both ratios are 1, PARTIAL if only F2P is partly met, else NO."""
    def ratio(kind):
        n = len(rep[kind]['success']) + len(rep[kind]['failure'])
        return len(rep[kind]['success']) / n if n else 1
    f, p = ratio(F2P), ratio(P2P)
    if p != 1:
        return NO
    return FULL if f == 1 else PARTIAL if f > 0 else NO


def derive_gold(before):
    """Gold lists from a baseline run: failing tests must pass, passing ones must stay."""
    return {F2P: sorted(k for k, v in before.items() if v in (FAILED, ERROR)),
            P2P: sorted(k for k, v in before.items() if v in (PASSED, XFAIL))}


def grade(after, parser='pytest', before=None, f2p=None, p2p=None, eval_type='pass_and_fail'):
    """Grade log text; explicit f2p/p2p override the lists derived from `before`."""
    def invalid(why):
        return {'status': INVALID, 'resolved': False, 'reason': why}
    sm, why = read_status(after, parser)
    if why:
        return invalid('after log: ' + why)
    gold = {F2P: [], P2P: []}
    if before is not None:
        base, why = read_status(before, parser)
        if why:
            return invalid('before log: ' + why)
        gold = derive_gold(base)
    if f2p is not None:
        gold[F2P] = list(f2p)
        # a named target must not also be required as "already passing"
        gold[P2P] = [t for t in gold[P2P] if t not in gold[F2P]]
    if p2p is not None:
        gold[P2P] = list(p2p)
    # WHY: an empty F2P list scores ratio 1, which would "resolve" with nothing fixed
    if not gold[F2P]:
        return invalid('no FAIL_TO_PASS tests (none failed before, none given)')
    rep = eval_report(sm, gold, eval_type)
    status = resolution(rep)
    return {'status': status, 'resolved': status == FULL, 'tests_status': rep}


# ---- CLI ----
def _read(path):
    """File text, tolerating stray bytes from test output."""
    with open(path, encoding='utf-8', errors='replace') as fh:
        return fh.read()


def _load_spec(path):
    """Read FAIL_TO_PASS/PASS_TO_PASS JSON; dataset rows store them as JSON strings."""
    spec = json.loads(_read(path))
    out = {}
    for key, arg in ((F2P, 'f2p'), (P2P, 'p2p')):
        if key in spec:
            val = json.loads(spec[key]) if isinstance(spec[key], str) else spec[key]
            if not isinstance(val, list):
                raise ValueError(f'{key} must be a list')
            out[arg] = val
    return out


def _print_grade(res):
    """Human summary with measured counts."""
    print(res['status'] + (f": {res['reason']}" if 'reason' in res else ''))
    for kind, r in res.get('tests_status', {}).items():
        total = len(r['success']) + len(r['failure'])
        print(f"{kind}: {len(r['success'])}/{total} [actual]")
        for name in r['failure']:
            print('  fail ' + name)


def _args(argv):
    """Parse the command line."""
    ap = argparse.ArgumentParser(prog='tz swebench', description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    for cmd in ('parse', 'grade'):
        p = sub.add_parser(cmd)
        p.add_argument('log', help='test log (grade: the run after the change)')
        p.add_argument('--parser', default='pytest', choices=sorted(PARSERS))
        p.add_argument('--json', action='store_true')
    p.add_argument('--before', help='baseline log; derives both test lists')
    p.add_argument('--spec', help='JSON with FAIL_TO_PASS / PASS_TO_PASS')
    p.add_argument('--f2p', action='append', help='test id that must now pass')
    p.add_argument('--p2p', action='append', help='test id that must keep passing')
    p.add_argument('--fail-only', action='store_true', help='only explicit FAILED counts')
    return ap.parse_args(argv)


def main(argv=None):
    """Exit 0 ok/resolved, 1 not resolved, 2 invalid log or input."""
    a = _args(sys.argv[1:] if argv is None else argv)
    try:
        if a.cmd == 'parse':
            sm, why = read_status(_read(a.log), a.parser)
            if why:
                print('INVALID: ' + why)
                return 2
            print(json.dumps(sm, indent=2) if a.json else
                  '\n'.join(f'{v} {k}' for k, v in sm.items()))
            return 0
        lists = _load_spec(a.spec) if a.spec else {}
        lists.update({k: v for k, v in (('f2p', a.f2p), ('p2p', a.p2p)) if v})
        res = grade(_read(a.log), a.parser, _read(a.before) if a.before else None,
                    eval_type='fail_only' if a.fail_only else 'pass_and_fail', **lists)
    except (OSError, ValueError) as e:
        print(f'tz swebench: {e}', file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(res, indent=2))
    else:
        _print_grade(res)
    return 2 if res['status'] == INVALID else 0 if res['resolved'] else 1


if __name__ == '__main__':
    sys.exit(main())
