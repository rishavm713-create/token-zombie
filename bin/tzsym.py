#!/usr/bin/env python3
"""`tz sym PATTERN`: find symbols by name path ("Class/method") and list real code references, with no language server."""
# Idea from oraios/serena (symbol lookup by name path, referencing symbols, file overview). Rebuilt from observed behaviour:
# no Serena code, prompts or docstrings. See third_party/serena/LICENSE and NOTICE.
import argparse, ast, io, os, re, sys, tokenize, warnings
import tzcompress as tc
from tzmap import _files, _rel

MAX_BYTES = 1000000  # WHY: minified bundles cost seconds to scan and are never what the caller is looking for
MAX_LINES, MAX_BODY, MAX_REFS = 60, 80, 30
EXT = {'.py': 'py', '.js': 'js', '.jsx': 'js', '.ts': 'js', '.tsx': 'js', '.mjs': 'js', '.cjs': 'js', '.sh': 'sh'}
TEST = re.compile(r'(^|/)(tests?|spec|__tests__)/|(^|/)test_|_test\.|\.spec\.|\.test\.')


# ---- source access

def lang_of(path):
    """'py' | 'js' | 'sh' from the extension, else from a shebang line, else None."""
    ext = os.path.splitext(path)[1].lower()
    if ext:
        return EXT.get(ext)
    try:
        with open(path, 'rb') as f:
            head = f.readline(200)
    except OSError:
        return None
    if not head.startswith(b'#!'):
        return None
    for rx, lang in ((rb'python', 'py'), (rb'\bnode\b', 'js'), (rb'\b(?:ba|z|da|k)?sh\b', 'sh')):
        if re.search(rx, head):
            return lang
    return None


def sources(root, notes):
    """Yield (relpath, lang, text) for every readable source file under root; oversize files are counted in notes."""
    for p in _files(root):
        lang = lang_of(p)
        if not lang:
            continue
        try:
            if os.path.getsize(p) > MAX_BYTES:
                notes['large'] += 1
                continue
            with open(p, encoding='utf-8-sig', errors='ignore') as f:
                yield _rel(p, root), lang, f.read()
        except OSError:
            continue


def node(name, kind, line, start, end):
    """One raw symbol-tree node (lines are 1-based; `line` holds the name, `start` includes decorators)."""
    return {'name': name, 'kind': kind, 'line': line, 'start': start, 'end': end, 'kids': []}


# ---- Python

