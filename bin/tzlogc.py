#!/usr/bin/env python3
# Build/test log compressor: keep every failure line, trace, failure section and summary; drop passing noise.
# adapted from headroomlabs-ai/headroom crates/headroom-core/src/transforms/log_compressor.rs
# (Apache-2.0, Copyright 2025 Headroom Contributors), see NOTICE. Changed: ported to stdlib Python and simplified;
# unlike upstream, error/failure lines and traces are never capped. Pure stdlib.
import re, sys

MIN_LINES = 50    # upstream min_lines_for_ccr: shorter input is not worth a recall round-trip
MAX_RATIO = 0.5   # upstream min_compression_ratio_for_ccr: a smaller gain is not worth hiding text
MAX_WARNINGS = 20  # distinct warnings shown; the rest stay in the stored original
HEAD, TAIL = 3, 5  # orientation lines (command echo, final status)

_ANSI = re.compile(r'\x1b\[[0-9;?]*[ -/]*[@-~]')
# WHY substring match: a false keep costs a few chars, a false drop hides a failure (AssertionError, ENOENT, ...).
_ERR = re.compile(r'error|fail|fatal|critical|exception|traceback|panic|denied|time(?:d[ -]?)?out|segfault|segmentation fault'
                  r'|abort|killed|refused|unhandled|undefined reference|core dumped|not found|cannot |can\'t |could not'
                  r'|ERR!|\bE(?:NOENT|ACCES|PERM|ADDRINUSE|CONNRESET|MFILE)\b|^\s*not ok\b|[✕✖✗✘●]|^E\s|\*\*\*', re.I)
_PY_PROGRESS_FAIL = re.compile(r'^(?:\S+\.py )?[.sxXpP]*[FE][.sxXpPFE]*(?:\s+\[ *\d+%\])?\s*$')
# only whole result lines of known runners: "ERROR expected state PASSED" must stay a failure
_PASS = re.compile(r'^[\w./\\-]+\.py::.* PASSED(?:\s+\[ *\d+%\])?\s*$|^(?:test )?\S+(?: \([\w.]+\))? \.\.\. ok\s*$|^\s*[✓✔√] ')
_WARN = re.compile(r'warn', re.I)
_QUIET = re.compile(r'\b(?:INFO|DEBUG|TRACE)\b')
_LEVEL = re.compile(r'\b(?:INFO|DEBUG|TRACE|WARN|WARNING|ERROR|FATAL|CRITICAL)\b')
_SUMMARY = re.compile(r'^(?:===|---|\d+ (?:passed|failed|skipped|error|warning)|(?:Tests?|Suites?|Test Suites):? +\d'
                      r'|TOTAL|Total|Summary|(?:Build|Compile|Test).*(?:succeeded|failed|complete)|test result:'
                      r'|(?:ok|FAIL)\s+\S+\s+[\d.]+s|added \d+ packages|\s*Finished |BUILD |Time:\s)')
_COMPILER = re.compile(r'^\s*(?:\S*/)?(?:gcc|g\+\+|clang|clang\+\+|cc|c\+\+|rustc|libtool)\s')
_FLAG = re.compile(r'(?<!\S)--?[A-Za-z][\w=,+-]*')
_CONT = re.compile(r'^(?:\s+\S|at |Caused by:|Suppressed:|--->|\d+ *\||\||= )')
_GO = re.compile(r'^(?:\s*$|\t|goroutine \d+|\[signal |created by |panic: |fatal error: |[\w./*()\[\]-]+\(.*\)$)')
_RUNTIME = re.compile(r'^\s*(?:at (?:java|jdk|sun|javax|scala|System|Microsoft)\.|at .*(?:node:internal/|node_modules/|\(internal/)'
                      r'|File ".*(?:site-packages/|lib/python3))')

