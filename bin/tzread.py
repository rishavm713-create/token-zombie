#!/usr/bin/env python3
# `tz read FILE [full|signatures|map|diff|lines A-B|task "words"|auto]`: read modes for one file.
# Behaviour adapted from yvgude/lean-ctx (Apache-2.0), see third_party/lean-ctx/NOTICE. Independent stdlib code.
# Every partial view says what it left out; when a mode cannot be applied the FULL text is printed with the reason.
# Credential files (tzshell's secret-path rules) are refused: nothing is printed or saved.
import ast, difflib, hashlib, os, re, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tzshell

AUTO_FULL = 8000  # auto: files up to this many chars are printed whole
WINDOW = 5        # task: context lines on each side of a match
USAGE = 'usage: tz read FILE [full|signatures|map|diff|lines A-B|task "words"|auto]'
IMPORT_RX = re.compile(r'(?:import|from|use|pub use|using|package|require|require_relative|source|\. |#include|extern crate|export\s[^=]*\bfrom)\b'
                       r'|(?:const|let|var)\s[^=]+=\s*require\(')


def _secret(path):
    for p in (os.path.abspath(path), os.path.realpath(path)):
        p = p.replace('\\', '/')  # Windows separators: the secret rules match '/'
        # tzshell._secret skips tokens containing whitespace (shell words); mask it so such paths are still checked
        q = re.sub(r'\s', '_', p)
        for v in (p, q, q.lower()):
            rule = tzshell._secret(v)
            if rule:
                return rule
    return None


def _lines(text):
    out = text.split('\n')
    if out and out[-1] == '':
        out.pop()
    return out


def _snap(path):
    key = hashlib.sha1(os.path.realpath(path).encode('utf-8', 'surrogateescape')).hexdigest()
    return os.path.join(os.path.expanduser('~'), '.claude', 'token-zombie', 'tzread', key + '.txt')


def _load_snap(path):
    try:
        with open(_snap(path), encoding='utf-8', newline='') as f:
            return f.read()
    except (OSError, UnicodeError):
        return None


def _save_snap(path, text):
    try:
        p = _snap(path)
        os.makedirs(os.path.dirname(p), mode=0o700, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p))  # created 0600
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
        os.replace(tmp, p)
    except (OSError, UnicodeError):
        print('tz read: could not save state; the next diff may be stale or unavailable', file=sys.stderr)


# Each mode returns (note, body), or raises Full(reason) to print the whole file.
class Full(Exception):
    pass


def signatures(path, text):
    import tzts
    lang = tzts.lang_of(path)
    if not lang:
        raise Full('no skeleton support for this file type')
    sk, good = tzts.skeleton(text, lang)
    if not good or len(sk) >= len(text):
        raise Full('no validated, smaller skeleton')
    note = f'signatures: function bodies omitted ({len(text)} -> {len(sk)} chars)'
    if lang == 'python':
        note += '; comments, formatting and docstring lines after the first are also omitted; line numbers do not apply'
    return note, sk


def _py_map(text):
    rows = []

    def walk(nodes):
        for n in nodes:
            if isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                rows.append((n.lineno, n.end_lineno))
            else:  # defs under top-level if/try/with are still top-level names
                for field in ('body', 'handlers', 'orelse', 'finalbody'):
                    walk(getattr(n, field, []))
    tree = ast.parse(text)
    walk(tree.body)
    src, out = text.split('\n'), []
    for a, z in rows:
        s = src[a - 1].strip()
        if s.startswith(('import ', 'from ')):
            out += [(i, src[i - 1]) for i in range(a, z + 1)]
        else:
            out.append((a, f'{src[a - 1]}  [ends L{z}]'))
    return out


def _other_map(path, text):
    import tzts
    src, rows = _lines(text), {}
    for i, line in enumerate(src):
        if IMPORT_RX.match(line):
            rows[i + 1] = line
            close = {'(': ')', '{': '}'}.get(line.rstrip()[-1:])
            if close:  # multi-line import: keep it whole
                for j in range(i + 1, len(src)):
                    rows[j + 1] = src[j]
                    if close in src[j]:
                        break
    for t in tzts.tags(path, text)[1]:
        n = t['line']
        # column 0 is the top-level test: the regex engine has no nesting information
        if t['role'] == 'def' and not t['local'] and 0 < n <= len(src) and src[n - 1][:1].strip():
            rows[n] = src[n - 1]
    return sorted(rows.items())


def file_map(path, text):
    rows = _py_map(text) if path.endswith(('.py', '.pyi')) else _other_map(path, text)
    if not rows:
        raise Full('no imports or top-level definitions found')
    total = len(_lines(text))
    note = (f'map: {len(rows)} of {total} lines listed (imports and top-level definitions found); all other lines omitted, '
            'including bodies and assignments' + ('' if path.endswith(('.py', '.pyi')) else '; detection is best-effort and indented definitions are omitted'))
    return note, '\n'.join(f'L{n}: {s.rstrip()}' for n, s in rows)