def py_tree(src):
    """Symbol tree from stdlib ast; None when the file does not parse (caller reports it, never silently 'absent')."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            mod = ast.parse(src)
        out = []
        _py_scope(mod, out, True)
        return out
    except Exception:
        return None


def _py_scope(parent, out, keep_vars):
    """Collect defs under parent (also inside if/try/with blocks); module and class scopes keep first assignments too."""
    found, assigned = [], []

    def walk(n):
        for c in ast.iter_child_nodes(n):
            if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                found.append(c)
            elif keep_vars and isinstance(c, (ast.Assign, ast.AnnAssign)):
                targets = c.targets if isinstance(c, ast.Assign) else [c.target]
                assigned.extend((t.id, c) for t in targets if isinstance(t, ast.Name))
            elif isinstance(c, (ast.stmt, ast.excepthandler)) or type(c).__name__ == 'match_case':
                walk(c)
    walk(parent)
    taken = {c.name for c in found}
    for c in found:
        cls = isinstance(c, ast.ClassDef)
        start = min([c.lineno] + [d.lineno for d in c.decorator_list])
        kind = 'class' if cls else ('method' if isinstance(parent, ast.ClassDef) else 'function')
        item = node(c.name, kind, c.lineno, start, c.end_lineno)
        _py_scope(c, item['kids'], cls)
        out.append(item)
    for name, stmt in assigned:
        if name not in taken:  # WHY: re-assignment is not a new symbol and would create noisy [i] duplicates
            taken.add(name)
            out.append(node(name, 'variable', stmt.lineno, stmt.lineno, stmt.end_lineno))
    out.sort(key=lambda x: x['line'])


# ---- JavaScript / TypeScript

def _wordch(c):
    return c.isalnum() or c in '_$'


def mask_js(s):
    """JS/TS source with comments, strings and regex text blanked (newlines kept); `${...}` code stays visible."""
    out, i, pc, pw = list(s), 0, None, ''
    while i < len(s):
        c, t = s[i], None
        # WHY: `</a>`, `/>` and "Don't" in JSX are not the start of a regex or a string
        jsx = (c == '/' and (s[i - 1:i] == '<' or s.startswith('/>', i))) or \
              (c == "'" and i and s[i - 1].isalnum() and pw not in tc._RX_KW)
        if c in '"\'`/' and not jsx:
            try:
                t = tc._js_tok(s, i, pc, pw)
                if t:
                    _blank(s, out, i, t[0])
            except (tc._Bail, RecursionError):
                t = None  # unterminated: treat as an ordinary character
        if t:
            if t[1] == 'str':
                pc, pw = 'S', ''
            i = t[0]
            continue
        if not c.isspace():
            if _wordch(c):
                pw = pw + c if i and _wordch(s[i - 1]) else c
            else:
                pw = ''
            pc = c
        i += 1
    return ''.join(out)


def _blank(s, out, a, z):
    """Overwrite s[a:z] with spaces in out, keeping newlines and the code inside template `${...}`."""
    k = a
    while k < z:
        if s[a] == '`' and s[k] == '\\':
            out[k:k + 2] = [x if x == '\n' else ' ' for x in s[k:k + 2]]
            k += 2
            continue
        if s[a] == '`' and s.startswith('${', k):
            e = tc._js_bal(s, k + 2)
            out[k:k + 2] = '  '
            out[k + 2:e - 1] = mask_js(s[k + 2:e - 1])
            out[e - 1] = ' '
            k = e
            continue
        if out[k] != '\n':
            out[k] = ' '
        k += 1


_LEAD = r'(?m)(?:^|(?<=[;{}]))[ \t]*'
JS_DECL = re.compile(_LEAD + r'(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:abstract\s+)?(?:async\s+)?'
                     r'(function\b\s*\*?|class\b|interface\b|enum\b|namespace\b|type\b|const\s+enum\b|const\b|let\b|var\b)'
                     r'\s*([A-Za-z_$][\w$]*)')
# WHY: no two adjacent optional space runs; masked strings leave long blanks that would backtrack for minutes
JS_MEMBER = re.compile(_LEAD + r'(?:(?:public|private|protected|static|readonly|override|abstract|async|get|set|declare|accessor)\s+)*'
                       r'(?:\*[ \t]*)?(#?[A-Za-z_$][\w$]*)(?:[ \t]*[?!])?(?:[ \t]*<[^()\n]*>)?[ \t]*(\(|=(?!=)|:|;|$)')
JS_FUNCVAL = re.compile(r'[^=;\n]*=\s*(?:async\s*)?(?:function\b|\(|<|[A-Za-z_$][\w$]*\s*=>)')


def _depths(m):
    """Per-character (brace depth, paren+bracket depth) before that character."""
    br, pa, b, p = [], [], 0, 0
    for c in m:
        br.append(b)
        pa.append(p)
        if c == '{':
            b += 1
        elif c == '}':
            b -= 1
        elif c in '([':
            p += 1
        elif c in ')]':
            p -= 1
    return br, pa


def _js_end(m, i, braced):
    """Offset of the last character of the declaration starting at i (braced: ends with its `{...}` body)."""
    d, n = 0, len(m)
    while i < n:
        c = m[i]
        if c in '([' or (c == '{' and (not braced or d)):
            d += 1
        elif c == '{':
            j = _close(m, i)
            rest = m[j + 1:j + 200].lstrip()
            if not rest.startswith('{'):  # WHY: `f(): {a: number} {` has a type literal before the body
                return j
            i = j
        elif c in ')]}':
            if not d:
                return i - 1
            d -= 1
        elif c == ';' and not d:
            return i
        elif c == '\n' and not d and not braced:
            before, after = m[max(0, i - 200):i].rstrip(), m[i:i + 200].lstrip()
            if before[-1:] not in tuple('=,+-*/&|?:(.>') and after[:1] not in tuple('.?:&|{'):
                return i
        i += 1
    return n - 1


def _close(m, i):
    """Offset of the `}` matching the `{` at i (end of text when unbalanced)."""
    d = 0
    for j in range(i, len(m)):
        if m[j] == '{':
            d += 1
        elif m[j] == '}':
            d -= 1
            if not d:
                return j
    return len(m) - 1


def js_tree(src):
    """Symbol tree for JS/TS from a masked-text scan: declarations plus class and interface members."""
    m = mask_js(src)
    br, pa = _depths(m)
    cands = {x.start(2): (x, True) for x in JS_DECL.finditer(m)}
    for x in JS_MEMBER.finditer(m):
        cands.setdefault(x.start(1), (x, False))
    top, stack, pos, line = [], [], 0, 1
    for off in sorted(cands):
        x, decl = cands[off]
        while stack and off > stack[-1][0]:
            stack.pop()
        owner = stack[-1][1] if stack else None
        if decl:
            kind, name = ' '.join(x.group(1).replace('*', '').split()), x.group(2)
            if kind in ('const', 'let', 'var'):
                if owner and owner['kind'] != 'namespace' and not JS_FUNCVAL.match(m, x.end()):
                    continue  # plain local variables are not symbols
                kind = 'variable'
        else:
            if not owner or owner['kind'] not in ('class', 'interface') or br[off] != stack[-1][2] or pa[off]:
                continue
            name, kind = x.group(1), 'method' if x.group(2) == '(' else 'field'
        braced = kind in ('function', 'class', 'interface', 'enum', 'const enum', 'namespace') or \
            (kind == 'method' and owner['kind'] == 'class')
        end = _js_end(m, x.end(1) if not decl else x.end(2), braced)
        line += m.count('\n', pos, off)
        pos = off
        item = node(name, kind, line, line, line + m.count('\n', off, max(off, end)))
        (owner['kids'] if owner else top).append(item)
        stack.append((end, item, br[off] + 1))
    return top


# ---- shell

SH_DEF = re.compile(r'^(\s*)(?:function\s+([\w:.-]+)(?:\s*\(\))?|([A-Za-z_][\w:.-]*)\s*\(\))\s*(\{.*)?$')


def sh_tree(src):
    """Shell functions; a body ends at the first `}` line with the definition's indent."""
    lines, out = src.split('\n'), []
    for i, text in enumerate(lines):
        x = SH_DEF.match(text)
        if not x:
            continue
        end = i
        if not (x.group(4) or '').rstrip().endswith('}'):
            closer = x.group(1) + '}'
            end = next((j for j in range(i + 1, len(lines)) if lines[j].startswith(closer)), i)
        out.append(node(x.group(2) or x.group(3), 'function', i + 1, i + 1, end + 1))
    return out