FORMATS = {
    'pytest': r'^=+ (?:FAILURES|ERRORS|test session|short test summary)|(?:PASSED|FAILED|ERROR|SKIPPED) +\[|::\S+ (?:PASSED|FAILED)|^collected \d+',
    'npm': r'^npm (?:ERR!|WARN|warn|error|info|http)',
    'cargo': r'^\s*(?:Compiling|Finished|Running) |^warning: |^error\[E\d+|^test \S+ \.\.\. ',
    'jest': r'^\s*(?:PASS|FAIL) |^Test Suites:',
    'make': r'^make(?:\[\d+\])?:|^(?:gcc|g\+\+|clang) ',
}


def detect(lines):
    """Log format name, 'generic' for a levelled log, or None when the text is not a log."""
    sample = lines[:200] + lines[-200:]
    score = {f: sum(1 for l in sample if re.search(p, l)) for f, p in FORMATS.items()}
    best = max(score, key=score.get)
    if score[best] >= 2:
        return best
    # WHY: file listings and source dumps must never be treated as logs, so generic needs real level words
    return 'generic' if sum(1 for l in sample if _LEVEL.search(l)) * 2 >= len(sample) else None


def is_error(line):
    """True for a line that reports a failure."""
    if _PY_PROGRESS_FAIL.match(line) and line.strip():
        return True
    if _PASS.search(line):
        return False
    if _COMPILER.match(line):  # -Werror and friends are flags, not failures
        line = _FLAG.sub('', line)
    return bool(_ERR.search(line))


def _split(text):
    """Lines with ANSI removed; of carriage-return redraws keep the last, plus any that report a failure."""
    out = []
    for raw in _ANSI.sub('', text).split('\n'):
        if '\r' not in raw:
            out.append(raw); continue
        segs = [s for s in raw.split('\r') if s.strip()]
        out.extend([s for s in segs[:-1] if is_error(s)] + segs[-1:] or [''])
    return out


def _opens(line):
    """Name of the multi-line failure block this line starts, or None."""
    if re.match(r'^=+ (?:FAILURES|ERRORS|short test summary info) =+', line):
        return 'pytest'
    if 'Traceback (most recent call last)' in line:
        return 'py'
    if re.match(r'^\s*● ', line):
        return 'jest'
    if re.match(r'^failures:\s*$', line):
        return 'cargo'
    if re.match(r'^(?:panic: |fatal error: )', line):
        return 'go'
    return None


def _inside(block, line):
    """(line belongs to the block, block stays open)."""
    if block == 'pytest':
        other = line.startswith('===') and _opens(line) != 'pytest'
        return not other, not other
    if block == 'jest':
        end = re.match(r'^\s*(?:PASS|FAIL) |^Test Suites:', line)
        return not end, not end
    if block == 'cargo':
        end = line.startswith('test result:')
        return not end, not end
    if block == 'go':
        m = bool(_GO.match(line))
        return m, m
    # python traceback: indented/blank/chain lines continue; the first other line is the exception and closes it
    more = not line.strip() or line[0] in ' \t' or line.startswith(('Traceback', 'During handling', 'The above exception'))
    return True, more


def failures(lines):
    """Indexes that must be kept: failure lines, their continuation lines, and whole failure blocks."""
    keep, block, cont = set(), None, False
    for i, l in enumerate(lines):
        if block:
            inc, still = _inside(block, l)
            if inc:
                keep.add(i)
            if not still:
                block, cont = None, inc
            if inc:
                continue
        new = _opens(l)
        if new:
            keep.add(i); block, cont = new, False
        elif is_error(l) or l.startswith(('During handling', 'The above exception')):
            keep.add(i); cont = True
        elif cont and _CONT.match(l) and not _QUIET.search(l) and not _PASS.search(l):
            keep.add(i)
        else:
            cont = False
    return keep


def dedupe_key(line):
    """Normalise numbers/addresses/paths only after the first ':' or '=' so distinct messages stay distinct."""
    m = re.search(r'[:=]', line)
    cut = m.start() if m else len(line)
    tail = re.sub(r'0x[0-9a-fA-F]+', 'ADDR', line[cut:])
    tail = re.sub(r'\d+', 'N', tail)
    return line[:cut] + re.sub(r'(?:/[\w.-]+)+/', '/PATH/', tail)


