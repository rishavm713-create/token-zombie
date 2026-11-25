#!/usr/bin/env python3
# `tz sg PATTERN [PATH...]`: structural code search. Python files use stdlib `ast`; other languages go to an
# `ast-grep` binary only if the user already installed one (never downloaded here).
# Metavariable grammar adapted from ast-grep crates/core/src/meta_var.rs and parity cases from
# crates/core/src/match_tree/mod.rs (MIT, Copyright (c) 2022 Herrington Darkholme), see NOTICE.
# The matcher itself is new: upstream matches tree-sitter nodes, this matches Python `ast` nodes.
import argparse, ast, itertools, json, os, re, shutil, subprocess, sys, textwrap, tokenize, warnings
from tzmap import _files

CAP = 50
WIDTH = 160
MAX_BYTES = 2_000_000
MAX_WILD = 6
# String literals are matched first so that "$A" inside quotes stays literal text.
LEX = re.compile(r'''(?P<str>(?:\'\'\'(?:\\.|[^\\])*?\'\'\'|"""(?:\\.|[^\\])*?"""|'(?:\\.|[^'\\\n])*'|"(?:\\.|[^"\\\n])*"))'''
                 r'''|(?<![A-Za-z0-9_$])(?P<mv>\$\$\$(?:[A-Z_][A-Z0-9_]*)?|\$\$?[A-Z_][A-Z0-9_]*)(?![A-Za-z0-9_$])''', re.S)
HOLE = re.compile(r'^__tzmv_([sm])_(\w*)__$')
# Fields that say nothing about code shape (load/store context, comments, u-prefix, AnnAssign parenthesis flag).
IGNORE = {'ctx', 'type_comment', 'kind', 'simple'}


class PatternError(ValueError):
    """The pattern is not valid Python after metavariable substitution."""


class Param(ast.AST):
    """One function parameter, so `$$$P` can span every parameter kind."""
    _fields = ('star', 'arg', 'annotation', 'default')


class Pair(ast.AST):
    """One dict entry, so `$$$` can span key/value pairs."""
    _fields = ('key', 'value')


def meta_var(src):
    """('single'|'multi', name or None) for a metavariable token, else None."""
    m = re.fullmatch(r'(\$\$\$|\$\$|\$)([A-Z_][A-Z0-9_]*)?', src)
    if not m or (m[1] != '$$$' and not m[2]):
        return None
    name = None if not m[2] or m[2].startswith('_') else m[2]
    return ('multi' if m[1] == '$$$' else 'single', name)


def _substitute(pattern):
    """Pattern with each metavariable replaced by a Python identifier."""
    def repl(m):
        if m['str']:
            return m['str']
        kind, name = meta_var(m['mv'])
        return f'__tzmv_{kind[0]}_{name or ""}__'
    return LEX.sub(repl, pattern)


def _parse(code):
    """ast.parse, retrying `$$$` after keywords/defaults as `**$$$` since Python rejects it positionally."""
    try:
        return ast.parse(code)
    except (SyntaxError, ValueError) as e:
        first = e
    spots = [m for m in re.finditer(r'(?<![\w*])__tzmv_m_\w*?__(?!\w)', code)]
    # Only the wildcards in argument position may take `**`, so try each small subset of them.
    for k in range(1, min(len(spots), MAX_WILD) + 1):
        for chosen in itertools.combinations(spots[:MAX_WILD], k):
            trial = code
            for m in reversed(chosen):
                trial = trial[:m.start()] + '**' + trial[m.start():]
            try:
                return ast.parse(trial)
            except (SyntaxError, ValueError):
                pass
    raise PatternError(f'pattern is not valid Python: {getattr(first, "msg", first)}')


def compile_pattern(pattern):
    """Template: one node (expression or statement) or a list of statements."""
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        body = _parse(_substitute(textwrap.dedent(pattern).strip())).body
    if not body:
        raise PatternError('pattern is empty')
    if len(body) > 1:
        return body
    return body[0].value if isinstance(body[0], ast.Expr) else body[0]


