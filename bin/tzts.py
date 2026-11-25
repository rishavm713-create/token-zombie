#!/usr/bin/env python3
# `tz ts`: tags (definitions/references), syntax check and skeletons through tree-sitter when it is installed, stdlib otherwise.
# Tag rules adapted from tree-sitter/tree-sitter crates/tags/src/tags.rs (MIT, Copyright (c) 2018 Max Brunsfeld), see NOTICE.
# Optional runtime use of py-tree-sitter (MIT, Copyright (c) 2019 Max Brunsfeld, GitHub). No grammar or query is bundled:
# TAGS_QUERY comes from whichever grammar package the user installed. Every tree-sitter failure falls back (fail open).
import ast, importlib, io, os, re, sys, tokenize
from collections import Counter

MAX_BYTES = 1_000_000  # WHY: a minified bundle costs seconds to parse and yields only noise
MAX_LINE = 180  # tags.rs MAX_LINE_LEN
EXT = {'.py': 'python', '.js': 'javascript', '.jsx': 'javascript', '.mjs': 'javascript', '.cjs': 'javascript',
       '.ts': 'typescript', '.tsx': 'tsx', '.sh': 'bash', '.go': 'go', '.rs': 'rust', '.java': 'java', '.rb': 'ruby',
       '.c': 'c', '.h': 'c', '.cc': 'cpp', '.cpp': 'cpp', '.hpp': 'cpp', '.cs': 'c_sharp', '.php': 'php'}
JSLIKE = ('javascript', 'typescript', 'tsx')
# lang -> (grammar module, function) where it differs from ('tree_sitter_<lang>', 'language')
GRAMMAR = {'typescript': ('tree_sitter_typescript', 'language_typescript'), 'tsx': ('tree_sitter_typescript', 'language_tsx'),
           'php': ('tree_sitter_php', 'language_php')}
# WHY: the TypeScript tags query only adds TS syntax; upstream layers the JavaScript query under it
EXTRA_TAGS = {'typescript': ('tree_sitter_javascript',), 'tsx': ('tree_sitter_javascript',)}
DEF_KINDS = {'class', 'function', 'method', 'interface', 'module', 'type', 'enum', 'macro', 'struct'}
OWNERS = {'class', 'interface', 'module', 'enum', 'struct'}
FUNC_NODES = {'function_declaration', 'method_declaration', 'function_item', 'function_definition', 'method_definition',
              'constructor_declaration', 'func_literal', 'closure_expression', 'lambda_expression'}
BLOCK_NODES = {'block', 'compound_statement', 'constructor_body'}
NOT_CALLS = {'if', 'for', 'while', 'switch', 'catch', 'function', 'return', 'typeof', 'await', 'with', 'super'}


def lang_of(path):
    """Language name for a path, or None."""
    return EXT.get(os.path.splitext(path)[1].lower())


def _load(lang):
    """(tree_sitter, Language, parser) when both optional packages work for `lang`, else None."""
    try:
        ts = importlib.import_module('tree_sitter')
        mod, fn = GRAMMAR.get(lang, ('tree_sitter_%s' % lang, 'language'))
        raw = getattr(importlib.import_module(mod), fn)()
        try:
            language = ts.Language(raw)
        except TypeError:  # py-tree-sitter <= 0.21 wants a name too
            language = ts.Language(raw, lang)
        try:
            parser = ts.Parser(language)
        except TypeError:  # <= 0.21: no constructor argument
            parser = ts.Parser()
            parser.set_language(language)
        return ts, language, parser
    except Exception:  # absent, ABI mismatch, broken wheel: all mean "use the fallback"
        return None


def parse(src, lang):
    """(root_node, source_bytes) from tree-sitter, or None."""
    got = _load(lang)
    if not got:
        return None
    try:
        b = src.encode('utf-8', 'replace')
        return got[2].parse(b).root_node, b
    except Exception:
        return None


