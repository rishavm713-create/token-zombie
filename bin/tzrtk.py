#!/usr/bin/env python3
"""Per-command output filters (pytest, git, cargo, tsc, mypy, ruff, go, npm, vitest/jest). Pure stdlib."""
# adapted from rtk-ai/rtk src/cmds/{python/pytest_cmd,python/mypy_cmd,python/ruff_cmd,git/git_cmd,js/tsc_cmd,js/npm_cmd}.rs
# (Apache-2.0, Copyright 2026 RTK AI Labs), see NOTICE and third_party/rtk/LICENSE. Changed: ported to Python; works on already
# captured text (never reruns commands); returns None when unsure; keeps unrecognised lines. cargo/go/js filters are
# line-drop rebuilds from behaviour. Nothing from the BUSL-1.1 engine/ or proxy/ directories is used.
import json, os, re, shutil, subprocess, sys
from collections import Counter

CAP_ERRORS, CAP_WARNINGS, CAP_LIST, CAP_INVENTORY = 20, 10, 20, 50
HUNK_MAX = 100


def _more(n, what):
    """Marker for omitted entries."""
    return f'[TZ: {n} more {what} omitted]'


def _capped(items, cap, what):
    """First cap items, plus a marker when some were left out."""
    return items[:cap] + ([_more(len(items) - cap, what)] if len(items) > cap else [])


# --- pytest -----------------------------------------------------------------
_PY_SUM = re.compile(r'^=*\s*(?:(?:\d+ (?:passed|failed|skipped|errors?|xfailed|xpassed|deselected|warnings?|rerun)(?:, )?)+'
                     r'|no tests ran) in [\d.]+(?:s| seconds)\b[^=]*=*$')
_PY_NOISE = re.compile(r'^(?:platform |cachedir:|rootdir:|configfile:|testpaths:|plugins:|collecting\b|collected \d)'
                       r'|^\S+\.py [.sxX]*[.FEsxX]+(?:\s+\[\s*\d+%\])?$|^[.FEsxX]+(?:\s+\[\s*\d+%\])?$'
                       r'|::\S.* (?:PASSED|SKIPPED|XFAIL|XPASS|FAILED|ERROR)\b.*\[\s*\d+%\]$')
_PY_HEAD = re.compile(r'^_+ (?=.*[^_\s]).+ _+$')


def _py_failure(block):
    """One failure block -> title, up to 4 'E ' lines and 3 location lines."""
    title = block[0].strip('_ ')
    out = [f'[ERROR] {title[6:]}' if title.startswith('ERROR ') else f'[FAIL] {title}']
    errs = [i for i, l in enumerate(block) if i and l.startswith('E ')]
    where = [i for i, l in enumerate(block) if i and (l.startswith('>') or re.match(r'\S+\.py:\d+', l))]
    out += ['     ' + block[i].strip()[:160] for i in sorted(errs[:4] + where[:2] + where[2:][-1:])]
    if len(errs) > 4:
        out.append('     ' + _more(len(errs) - 4, 'error lines'))
    return '\n'.join(out)


def _py_split(lines):
    """Split a pytest log into (failure blocks, short-summary lines, summary lines, other lines)."""
    state, blocks, short, sums, other = '', [], [], [], []
    for line in lines:
        s = line.strip()
        if _PY_SUM.match(s):
            sums.append(s); state = ''
        elif s.startswith('==='):
            title = s.strip('= ')
            state = ('fail' if title in ('FAILURES', 'ERRORS') else 'short' if title.startswith('short test summary')
                     else 'warn' if title.startswith('warnings summary') else '')
            if not state and 'test session starts' not in title:
                other.append(line)
        elif state == 'fail':
            if _PY_HEAD.match(s):
                blocks.append([s])
            elif s and blocks:
                blocks[-1].append(line.rstrip())
        elif state == 'short' and s.startswith(('FAILED', 'ERROR', 'XFAIL', 'XPASS')):
            short.append(s[:200])
        elif state != 'warn' and s and not _PY_NOISE.search(s):
            other.append(line)
    return blocks, short, sums, other