def warnings(lines, skip):
    """{index of first occurrence: times seen} for distinct warnings outside the kept failures."""
    first, count = {}, {}
    for i, l in enumerate(lines):
        if i not in skip and _WARN.search(l):
            k = dedupe_key(l.strip())
            first.setdefault(k, i); count[k] = count.get(k, 0) + 1
    return {first[k]: count[k] for k in list(first)[:MAX_WARNINGS]}


def collapse(lines, keep):
    """Drop the tail of long runs of runtime/library stack frames that carry no failure words."""
    run = []
    for i in range(len(lines) + 1):
        l = lines[i] if i < len(lines) else ''
        quiet = i in keep and not is_error(l)
        frame = quiet and _RUNTIME.match(l)
        # a Python frame owns the indented source line under it
        source = run and quiet and l.startswith('    ') and lines[run[-1]].lstrip().startswith('File ')
        if frame or source:
            run.append(i); continue
        if len(run) >= 4:
            keep -= set(run[2:])
        run = []
    return keep


def render(lines, keep, warns):
    """Kept lines in order; each hidden run becomes one counted marker."""
    out, last = [], -1
    for i in sorted(keep) + [len(lines)]:
        gap = i - last - 1
        if gap == 1:
            out.append(lines[last + 1])  # a marker would be longer than the line
        elif gap > 1:
            out.append(f'[tz: {gap} lines omitted]')
        if i < len(lines):
            out.append(lines[i] + (f' [tz: x{warns[i]} similar]' if warns.get(i, 0) > 1 else ''))
        last = i
    return '\n'.join(out)


def compress(text):
    """dict(text, format, chars_in, chars_out, lines_in, lines_omitted) or None. Caller must keep the original."""
    lines = _split(text)
    if len(lines) < MIN_LINES:
        return None
    fmt = detect(lines)
    if not fmt:
        return None
    must = failures(lines)
    warns = warnings(lines, must)
    n = len(lines)
    base = {i for i in range(n) if _SUMMARY.match(lines[i])} | set(range(HEAD)) | set(range(n - TAIL, n))
    # a deduped repeat must not slip back in as an "orientation" or summary line
    repeats = {i for i in range(n) if i not in must and _WARN.search(lines[i]) and i not in warns}
    for ctx in (3, 1, 0):  # adaptive budget: shrink context, never failures
        near = {j for i in must for j in range(max(0, i - ctx), min(n, i + ctx + 1))}
        keep = collapse(lines, must | set(warns) | ((base | near) - repeats))
        out = render(lines, keep, warns)
        if len(out) < len(text) * MAX_RATIO:
            return {'text': out, 'format': fmt, 'chars_in': len(text), 'chars_out': len(out),
                    'lines_in': n, 'lines_omitted': n - len(keep)}
    return None


def main(argv):
    """`tz logc [FILE]`: compress a build/test log (stdin without FILE); the original is stored for `tz recall`."""
    if argv[:1] in (['-h'], ['--help']) or len(argv) > 1:
        print('usage: tz logc [FILE]   (reads stdin without FILE)'); return 0 if argv[:1] in (['-h'], ['--help']) else 2
    try:
        raw = open(argv[0], 'rb').read() if argv else sys.stdin.buffer.read()
    except OSError as e:
        print(f'tz logc: {e}', file=sys.stderr); return 1
    try:
        text = raw.decode('utf-8')
        r = compress(text)
        if r:
            import tzout
            rid = tzout.spill(text)  # before printing: no marker may point at an unstored original
    except (UnicodeDecodeError, OSError) as e:
        r = None
        print(f'tz logc: not compressed ({type(e).__name__})', file=sys.stderr)
    if not r:
        sys.stdout.flush(); sys.stdout.buffer.write(raw); sys.stdout.flush()
        print(f'[MEASURED] unchanged: {len(raw)} bytes', file=sys.stderr)
        return 0
    out = f"{r['text']}\n[tz: {r['lines_omitted']} lines omitted, full: tz recall {rid}]"
    print(out)
    print(f"[MEASURED] {r['format']} log: {len(text)} -> {len(out)} chars", file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