def _matches(ts, language, query, root):
    """Query matches as [(pattern_index, {capture: [nodes]})] for both the 0.25+ and older APIs."""
    if hasattr(ts, 'QueryCursor'):
        found = ts.QueryCursor(ts.Query(language, query)).matches(root)
    else:
        found = language.query(query).matches(root)
    return [(i, {k: v if isinstance(v, list) else [v] for k, v in caps.items()}) for i, caps in found]


def _queries(lang):
    """TAGS_QUERY strings shipped by the installed grammar packages, most specific first."""
    out = []
    for mod in (GRAMMAR.get(lang, ('tree_sitter_%s' % lang,))[0],) + EXTRA_TAGS.get(lang, ()):
        try:
            q = getattr(importlib.import_module(mod), 'TAGS_QUERY', None)
        except Exception:
            q = None
        if q:
            out.append(q)
    return out


def _tag(name, role, kind, line, end, span, lines):
    """One tag record."""
    text = lines[line - 1].strip()[:MAX_LINE] if 0 < line <= len(lines) else ''
    return {'name': name, 'qual': name, 'role': role, 'kind': kind, 'line': line, 'end': end, 'span': span,
            'local': False, 'text': text}


def _from_match(caps, b, lines):
    """(name range, tag or None for @ignore) for one query match, or None when it is not a tag."""
    if caps.get('ignore'):
        n = caps['ignore'][0]
        return (n.start_byte, n.end_byte), None
    kinds = [k for k in caps if k.startswith(('definition.', 'reference.'))]
    if not caps.get('name') or not kinds:
        return None
    name, node = caps['name'][0], caps[kinds[-1]][0]
    if name.has_error:
        return None
    role, kind = kinds[-1].split('.', 1)
    span = (min(node.start_byte, name.start_byte), max(node.end_byte, name.end_byte))
    t = _tag(b[name.start_byte:name.end_byte].decode('utf-8', 'replace'), 'def' if role == 'definition' else 'ref', kind,
             name.start_point[0] + 1, node.end_point[0] + 1, span, lines)
    return (name.start_byte, name.end_byte), t


def _ts_tags(src, lang):
    """Tags from the grammar's TAGS_QUERY, or None when tree-sitter cannot serve this language."""
    got, queries = _load(lang), _queries(lang)
    if not got or not queries:
        return None
    try:
        b = src.encode('utf-8', 'replace')
        root = got[2].parse(b).root_node
    except Exception:
        return None
    lines, best, ran = src.split('\n'), {}, 0
    for qi, query in enumerate(queries):
        try:
            found = _matches(got[0], got[1], query, root)
            ran += 1
        except Exception:  # an inherited query may name nodes this grammar lacks
            continue
        for pi, caps in found:
            hit = _from_match(caps, b, lines)
            # one tag per name node; the earliest pattern wins (tags.rs)
            if hit and (hit[0] not in best or (qi, pi) < best[hit[0]][0]):
                best[hit[0]] = ((qi, pi), hit[1])
    if not ran:
        return None
    return _qualify([t for _, t in (best[k] for k in sorted(best)) if t])


def _qualify(tags):
    """Name definitions `Owner.member` by span nesting and mark those inside a function as local."""
    stack = []
    for t in sorted((t for t in tags if t['role'] == 'def'), key=lambda t: (t['span'][0], -t['span'][1])):
        while stack and not (stack[-1]['span'][0] <= t['span'][0] and t['span'][1] <= stack[-1]['span'][1]):
            stack.pop()
        if stack:
            t['qual'] = '.'.join([o['name'] for o in stack if o['kind'] in OWNERS] + [t['name']])
            t['local'] = any(o['kind'] in ('function', 'method') for o in stack)
        stack.append(t)
    return tags