def pytest(text, cmd=''):
    """Counts, failures and anything unrecognised; passing progress dropped."""
    blocks, short, sums, other = _py_split(text.split('\n'))
    if len(sums) != 1:  # no summary (crash, cut off) or several runs: do not guess
        return None
    dur = re.search(r' in ([\d.]+)(?:s| seconds)', sums[0]).group(1)
    n = Counter()
    for num, word in re.findall(r'(\d+) (xpassed|xfailed|passed|failed|skipped|errors?)', sums[0]):
        n['errors' if word.startswith('error') else word] = int(num)
    if not n:
        head = 'Pytest: No tests collected'
    elif n['passed'] and not any(n[k] for k in ('failed', 'errors', 'skipped', 'xfailed', 'xpassed')):
        head = f'Pytest: {n["passed"]} passed in {dur}s'
    else:
        extra = ''.join(f', {n[k]} {k}' for k in ('skipped', 'xfailed', 'xpassed', 'errors') if n[k])
        head = f'Pytest: {n["passed"]} passed, {n["failed"]} failed{extra} in {dur}s'
    out = [head.replace('1 errors', '1 error')]
    if blocks:
        out += ['', 'Failures:'] + _capped([_py_failure(b) for b in blocks], CAP_WARNINGS, 'failures')
    if short:
        out += [''] + _capped(short, CAP_ERRORS, 'summary lines')
    if other:
        out += [''] + _capped(other, CAP_ERRORS, 'other lines')
    return '\n'.join(out)


# --- git --------------------------------------------------------------------
def git_status(text, cmd=''):
    """Drop blank and hint lines; cap each file section (long or short format)."""
    if 'diff --git' in text:  # status -v carries a diff: leave it to the diff crusher
        return None
    out, n, extra = [], 0, 0

    def flush():
        if extra:
            out.append('  ' + _more(extra, 'entries in this section'))
    for line in text.split('\n'):
        s = line.strip()
        if not s or s.startswith(('(use "git', '(create/copy')):
            continue
        short = re.match(r'(?:[ MADRCUT?!]{2}) \S', line)
        if line.startswith('\t') or short:
            n += 1
            if n > (CAP_INVENTORY if short else CAP_LIST):
                extra += 1
                continue
        else:
            flush(); n, extra = 0, 0
        out.append(line)
    flush()
    return '\n'.join(out) or None


def _commit(block, width):
    """One default-format commit block -> 'sha subject (date) <author>' plus up to 3 body lines."""
    sha, refs, meta, body = block
    subject = body[0] if body else ''
    head = f'{sha[:7]}{refs} {subject} ({meta.get("Date", "?")}) <{meta.get("Author", "?").split(" <")[0]}>'
    rest = [l for l in body[1:] if not l.startswith(('Signed-off-by:', 'Co-authored-by:', 'Co-Authored-By:'))]
    lines = [head[:width]] + ['  ' + l[:width] for l in rest[:3]]
    if len(rest) > 3:
        lines.append(f'  [+{len(rest) - 3} lines omitted]')
    return '\n'.join(lines)


def git_log(text, cmd=''):
    """Default/medium git log -> one short entry per commit; None for patch, stat, graph or custom formats."""
    commits = []
    for line in text.split('\n'):
        m = re.match(r'commit ([0-9a-f]{7,64})( .*)?$', line)
        h = re.match(r'(Author|AuthorDate|Date|Commit|CommitDate|Merge):\s*(.*)$', line)
        if m:
            commits.append((m.group(1), m.group(2) or '', {}, []))
        elif not commits:
            return None
        elif h and not commits[-1][3]:
            commits[-1][2][h.group(1)] = h.group(2)
        elif line.startswith('    '):
            if line.strip():
                commits[-1][3].append(line.strip())
        elif line.strip():
            return None
    if not commits:
        return None
    chosen = re.search(r'(?:^|\s)(?:-\d+|-n\s*\d+|--max-count)', cmd or '')  # user set a count: never cap it
    entries = [_commit(c, 120 if chosen else 80) for c in commits]
    return '\n'.join(entries if chosen else _capped(entries, CAP_INVENTORY, 'commits'))