def _hole(x):
    """(kind, name) when x is a placeholder identifier string or Name node."""
    if isinstance(x, ast.Name):
        x = x.id
    m = HOLE.match(x) if isinstance(x, str) else None
    return (m[1], m[2]) if m else None


def _multi(item):
    """(kind, name) when a pattern list item is a `$$$` wildcard in any wrapper node."""
    x = item
    if isinstance(item, ast.Expr):
        x = item.value
    elif isinstance(item, ast.alias) and not item.asname:
        x = item.name
    elif isinstance(item, ast.keyword) and item.arg is None:
        x = item.value
    elif isinstance(item, Pair) and item.key is None:
        x = item.value
    elif isinstance(item, Param) and item.annotation is None and item.default is None and item.star in ('', '**'):
        x = item.arg
    elif isinstance(item, ast.withitem) and not item.optional_vars:
        x = item.context_expr
    h = _hole(x)
    return h if h and h[0] == 'm' else None


def _params(a):
    """Flatten ast.arguments into ordered Param nodes."""
    pos = [('p', x) for x in a.posonlyargs] + [('', x) for x in a.args]
    defaults = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
    rows = [(s, x, d) for (s, x), d in zip(pos, defaults)]
    rows += [('*', a.vararg, None)] if a.vararg else []
    rows += [('k', x, d) for x, d in zip(a.kwonlyargs, a.kw_defaults)]
    rows += [('**', a.kwarg, None)] if a.kwarg else []
    return [Param(star=s, arg=x.arg, annotation=x.annotation, default=d) for s, x, d in rows]


def _ordered(a, b):
    """Positional and keyword arguments merged back into source order."""
    return sorted(a + b, key=lambda n: (getattr(n, 'lineno', 0), getattr(n, 'col_offset', 0)))


def _view(n):
    """Comparable fields of a node, with split argument lists merged."""
    out = {f: getattr(n, f, None) for f in n._fields if f not in IGNORE}
    if isinstance(n, ast.Call):
        out['args'] = _ordered(out['args'], out.pop('keywords'))
    elif isinstance(n, ast.ClassDef):
        out['bases'] = _ordered(out['bases'], out.pop('keywords'))
    elif isinstance(n, ast.arguments):
        out = {'params': _params(n)}
    elif isinstance(n, ast.Dict):
        out = {'pairs': [Pair(key=k, value=v) for k, v in zip(n.keys, n.values)]}
    return out


def _key(x):
    """Context-free identity of a captured value; a bare name equals the same identifier string."""
    if isinstance(x, str):
        return x
    if isinstance(x, ast.Name):
        return x.id
    if isinstance(x, Param) and not (x.star or x.annotation or x.default):
        return x.arg
    if isinstance(x, ast.AST):
        return (type(x).__name__,) + tuple(_key(getattr(x, f, None)) for f in x._fields if f not in IGNORE)
    if isinstance(x, list):
        return tuple(_key(i) for i in x)
    return (type(x).__name__, repr(x))


def _bind(env, name, key, nodes):
    """New env with name bound, or None when an earlier binding differs."""
    if not name:
        return env
    if name in env:
        return env if env[name][0] == key else None
    return {**env, name: (key, nodes)}


def _match(p, c, env):
    """Env (dict of captures) when pattern value p matches candidate c, else None."""
    h = _hole(p)
    if h:
        # A multi wildcard in a single slot may match nothing; a single one needs a real node.
        if c is None and h[0] == 's':
            return None
        return _bind(env, h[1], _key(c), [c])
    # A lone `$X` parameter or statement stands for the whole parameter or statement.
    if isinstance(p, Param) and not (p.star or p.annotation or p.default):
        h = _hole(p.arg)
        if h:
            return _bind(env, h[1], _key(c), [c])
    if isinstance(p, ast.Expr) and isinstance(c, ast.stmt) and _hole(p.value):
        return _bind(env, _hole(p.value)[1], _key(c), [c])
    if isinstance(p, ast.AST):
        return _match_node(p, c, env) if type(p) is type(c) else None
    if isinstance(p, list):
        return _seq(p, c, env) if isinstance(c, list) else None
    return env if type(p) is type(c) and p == c else None