def _py_tags(src):
    """Python tags from stdlib ast; raises on a syntax error."""
    lines, out = src.split('\n'), []

    def walk(node, pre, owner, local):
        for n in ast.iter_child_nodes(node):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                cls = isinstance(n, ast.ClassDef)
                kind = 'class' if cls else ('method' if owner else 'function')
                t = _tag(n.name, 'def', kind, n.lineno, n.end_lineno, None, lines)
                t['qual'], t['local'] = pre + n.name, local
                out.append(t)
                for base in (n.bases if cls else []):
                    ref(base, 'class')
                walk(n, pre + n.name + '.' if cls else pre, cls, local or not cls)
            else:
                if isinstance(n, ast.Call):
                    ref(n.func, 'call')
                walk(n, pre, owner, local)

    def ref(n, kind):
        name = getattr(n, 'id', None) or getattr(n, 'attr', None)
        if name:
            out.append(_tag(name, 'ref', kind, n.lineno, n.lineno, None, lines))
    walk(ast.parse(src), '', False, False)
    return sorted(out, key=lambda t: t['line'])


def _mask(src, lang):
    """Source with strings and comments blanked (newlines kept), so words inside them are never tags."""
    if lang == 'bash':
        return re.sub(r'(?m)(^|\s)#.*$', r'\1', src)
    if lang == 'python':
        return re.sub(r'(?m)#.*$', '', src)
    try:
        from tzcompress import _js_tok
        out, i, pc, pw = list(src), 0, None, ''
        while i < len(src):
            c = src[i]
            t = _js_tok(src, i, pc, pw) if c in '"\'`/' else None
            if t:
                out[i:t[0]] = [x if x == '\n' else ' ' for x in src[i:t[0]]]
                if t[1] == 'str':
                    pc, pw = 'S', ''
                i = t[0]
                continue
            if not c.isspace():
                word = c.isalnum() or c in '_$'
                pw, pc = (pw + c if word else ''), c
            i += 1
        return ''.join(out)
    except Exception:  # unterminated token: unmasked text beats no tags
        return src


RX_DEF = {
    'javascript': re.compile(r'(?m)^(?:[ \t]*(?:export[ \t]+)?(?:default[ \t]+)?(?:declare[ \t]+)?(?:abstract[ \t]+)?'
                             r'(?:async[ \t]+)?(?P<kw>function\*?|class|interface|type|enum)[ \t]+(?P<name>[A-Za-z_$][\w$]*)'
                             r'|(?:export[ \t]+)?const[ \t]+(?P<arrow>[A-Za-z_$][\w$]*)[ \t]*=[ \t]*(?:async[ \t]*)?(?:\(|function\b))'),
    'bash': re.compile(r'(?m)^[ \t]*(?:function[ \t]+(?P<arrow>[\w:-]+)|(?P<name>[\w:-]+)[ \t]*\(\))'),
    'python': re.compile(r'(?m)^[ \t]*(?:async[ \t]+)?(?P<kw>def|class)[ \t]+(?P<name>\w+)'),
}
RX_CALL = re.compile(r'(?<![\w$])([A-Za-z_$][\w$]*)[ \t]*\(')


def _rx_tags(src, lang):
    """Line-regex tags for JS/TS, shell and unparseable Python; None for other languages."""
    key = 'javascript' if lang in JSLIKE else lang
    if key not in RX_DEF:
        return None
    text, lines, out, named = _mask(src, lang), src.split('\n'), [], set()
    for m in RX_DEF[key].finditer(text):
        g = m.groupdict()
        name_group = 'name' if g.get('name') else 'arrow'
        kw = (g.get('kw') or 'function').rstrip('*')
        kind = 'function' if kw == 'def' else kw
        line = text.count('\n', 0, m.start(name_group)) + 1
        named.add(m.start(name_group))
        out.append(_tag(g[name_group], 'def', kind, line, line, None, lines))
    if lang in JSLIKE:
        for m in RX_CALL.finditer(text):
            # `name(...) {` is a method definition, not a call
            if m.start(1) in named or m.group(1) in NOT_CALLS or re.compile(r'[^()\n]*\)[ \t]*\{').match(text, m.end()):
                continue
            line = text.count('\n', 0, m.start()) + 1
            out.append(_tag(m.group(1), 'ref', 'call', line, line, None, lines))
    return sorted(out, key=lambda t: t['line'])