def cap_hunks(diff, limit=HUNK_MAX):
    """Keep at most limit lines of each diff hunk, saying how many were dropped."""
    out, n, extra, inside = [], 0, 0, False
    for line in diff.split('\n') + [None]:
        if line is None or line.startswith(('@@', 'diff ')):
            if extra:
                out.append(f'[TZ: {extra} more lines in this hunk]')
            n, extra, inside = 0, 0, bool(line) and line.startswith('@@')
        elif inside:
            n += 1
            if n > limit:
                extra += 1
                continue
        if line is not None:
            out.append(line)
    return '\n'.join(out)


# --- compilers and linters --------------------------------------------------
_TSC = re.compile(r'^(.+?)(?:\((\d+),\d+\):|:(\d+):\d+ -)\s+(?:error|warning)\s+(TS\d+):\s+(.+)$')


def _grouped(tool, diags, other):
    """diags [(file, line, code, [message lines])] -> totals, top codes, then per-file list (worst file first)."""
    files = {}
    for d in diags:
        files.setdefault(d[0], []).append(d)
    out = other + [f'{tool}: {len(diags)} errors in {len(files)} files']
    codes = Counter(d[2] for d in diags if d[2])
    if len(codes) > 1:
        out.append('Top codes: ' + ', '.join(f'{c} ({k}x)' for c, k in codes.most_common(5)))
    for f, ds in sorted(files.items(), key=lambda kv: -len(kv[1])):
        out.append(f'{f} ({len(ds)} errors)')
        for _, ln, code, msg in ds:
            out.append('  ' + ' '.join(p for p in (f'L{ln}', code, msg[0]) if p))
            out += ['    ' + m for m in msg[1:]]
    return '\n'.join(out)


def tsc(text, cmd=''):
    """Group TypeScript diagnostics by file; None when none parsed (never a false 'no errors')."""
    diags, other, open_ = [], [], False
    for line in text.split('\n'):
        m = _TSC.match(line)
        if m:
            diags.append((m.group(1), m.group(2) or m.group(3), m.group(4), [m.group(5)])); open_ = True
        elif open_ and line[:1] in ' \t' and line.strip() and not re.match(r'\s*(~+|\d+)\s*$', line):
            diags[-1][3].append(line.strip())
        else:
            open_ = False
            if line.strip() and not re.match(r'Found \d+ error|\s*\d+(\s|$)|\s*~+\s*$|Errors\s+Files', line):
                other.append(line)
    return _grouped('TypeScript', diags, _capped(other, CAP_ERRORS, 'other lines')) if diags else None


def mypy(text, cmd=''):
    """Group mypy errors by file, notes attached to their error."""
    diags, other = [], []
    for line in text.split('\n'):
        m = re.match(r'(.+?):(\d+)(?::\d+)?: (error|warning|note): (.+?)(?:\s+\[([\w-]+)\])?$', line)
        if m and m.group(3) != 'note':
            diags.append((m.group(1), m.group(2), f'[{m.group(5)}]' if m.group(5) else '', [m.group(4)]))
        elif m and diags and diags[-1][0] == m.group(1):
            diags[-1][3].append('note: ' + m.group(4))
        elif line.strip() and not line.startswith(('Found ', 'Success:')):
            other.append(line)
    return _grouped('mypy', diags, _capped(other, CAP_ERRORS, 'other lines')) if diags else None


def _ruff_json(text):
    """ruff --output-format json -> [(file, line, col, code, message)] or None."""
    try:
        return [(d['filename'], d['location']['row'], d['location']['column'], d['code'], d['message']) for d in json.loads(text)]
    except (ValueError, TypeError, KeyError):
        return None