TREES = {'py': py_tree, 'js': js_tree, 'sh': sh_tree}


# ---- name paths

def flatten(tree, rel, prefix=()):
    """Depth-first symbols; each gets `parts` = ((name, index|None), ...), index only for same-named siblings."""
    count, seen, out = {}, {}, []
    for n in tree:
        count[n['name']] = count.get(n['name'], 0) + 1
    for n in tree:
        name = n['name']
        idx = seen.get(name, 0) if count[name] > 1 else None
        seen[name] = seen.get(name, 0) + 1
        s = dict(n, file=rel, parts=prefix + ((name, idx),))
        out.append(s)
        out.extend(flatten(n['kids'], rel, s['parts']))
    return out


def name_path(sym):
    """'Class/method[1]' for a flattened symbol."""
    return '/'.join(n if i is None else '%s[%d]' % (n, i) for n, i in sym['parts'])


def parse_pattern(pattern):
    """(anchored, [(name, index|None)]) from 'name', 'A/b', '/A/b' or 'A/b[1]'."""
    comps = []
    for c in pattern.strip('/').split('/'):
        x = re.match(r'(.*?)(?:\[(\d+)\])?$', c)
        comps.append((x.group(1), None if x.group(2) is None else int(x.group(2))))
    return pattern.startswith('/'), comps


def matches(pattern, parts, substr=False):
    """True when the pattern names the symbol: suffix match, leading '/' = full path, substr loosens the last name only."""
    anchored, comps = parse_pattern(pattern)
    if not comps[-1][0] or len(parts) < len(comps) or (anchored and len(parts) != len(comps)):
        return False
    for k, ((want, wi), (have, hi)) in enumerate(zip(comps, parts[-len(comps):])):
        loose = substr and k == len(comps) - 1
        if not (want in have if loose else want == have):
            return False
        if wi is not None and wi != hi:
            return False
    return True