def _read(path):
    """File text, or None when missing, unreadable or over the size cap."""
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return None
        with open(path, encoding='utf-8', errors='replace') as f:
            return f.read()
    except OSError:
        return None


def tags(path, src=None):
    """(engine, tags) for a file; engine is 'tree-sitter', 'ast', 'regex' or 'none'. Never raises."""
    lang = lang_of(path)
    src = _read(path) if src is None else src
    if not lang or src is None or len(src) > MAX_BYTES:
        return 'none', []
    try:
        found = _ts_tags(src, lang)
        if found is not None:
            return 'tree-sitter', found
    except Exception:
        pass
    if lang == 'python':
        try:
            return 'ast', _py_tags(src)
        except Exception:
            pass
    try:
        found = _rx_tags(src, lang)
    except Exception:
        found = None
    return ('none', []) if found is None else ('regex', found)


def defs(path):
    """Drop-in for tzmap.defs_methods: same strings, tree-sitter when it can, otherwise exactly tzmap's answer."""
    engine, found = tags(path)
    if engine == 'tree-sitter':
        py = path.endswith('.py')
        out = [('class ' if py and t['kind'] == 'class' and t['qual'] == t['name'] else '') + t['qual']
               for t in found if t['role'] == 'def' and t['kind'] in DEF_KINDS and not t['local']]
        if out:
            return out
    import tzmap
    return tzmap.defs_methods(path)


def _leaf_words(root, b):
    """Counter of identifier leaf nodes, so strings and comments are never counted."""
    c, todo = Counter(), [root]
    while todo:
        n = todo.pop()
        if n.children:
            todo.extend(n.children)
        elif 'identifier' in n.type or n.type in ('constant', 'word', 'variable_name'):
            c[b[n.start_byte:n.end_byte].decode('utf-8', 'replace')] += 1
    return c


def words(src, lang):
    """Counter of code identifiers (no strings/comments), or None when this language cannot be tokenised."""
    got = parse(src, lang)
    if got:
        try:
            return _leaf_words(*got)
        except Exception:
            pass
    try:
        if lang == 'python':
            toks = tokenize.generate_tokens(io.StringIO(src).readline)
            return Counter(t.string for t in toks if t.type == tokenize.NAME)
        if lang in JSLIKE or lang == 'bash':
            return Counter(re.findall(r'[A-Za-z_]\w*', _mask(src, lang)))
    except Exception:
        pass
    return None


def _ts_errors(root):
    """[(line, message)] for ERROR and MISSING nodes."""
    out, todo = [], [root]
    while todo:
        n = todo.pop()
        missing = getattr(n, 'is_missing', False)
        if n.type == 'ERROR' or missing:
            out.append((n.start_point[0] + 1, 'missing %s' % n.type if missing else 'syntax error'))
        elif n.has_error:
            todo.extend(n.children)
    return sorted(out)


def errors(path, src=None):
    """(engine, [(line, message)]); engine 'none' means UNCHECKED, never 'clean'."""
    lang = lang_of(path)
    src = _read(path) if src is None else src
    if not lang or src is None or len(src) > MAX_BYTES:
        return 'none', []
    got = parse(src, lang)
    if got:
        try:
            return 'tree-sitter', _ts_errors(got[0])
        except Exception:
            pass
    if lang == 'python':
        try:
            ast.parse(src)
            return 'ast', []
        except SyntaxError as e:
            return 'ast', [(e.lineno or 0, e.msg)]
        except Exception:
            return 'none', []
    if lang in JSLIKE:  # weak check: bracket balance only
        try:
            from tzcompress import _Bail, _js_ok
        except Exception:
            return 'none', []
        try:
            good = _js_ok(src)
        except _Bail:
            good = False
        except Exception:
            return 'none', []
        return 'scanner', [] if good else [(0, 'unbalanced brackets or unterminated string/comment')]
    return 'none', []