def _ruff_text(text):
    """ruff concise or full text -> (diagnostics, footer lines)."""
    diags, foot, pend = [], [], None
    for line in text.split('\n'):
        c = re.match(r'(\S.*?):(\d+):(\d+): ([A-Z]+\d+) (?:\[\*\] )?(.*)$', line)
        h = re.match(r'([A-Z]+\d+) (?:\[\*\] )?(.+)$', line)
        a = re.match(r'\s*--> (.+):(\d+):(\d+)$', line)
        if c:
            diags.append(c.groups())
        elif h:
            pend = h.groups()
        elif a and pend:
            diags.append(a.groups() + pend); pend = None
        elif re.match(r'(Found \d+|\[\*\]|No fixes|warning:|error:|ruff failed)', line):
            foot.append(line)
    return diags, foot


def ruff(text, cmd=''):
    """Totals, top rules and the first violations."""
    diags, foot = _ruff_json(text) if text.lstrip().startswith('[{') else None, []
    if diags is None:
        diags, foot = _ruff_text(text)
    if not diags:
        return None
    rules = Counter(d[3] for d in diags)
    out = [f'Ruff: {len(diags)} issues in {len({d[0] for d in diags})} files',
           'Top rules: ' + ', '.join(f'{r} ({k}x)' for r, k in rules.most_common(CAP_WARNINGS))]
    out += _capped([f'  {f}:{l}:{c} {code} {msg[:100]}' for f, l, c, code, msg in diags], CAP_INVENTORY, 'violations')
    return '\n'.join(out + foot)


# --- line-drop filters ------------------------------------------------------
def _dropper(pattern, label):
    """Build a filter that removes noise lines and says how many."""
    rx = re.compile(pattern)

    def run(text, cmd=''):
        lines = text.split('\n')
        keep = [l for l in lines if not rx.search(l)]
        gone = len(lines) - len(keep)
        return '\n'.join(keep + [f'[TZ: {gone} {label} lines omitted]']) if gone else None
    return run


FILTERS = {
    'pytest': pytest, 'git_status': git_status, 'git_log': git_log, 'tsc': tsc, 'mypy': mypy, 'ruff': ruff,
    'cargo': _dropper(r'^\s*(?:Compiling|Checking|Downloading|Downloaded|Updating|Locking|Adding|Blocking|Fresh|Documenting) '
                      r'|^test .+ \.\.\. (?:ok|ignored.*)$|^running \d+ tests?$|^\s*$', 'cargo progress/passing-test/blank'),
    'go': _dropper(r'^\s*(?:=== (?:RUN|PAUSE|CONT|NAME)\b|--- PASS:)|^go: downloading |^\s*$', 'go run/pass/blank'),
    'npm': _dropper(r'^> (?=.*@)|^\s*(?i:npm (?:warn|notice))\b|[⸨⸩]|^\s*$', 'npm banner/warn/notice/blank'),
    'js_test': _dropper(r'^\s*(?:✓|√|PASS )|^\s*$', 'passing-test/blank'),
}

# command line -> filter name
_CMDS = (('pytest', r'(?:(?:python[\d.]* -m|uv run|poetry run) )?(?:\S*/)?pytest\b'),
         ('git_status', r'git (?:-C \S+ )?status\b'), ('git_log', r'git (?:-C \S+ )?log\b'),
         ('cargo', r'cargo (?:\+\S+ )?(?:test|build|check|clippy|nextest)\b'),
         ('tsc', r'(?:(?:npx|bunx|yarn|pnpm(?: exec)?) )?(?:\S*/)?tsc\b'),
         ('mypy', r'(?:(?:python[\d.]* -m|uv run|poetry run) )?(?:\S*/)?mypy\b'),
         ('ruff', r'(?:(?:python[\d.]* -m|uv run|poetry run) )?(?:\S*/)?ruff (?:check\b|\.|--)'),
         ('go', r'go (?:test|build|vet)\b(?!.* -json)'),
         ('js_test', r'(?:(?:npx|bunx|yarn|pnpm(?: exec)?) )?(?:vitest|jest)\b'),
         ('npm', r'(?:npm|pnpm|yarn) (?:run|test|install|ci|build|i)\b'))