def diff(path, text, old):
    if old is None:
        raise Full('no earlier tz read of this file')
    if old == text:
        return f'diff: unchanged since the last tz read; all {len(_lines(text))} lines omitted (that read may have been partial)', ''
    body = '\n'.join(difflib.unified_diff(old.split('\n'), text.split('\n'), 'last tz read', 'now', lineterm=''))
    if len(body) >= len(text):
        raise Full('diff is not smaller than the file')
    return 'diff: changes since the last tz read (that read may have been partial); lines outside the hunks omitted', body


def line_range(text, spec):
    m = re.fullmatch(r'(\d+)-(\d+)', spec)
    src = _lines(text)
    if not m or not 1 <= int(m[1]) <= int(m[2]) or int(m[1]) > len(src):
        raise Full(f'invalid range {spec!r} for a {len(src)}-line file')
    a, z = int(m[1]), min(int(m[2]), len(src))
    gone = ([f'1-{a - 1}'] if a > 1 else []) + ([f'{z + 1}-{len(src)}'] if z < len(src) else [])
    return f'lines {a}-{z} of {len(src)}; omitted: {", ".join(gone) or "none"}', '\n'.join(src[a - 1:z])


def task(text, query):
    words = {w for w in re.findall(r'\w+', query.lower()) if len(w) > 2}
    if not words:
        raise Full('no search words of 3+ characters')
    src, spans = _lines(text), []
    for i, line in enumerate(src):
        low = line.lower()
        if any(w in low for w in words):
            a, z = max(0, i - WINDOW), min(len(src), i + WINDOW + 1)
            if spans and a <= spans[-1][1]:
                spans[-1][1] = z
            else:
                spans.append([a, z])
    if not spans:
        raise Full('no line matches the task words')
    if spans == [[0, len(src)]]:
        raise Full('matching windows cover the whole file')
    out, last = [], 0
    for a, z in spans:
        if a > last:
            out.append(f'[omitted lines {last + 1}-{a}]')
        out += [f'L{n + 1}: {src[n]}' for n in range(a, z)]
        last = z
    if last < len(src):
        out.append(f'[omitted lines {last + 1}-{len(src)}]')
    shown = sum(z - a for a, z in spans)
    return f'task: literal word matches +/-{WINDOW} lines, {shown} of {len(src)} lines shown; relevant lines without these words may be omitted', '\n'.join(out)


def main(argv):
    args = list(argv)
    if not args or args[0] in ('-h', '--help'):
        print(USAGE)
        return 0 if args else 2
    path, mode, rest = args[0], (args[1] if len(args) > 1 else 'auto'), args[2:]
    if mode not in ('full', 'signatures', 'map', 'diff', 'lines', 'task', 'auto') or (mode in ('lines', 'task')) != bool(rest) \
            or (mode == 'lines' and len(rest) != 1):
        print(USAGE)
        return 2
    rule = _secret(path)
    if rule:
        print(f'[TOKEN ZOMBIE: not reading {path}: credentials file ({rule})]')
        return 2
    if not os.path.isfile(path):
        print(f'tz read: not a regular file: {path}')
        return 1
    try:
        with open(path, 'rb') as f:
            raw = f.read()
    except OSError as e:
        print(f'tz read: {e}')
        return 1
    try:
        text = raw.decode('utf-8')
    except UnicodeError:
        text = raw.decode('utf-8', 'replace')
        print('tz read: file is not valid UTF-8; undecodable bytes are shown as replacement characters', file=sys.stderr)
    old = _load_snap(path)
    note, body = '', text
    try:
        if mode == 'auto' and len(text) > AUTO_FULL:
            note, body = signatures(path, text)
        elif mode == 'signatures':
            note, body = signatures(path, text)
        elif mode == 'map':
            note, body = file_map(path, text)
        elif mode == 'diff':
            note, body = diff(path, text, old)
        elif mode == 'lines':
            note, body = line_range(text, rest[0])
        elif mode == 'task':
            note, body = task(text, ' '.join(rest))
    except Full as e:
        note = f'{mode}: {e}; full text follows'
    except Exception as e:  # fail open
        note, body = f'{mode}: failed ({type(e).__name__}); full text follows', text
    if note:
        extra = '' if body == text else f'; full text: tz read {path} full'
        print(f'[TOKEN ZOMBIE read {note}{extra}]')
    sys.stdout.write(body if body == text or not body or body.endswith('\n') else body + '\n')
    _save_snap(path, text)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