def index(root, notes):
    """[(relpath, lang, text, flat symbols)] for the whole tree; unparsed Python files are counted in notes."""
    out = []
    for rel, lang, text in sources(root, notes):
        try:
            tree = TREES[lang](text)
        except RecursionError:
            tree = None
        if tree is None:
            notes['unparsed'] += 1
        out.append((rel, lang, text, flatten(tree or [], rel)))
    return out


def within(rel, scope):
    """True when rel is the scoped file or sits under the scoped directory."""
    return scope in (None, '.', '') or rel == scope or rel.startswith(scope + '/')


def find(files, pattern, substr=False, scope=None):
    """Symbols matching the pattern (all top-level symbols of the scope when pattern is None)."""
    return [s for rel, _, _, syms in files if within(rel, scope) for s in syms
            if (len(s['parts']) == 1 if pattern is None else matches(pattern, s['parts'], substr))]


# ---- references

def py_hits(src, names):
    """[(line, name)] for identifier tokens only, so comments and strings never count; def/class names are skipped."""
    out, prev = [], ''
    try:
        for t in tokenize.generate_tokens(io.StringIO(src).readline):
            if t.type == tokenize.NAME:
                if t.string in names and prev not in ('def', 'class'):
                    out.append((t.start[0], t.string))
                prev = t.string
            elif t.type == tokenize.OP:
                prev = t.string
        return out
    except (tokenize.TokenError, SyntaxError, ValueError):
        return word_hits(strip_hash(src), names, r'\w')  # broken file: best effort, comments still removed


def strip_hash(src):
    """Drop `#` comments (not inside quotes on the same line), keeping line numbers."""
    rx = re.compile(r'''("(?:\\.|[^"\\])*"|'[^']*')|(?<![^\s;&|(])#.*''')
    return '\n'.join(rx.sub(lambda x: x.group(1) or '', line) for line in src.split('\n'))


def word_hits(code, names, wordclass):
    """[(line, name)] whole-word matches, with wordclass saying which characters extend a word."""
    rx = re.compile(r'(?<![%s])(%s)(?![%s])' % (wordclass, '|'.join(map(re.escape, sorted(names))), wordclass))
    return [(i, x.group(1)) for i, line in enumerate(code.split('\n'), 1) for x in rx.finditer(line)]


def refs(files, names):
    """[(file, line, enclosing name path, text)] where a name is used in code, declarations excluded."""
    out = []
    for rel, lang, text, syms in files:
        if not any(n in text for n in names):
            continue
        if lang == 'py':
            hits = py_hits(text, names)
        elif lang == 'js':
            hits = word_hits(mask_js(text), names, r'\w$')
        else:
            hits = word_hits(strip_hash(text), names, r'\w\-')
        # WHY: py already skips `def X`; every other declaration owns the first hit on its line
        decls = {(s['line'], s['name']) for s in syms if lang != 'py' or s['kind'] == 'variable'}
        lines, done = text.split('\n'), set()
        for no, name in hits:
            if (no, name) in decls:
                decls.discard((no, name))
                continue
            if no in done:
                continue
            done.add(no)
            holders = [s for s in syms if s['start'] <= no <= s['end']]
            holder = name_path(max(holders, key=lambda s: len(s['parts']))) if holders else ''
            out.append((rel, no, holder, lines[no - 1].strip()[:160]))
    return out


# ---- output

def row(s):
    """One definition line: name path, kind, file and line range."""
    return '%s  %s  %s:%d-%d' % (name_path(s), s['kind'], s['file'], s['start'], s['end'])


def listing(found, files, depth):
    """Definition rows, each followed by its descendants down to `depth` levels."""
    flat = {rel: syms for rel, _, _, syms in files}
    out = []
    for s in found:
        out.append(row(s))
        k = len(s['parts'])
        out.extend('  ' * (len(c['parts']) - k) + row(c) for c in flat[s['file']]
                   if k < len(c['parts']) <= k + depth and c['parts'][:k] == s['parts'])
    return out