# first output line -> filter name (strict: tool results other than Bash pass through here too)
_SIGNS = (('pytest', r'=+ test session starts =+'), ('git_status', r'On branch \S|HEAD detached (?:at|from) '),
          ('git_log', r'commit [0-9a-f]{40}(?: \(.*\))?\n(?:Merge|Author):'),
          ('cargo', r'\s+(?:Compiling|Checking) \S+ v\d|running \d+ tests?\n'), ('go', r'=== RUN '),
          ('tsc', r'\S+(?:\(\d+,\d+\):|:\d+:\d+ -) error TS\d+:'), ('npm', r'(?:npm (?:warn|WARN|notice) |> \S+@\d\S* )'))


def detect(text, cmd=None):
    """Filter name for this command (single command only), else from the first output line, else None."""
    c = re.sub(r'^(?:cd [^;&|]+&& *|[A-Z_][A-Z0-9_]*=\S* +|rtk +|timeout \d+ +)+', '', (cmd or '').strip())
    if c and not re.search(r'\||;|&&|\n', c):
        for name, rx in _CMDS:
            if re.match(rx, c):
                return name
    head = text.lstrip('\n')[:400]
    return next((name for name, rx in _SIGNS if re.match(rx, head)), None)


def apply(text, cmd=None):
    """(filtered, name) when a filter shrinks the text by >=10%, else (None, name or None). Caller spills the original."""
    from tzcrush import clean
    text = clean(text)
    name = detect(text, cmd)
    if not name:
        return None, None
    try:
        new = FILTERS[name](text, cmd or '')
    except Exception:
        return None, name
    return (new, name) if new and len(new) <= len(text) * 0.9 else (None, name)


# --- CLI --------------------------------------------------------------------
def _emit(text, cmd):
    """Print filtered output (original spilled for `tz recall`) or the text unchanged."""
    new, name = apply(text, cmd)
    if new is None:
        sys.stdout.write(text)
        return
    import tzout
    rid = tzout.spill(text)
    print(new)
    print(f'[TZ rtk:{name}: {len(text) - len(new)} chars removed [actual]. Original: tz recall {rid}]')


def _delegate(argv):
    """Installed rtk binary for a command it filters natively (run as a separate process, never bundled), else None."""
    native = ('git', 'cargo', 'pytest', 'tsc', 'mypy', 'ruff', 'go', 'npm', 'vitest')
    if os.environ.get('TZ_RTK') == '0' or argv[0] not in native or not detect('', ' '.join(argv)):
        return None
    return shutil.which('rtk')


def run(argv):
    """Run one command (no shell), filter its combined output, keep its exit code."""
    rtk = _delegate(argv)
    try:
        if rtk:
            code = subprocess.run([rtk] + argv).returncode
        else:
            r = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')
            _emit(r.stdout, ' '.join(argv)); code = r.returncode
    except OSError as e:
        print(f'tz rtk: cannot run {argv[0]}: {e}', file=sys.stderr)
        return 127
    return code if code >= 0 else 128 - code


def main(argv):
    """tz rtk status | filter [--cmd C] [FILE] | run -- CMD..."""
    sub, rest = (argv[0], argv[1:]) if argv else ('status', [])
    if sub == 'run':
        rest = rest[1:] if rest[:1] == ['--'] else rest
        if rest:
            return run(rest)
    elif sub == 'filter':
        cmd = None
        if rest[:1] == ['--cmd'] and len(rest) > 1:
            cmd, rest = rest[1], rest[2:]
        if rest:
            with open(rest[0], encoding='utf-8', errors='replace') as fh:
                _emit(fh.read(), cmd)
        else:
            _emit(sys.stdin.read(), cmd)
        return 0
    elif sub == 'status':
        print('built-in filters: ' + ', '.join(sorted(FILTERS)))
        print('rtk binary: ' + (shutil.which('rtk') or 'not installed (built-in filters used)'))
        return 0
    print('usage: tz rtk status | filter [--cmd C] [FILE] | run -- CMD...', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