def _match_node(p, c, env):
    """Field-by-field match of two nodes of the same type."""
    want, got = _view(p), _view(c)
    for f, v in want.items():
        # Like upstream, an undecorated pattern also finds decorated definitions.
        if f == 'decorator_list' and not v:
            continue
        env = _match(v, got.get(f), env)
        if env is None:
            return None
    return env


def _seq(pats, cands, env, i=0, j=0):
    """Match pattern list against candidate list; `$$$` takes the shortest run that lets the rest match."""
    while i < len(pats):
        h = _multi(pats[i])
        if h:
            last = i == len(pats) - 1
            for end in ([len(cands)] if last else range(j, len(cands) + 1)):
                run = cands[j:end]
                e = _bind(env, h[1], _key(run), run)
                if e is not None:
                    e = _seq(pats, cands, e, i + 1, end)
                    if e is not None:
                        return e
            return None
        if j >= len(cands):
            return None
        env = _match(pats[i], cands[j], env)
        if env is None:
            return None
        i, j = i + 1, j + 1
    return env if j == len(cands) else None


def _candidates(template, tree):
    """Yield (first node, captures) for every match in a parsed module."""
    if isinstance(template, list):
        yield from _blocks(template, tree)
        return
    # A bare `$A` means "any expression", not every node in the tree.
    root = ast.expr if _hole(template) else type(template)
    for n in ast.walk(tree):
        if isinstance(n, root):
            env = _match(template, n, {})
            if env is not None:
                yield n, env


def _blocks(template, tree):
    """Multi-statement patterns: match consecutive statements inside any statement list."""
    tail = ast.Expr(value=ast.Name(id='__tzmv_m___'))
    pats = template + [tail]
    for n in ast.walk(tree):
        for _, block in ast.iter_fields(n):
            if not (isinstance(block, list) and block and isinstance(block[0], ast.stmt)):
                continue
            for k in range(1 if _multi(pats[0]) else len(block)):
                env = _seq(pats, block, {}, 0, k)
                if env is not None:
                    yield block[k], env


def _text(src, node):
    """Source text of a captured node (or the captured identifier itself)."""
    if isinstance(node, str):
        return node
    if isinstance(node, Param):
        return node.arg
    if isinstance(node, Pair):
        return ': '.join(filter(None, (_text(src, node.key), _text(src, node.value)))) if node.key else _text(src, node.value)
    if node is None:
        return ''
    return ' '.join((ast.get_source_segment(src, node) or '').split())


def search_source(template, src):
    """Sorted [(line, source line, {name: text})], one entry per matching line."""
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        tree = ast.parse(src)
    lines, hits = src.split('\n'), {}
    for node, env in _candidates(template, tree):
        line = node.lineno
        if line not in hits or node.col_offset < hits[line][0]:
            hits[line] = (node.col_offset, env)
    out = []
    for line in sorted(hits):
        caps = {k: ', '.join(_text(src, n) for n in v[1]) for k, v in sorted(hits[line][1].items())}
        out.append((line, lines[line - 1].strip(), caps))
    return out


def _is_python(path):
    """True for .py/.pyi files and extensionless scripts with a python shebang."""
    if path.endswith(('.py', '.pyi')):
        return True
    if os.path.splitext(path)[1]:
        return False
    try:
        with open(path, 'rb') as f:
            head = f.readline(100)
    except OSError:
        return False
    return head.startswith(b'#!') and b'python' in head


def _read(path):
    """Decoded source honouring the file's coding cookie."""
    with tokenize.open(path) as f:
        return f.read()


def _targets(paths):
    """Python files to scan: explicit files as given, directories walked with TZ's skip list."""
    seen = set()
    for p in paths:
        found = [p] if os.path.isfile(p) else (f for f in _files(p) if os.path.isfile(f) and _is_python(f))
        for f in found:
            f = os.path.normpath(f)
            if f not in seen:
                seen.add(f)
                yield f