def _ts_cut(src, lang):
    """Skeleton with brace function bodies cut, or None (absent grammar or parse errors)."""
    got = parse(src, lang)
    if not got or got[0].has_error:
        return None
    root, b = got
    cuts, todo = [], [root]
    while todo:
        n = todo.pop()
        body = n.child_by_field_name('body') if n.type in FUNC_NODES else None
        if body is not None and body.type in BLOCK_NODES and b[body.start_byte:body.start_byte + 1] == b'{':
            cuts.append((body.start_byte, body.end_byte))
        else:
            todo.extend(n.children)
    out, last = [], 0
    for a, z in sorted(cuts):
        out += [b[last:a], b'{ ... }']
        last = z
    return b''.join(out + [b[last:]]).decode('utf-8', 'replace')


def skeleton(src, lang):
    """(skeleton, ok); ok False means the source is returned unchanged. Python and JS/TS reuse tzcompress."""
    try:
        if lang == 'python' or lang in JSLIKE:
            import tzcompress as c
            if lang == 'python':
                return c.skeleton(src)
            return c.ts_skeleton(src, lang == 'tsx') or c.js_skeleton(src)
        out = _ts_cut(src, lang)
    except Exception:
        out = None
    return (src, False) if out is None else (out, True)


def doctor():
    """Lines saying which engine each language gets here."""
    try:
        from importlib.metadata import version
        importlib.import_module('tree_sitter')
        head = 'tree_sitter: installed %s' % version('tree-sitter')
    except Exception:
        head = 'tree_sitter: not installed or unreadable (optional; stdlib fallback in use). TZ installs nothing.'
    out = [head]
    for lang in sorted(set(EXT.values())):
        if _load(lang) and _queries(lang):
            how = 'tree-sitter'
        elif lang == 'python':
            how = 'ast'
        elif lang in JSLIKE or lang == 'bash':
            how = 'regex'
        else:
            how = 'none (needs the tree-sitter-%s package)' % lang.replace('_', '-')
        out.append('  %-11s tags: %s' % (lang, how))
    return out


def main(argv):
    """CLI: tz ts doctor | tags FILE [--refs] | check FILE | skel FILE."""
    if argv and argv[0] == 'ts':
        argv = argv[1:]
    if argv[:1] == ['doctor']:
        print('\n'.join(doctor()))
        return 0
    if len(argv) < 2 or argv[0] not in ('tags', 'check', 'skel') or not os.path.isfile(argv[1]):
        print('usage: tz ts doctor | tags FILE [--refs] | check FILE | skel FILE')
        return 2
    cmd, path = argv[0], argv[1]
    src = _read(path)
    if src is None:
        print('not read: unreadable or over %d bytes' % MAX_BYTES)
        return 2
    if cmd == 'tags':
        engine, found = tags(path, src)
        rows = [t for t in found if '--refs' in argv or t['role'] == 'def']
        for t in rows[:200]:
            print('L%d %s.%s %s' % (t['line'], t['role'], t['kind'], t['qual']))
        more = ', %d not shown' % (len(rows) - 200) if len(rows) > 200 else ''
        print('# %d tag(s) [actual]%s, engine: %s' % (len(rows), more, engine))
        return 0 if engine != 'none' else 2
    if cmd == 'check':
        engine, bad = errors(path, src)
        for line, msg in bad[:50]:
            print('L%d %s' % (line, msg))
        if engine == 'none':
            print('UNCHECKED: no parser for this file type')
            return 2
        print('# %d syntax error(s) [actual], engine: %s' % (len(bad), engine))
        return 1 if bad else 0
    out, good = skeleton(src, lang_of(path))
    if not good:
        print('no validated skeleton for this file; read it directly')
        return 1
    print(out)
    print('# %d -> %d chars [actual]' % (len(src), len(out)), file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