def bodies(found, files):
    """Source of each match under a header row, about MAX_BODY lines in total."""
    text = {rel: t.split('\n') for rel, _, t, _ in files}
    out, left = [], MAX_BODY
    for s in found:
        if left <= 0:
            out.append('... %d more match(es) not shown; narrow with --in or a longer name path' % (len(found) - found.index(s)))
            break
        n = s['end'] - s['start'] + 1
        take = min(n, left)
        out.append(row(s))
        out.extend('%5d  %s' % (s['start'] + i, line[:200])
                   for i, line in enumerate(text[s['file']][s['start'] - 1:s['start'] - 1 + take]))
        if take < n:
            out.append('... cut at %d of %d lines; read %s:%d-%d' % (take, n, s['file'], s['start'] + take, s['end']))
        left -= take + 1  # WHY: header rows count too, or many tiny matches would escape the cap
    return out


def ref_report(hits, names):
    """References grouped by file with test files flagged; MAX_REFS rows."""
    nfiles = len({h[0] for h in hits})
    out = ['references to %s: %d line(s) in %d file(s) [actual]; matched by name, not by type'
           % (', '.join(sorted(names)[:5]), len(hits), nfiles)]
    last = None
    for rel, no, holder, text in hits[:MAX_REFS]:
        if rel != last:
            out.append(rel + (' [test]' if TEST.search(rel) else ''))
            last = rel
        out.append('  %d%s: %s' % (no, ' in ' + holder if holder else '', text))
    if len(hits) > MAX_REFS:
        out.append('... %d more reference line(s) not shown' % (len(hits) - MAX_REFS))
    tests = sorted({h[0] for h in hits if TEST.search(h[0])})
    out.append('tests among them: ' + (', '.join(tests[:10]) or 'none'))
    return out


def clip(lines, cap):
    """At most cap lines, saying how many were dropped."""
    if len(lines) <= cap:
        return lines
    return lines[:cap - 1] + ['... %d more line(s) not shown; narrow with --in or a longer name path' % (len(lines) - cap + 1)]


def parser():
    """Command line of `tz sym`."""
    p = argparse.ArgumentParser(prog='tz sym', description='Find symbols by name path and their references (no language server).')
    p.add_argument('pattern', nargs='?', help='name, Class/method, /Class/method (full path) or Class/method[1]')
    p.add_argument('--in', dest='scope', metavar='PATH', help='only definitions in this file or folder; alone: file overview')
    p.add_argument('--depth', type=int, default=0, help='also list members this many levels down')
    p.add_argument('--substr', action='store_true', help='last name of the pattern may be a substring')
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--body', action='store_true', help='print the source of each match')
    mode.add_argument('--refs', action='store_true', help='code lines using the name (comments and strings excluded)')
    return p


def main(argv):
    """Run `tz sym ...` in the current folder; 0 found, 1 nothing, 2 bad usage."""
    p = parser()
    try:
        a = p.parse_args(argv)
        if a.pattern is None and a.scope is None:
            p.error('give a PATTERN or --in PATH')
        if a.pattern is None and a.refs:
            p.error('--refs needs a PATTERN')
    except SystemExit as e:
        return e.code
    root = os.getcwd()
    scope = None
    if a.scope:
        scope = _rel(os.path.abspath(a.scope), os.path.abspath(root))
    notes = {'large': 0, 'unparsed': 0}
    files = index(root, notes)
    found = find(files, a.pattern, a.substr, scope)
    out = bodies(found, files) if a.body else clip(listing(found, files, a.depth), MAX_LINES)
    code = 0 if found else 1
    if not found:
        out = ['no definition matches %s%s' % (a.pattern or scope, '' if a.substr or not a.pattern else ' (try --substr)')]
    if a.refs:
        # WHY: a name defined outside this tree (a library call) still has references worth listing
        last = parse_pattern(a.pattern)[1][-1][0]
        names = {s['name'] for s in found} or ({last} if last else set())
        hits = refs(files, names) if names else []
        out = clip(out, MAX_LINES // 3) + (ref_report(hits, names) if hits else ['no code references found'])
        code = 0 if found or hits else 1
    print('\n'.join(out))
    if notes['large'] or notes['unparsed']:
        print('not fully searched: %d file(s) over 1 MB skipped, %d unparsed file(s) have no symbols [actual]'
              % (notes['large'], notes['unparsed']))
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