def search(pattern, paths, cap=CAP):
    """(matches [(path, line, text, captures)], more_exist, skipped_file_count)."""
    template, out, skipped = compile_pattern(pattern), [], 0
    for f in _targets(paths):
        try:
            if os.path.getsize(f) > MAX_BYTES:
                skipped += 1
                continue
            found = search_source(template, _read(f))
        except (OSError, SyntaxError, ValueError, LookupError, RecursionError, MemoryError):
            skipped += 1
            continue
        for line, text, caps in found:
            if len(out) >= cap:
                return out, True, skipped
            out.append((f.replace(os.sep, '/'), line, text, caps))
    return out, False, skipped


def find_binary():
    """Path of an installed ast-grep, or None; `sg` is verified because Linux ships an unrelated `sg`."""
    for name in ('ast-grep', 'sg'):
        exe = shutil.which(name)
        if not exe:
            continue
        try:
            r = subprocess.run([exe, '--version'], capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            continue
        if r.stdout.startswith('ast-grep'):
            return exe
    return None


def external(pattern, lang, paths, cap=CAP):
    """Same tuple as search(), using the user's installed ast-grep for non-Python languages."""
    exe = find_binary()
    if not exe:
        raise PatternError(f'UNSUPPORTED: --lang {lang} needs an installed ast-grep binary (built in: python only)')
    cmd = [exe, 'run', f'--pattern={pattern}', f'--lang={lang}', '--json=compact', '--'] + list(paths)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace',
                           timeout=120, stdin=subprocess.DEVNULL)
        rows = json.loads(r.stdout)
        out = [(m['file'], m['range']['start']['line'] + 1, (m.get('lines') or m.get('text') or '').split('\n')[0].strip(), {})
               for m in rows[:cap]]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        raise PatternError('ast-grep failed or returned unreadable output')
    return out, len(rows) > cap, 0


def _clip(s):
    """Keep one output row short."""
    return s if len(s) <= WIDTH else s[:WIDTH - 3] + '...'


def main(argv):
    """CLI; exit 0 = matches, 1 = none, 2 = bad usage or pattern."""
    ap = argparse.ArgumentParser(prog='tz sg', description='Structural search: $A one node, $$$ARGS many, $_ anything.')
    ap.add_argument('pattern')
    ap.add_argument('paths', nargs='*')
    ap.add_argument('--lang', default='python')
    ap.add_argument('--max', type=int, default=CAP, dest='cap')
    ap.add_argument('--captures', action='store_true', help='show what each metavariable matched')
    try:
        a = ap.parse_intermixed_args(argv)
    except SystemExit as e:
        return int(e.code or 0)
    paths, cap = a.paths or ['.'], max(1, a.cap)
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        print(f'tz sg: no such path: {missing[0]}', file=sys.stderr)
        return 2
    try:
        if a.lang.lower() in ('py', 'python'):
            rows, more, skipped = search(a.pattern, paths, cap)
        else:
            # `./` stops a path that starts with "-" being read as an option.
            rows, more, skipped = external(a.pattern, a.lang, [p if not p.startswith('-') else './' + p for p in paths], cap)
    except PatternError as e:
        print(f'tz sg: {e}', file=sys.stderr)
        return 2
    for path, line, text, caps in rows:
        extra = '  {' + ', '.join(f'{k}={v}' for k, v in caps.items()) + '}' if a.captures and caps else ''
        print(f'{path}:{line}: {_clip(text)}{_clip(extra)}')
    tail = f'; capped at {cap}, more exist (--max N)' if more else ''
    tail += f'; {skipped} file(s) skipped (unparseable or over {MAX_BYTES} bytes)' if skipped else ''
    print(f'{len(rows)} matching line(s) [actual]{tail}')
    return 0 if rows else 1


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(errors='replace')
    sys.exit(main(sys.argv[1:]))
