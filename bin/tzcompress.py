#!/usr/bin/env python3
# `tz compress FILE.py`: structural (AST) skeleton of a Python file: signatures, class layout and one docstring line, bodies -> "...".
# Validated: the result must parse and keep every class/function name; otherwise FAIL OPEN (the original is returned unchanged).
# Reversible: the full source is kept in the recall vault (`tz recall ID`). Never applied automatically.
import ast, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _names(t):
    return sorted(f'{type(n).__name__}:{n.name}' for n in ast.walk(t) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))


def skeleton(src):
    """(skeleton, ok). ok False => skeleton is the original source."""
    try:
        tree = ast.parse(src)
        want = _names(tree)

        class T(ast.NodeTransformer):
            def _fn(self, n):
                doc = ast.get_docstring(n)
                body = [ast.Expr(ast.Constant(doc.strip().split('\n')[0]))] if doc else []
                n.body = body + [ast.Expr(ast.Constant(...))]
                return n
            visit_FunctionDef = visit_AsyncFunctionDef = _fn

            def visit_ClassDef(self, n):
                self.generic_visit(n)
                return n
        out = ast.unparse(T().visit(tree))
        if _names(ast.parse(out)) != want:
            return src, False
        return out, True
    except Exception:
        return src, False


class _Bail(Exception):
    pass


_RX_PREV = set('(,=:[!&|?{};+-*%<>~^')
_RX_KW = {'return', 'typeof', 'case', 'delete', 'void', 'throw', 'in', 'of', 'new', 'else', 'do', 'yield', 'await', 'instanceof'}


def _js_tok(s, i, pc, pw):
    """If a string/template/comment/regex starts at s[i], return (end, kind); else None. Raises _Bail on anything unterminated."""
    n, c = len(s), s[i]
    if c in '"\'':
        k = i + 1
        while k < n and s[k] != c:
            if s[k] == '\n':
                raise _Bail
            k += 2 if s[k] == '\\' else 1
        if k >= n:
            raise _Bail
        return k + 1, 'str'
    if c == '`':
        k = i + 1
        while k < n:
            if s[k] == '\\':
                k += 2
            elif s[k] == '`':
                return k + 1, 'str'
            elif s.startswith('${', k):
                k = _js_bal(s, k + 2)
            else:
                k += 1
        raise _Bail
    if c == '/':
        if s.startswith('//', i):
            k = s.find('\n', i)
            return (n if k < 0 else k), 'cmt'
        if s.startswith('/*', i):
            k = s.find('*/', i + 2)
            if k < 0:
                raise _Bail
            return k + 2, 'cmt'
        if pc is None or pc in _RX_PREV or pw in _RX_KW:
            k, cls = i + 1, False
            while k < n:
                ch = s[k]
                if ch == '\n':
                    raise _Bail
                if ch == '\\':
                    k += 2; continue
                if ch == '[':
                    cls = True
                elif ch == ']':
                    cls = False
                elif ch == '/' and not cls:
                    return k + 1, 'str'
                k += 1
            raise _Bail
    return None


def _js_bal(s, j):
    """Index just past the `}` closing a `{` already consumed (j is after it); skips strings/comments/regex/templates."""
    n, d, pc, pw = len(s), 1, '{', ''
    while j < n:
        t = _js_tok(s, j, pc, pw) if s[j] in '"\'`/' else None
        if t:
            if t[1] == 'str':
                pc, pw = 'S', ''
            j = t[0]; continue
        c = s[j]
        if c == '{':
            d += 1
        elif c == '}':
            d -= 1
            if not d:
                return j + 1
        if not c.isspace():
            pw = (pw + c) if (c.isalnum() or c in '_$') and pw else (c if c.isalnum() or c in '_$' else '')
            pc = c
        j += 1
    raise _Bail


def _js_ok(s):
    """True when braces/parens/brackets in code (outside strings, comments, regex) are balanced."""
    n, i, pc, pw, st = len(s), 0, None, '', []
    pair = {')': '(', ']': '[', '}': '{'}
    while i < n:
        t = _js_tok(s, i, pc, pw) if s[i] in '"\'`/' else None
        if t:
            if t[1] == 'str':
                pc, pw = 'S', ''
            i = t[0]; continue
        c = s[i]
        if c in '([{':
            st.append(c)
        elif c in pair:
            if not st or st.pop() != pair[c]:
                return False
        if not c.isspace():
            pw = (pw + c) if (c.isalnum() or c in '_$') and pw else (c if c.isalnum() or c in '_$' else '')
            pc = c
        i += 1
    return not st


TS_FUNCS = {'function_declaration', 'generator_function_declaration', 'method_definition', 'arrow_function', 'function_expression', 'function'}


def ts_skeleton(src, tsx=False):
    """(skeleton, ok) via tree-sitter when `tree_sitter` + `tree_sitter_typescript` are installed (OPTIONAL dep); None when absent
    or the parse has errors, so the caller falls back to the scanner. Function/method/arrow bodies become `{ ... }`."""
    try:
        import tree_sitter, tree_sitter_typescript as tst
        lang = tree_sitter.Language(tst.language_tsx() if tsx else tst.language_typescript())
        b = src.encode('utf-8')
        root = tree_sitter.Parser(lang).parse(b).root_node
    except Exception:
        return None
    if root.has_error:
        return None
    cuts, todo = [], [root]
    while todo:
        nd = todo.pop()
        body = nd.child_by_field_name('body') if nd.type in TS_FUNCS else None
        if body is not None and body.type == 'statement_block':
            cuts.append((body.start_byte, body.end_byte))
        else:
            todo.extend(nd.children)
    out, last = [], 0
    for a, z in sorted(cuts):
        out.append(b[last:a]); out.append(b'{ ... }'); last = z
    out.append(b[last:])
    return b''.join(out).decode('utf-8'), True


def js_skeleton(src):
    """(skeleton, ok) for JS/TS with a small scanner (no parser, no deps). Skips strings, template literals (nested ${}), comments and regex literals.
    Bodies of functions, methods (getters/setters/static/TS modifiers/decorators), top-level arrow functions and `export default function` become `{ ... }`;
    interfaces, types, enums, imports and exports stay intact. Anything unscannable or unbalanced FAILS OPEN (original returned)."""
    import re
    sig = re.compile(r'(?:=>|\))\s*$|\)\s*:[^;{}?]*$')
    exc = re.compile(r'\b(?:interface|enum|namespace|class)\b|^\s*(?:export\s+)?(?:declare\s+)?(?:type|module)\s')
    ctl = re.compile(r'\s*(?:else\s+)?(?:if|for|while|switch|catch|with)\b')
    n, out, last, i, stack, par, pre, pc, pw = len(src), [], 0, 0, [], 0, '', None, ''
    try:
        while i < n:
            c = src[i]
            t = _js_tok(src, i, pc, pw) if c in '"\'`/' else None
            if t:
                if t[1] == 'str':
                    pc, pw, pre = 'S', '', pre + 'S'
                else:
                    pre += ' '
                i = t[0]; continue
            if c == '{':
                if not par and (not stack or stack[-1] == 'class') and sig.search(pre) and not exc.search(pre) and not ctl.match(pre):
                    j = _js_bal(src, i + 1)
                    out.append(src[last:i]); out.append('{ ... }'); last = i = j
                    pre, pc, pw = '', '}', ''
                    continue
                stack.append('class' if re.search(r'\bclass\b(?!\s*:)', pre) else 'other')
                if not par:
                    pre = ''
            elif c == '}':
                if not stack:
                    return src, False
                stack.pop()
                if not par:
                    pre = ''
            elif c in '([':
                par += 1; pre += c
            elif c in ')]':
                par -= 1; pre += c
                if par < 0:
                    return src, False
            elif c == ';' and not par:
                pre = ''
            else:
                pre += c
            if not c.isspace():
                pw = (pw + c) if (c.isalnum() or c in '_$') and pw else (c if c.isalnum() or c in '_$' else '')
                pc = c
            i += 1
        out.append(src[last:])
        sk = ''.join(out)
        if stack or par or not _js_ok(sk):
            return src, False
        return sk, True
    except (_Bail, RecursionError):
        return src, False


_OUT_RX = __import__('re').compile(r'^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:(?:def|class|function|func|fn|interface|type|struct|enum|impl|trait|module)\s|const\s+\w+\s*=\s*(?:async\s*)?\(|#{1,3}\s)')


def outline(path, cap=1200):
    """Line-numbered outline of a file ('L12 def foo(a, b)'), at most cap chars; '' if none. Python via ast
    (exact spans), other text via a definition-line regex. Used when a duplicate Read is denied: the model already
    holds the content, the outline tells it which offset/limit to read instead of the whole file again."""
    try:
        src = open(path, encoding='utf-8', errors='replace').read()
    except OSError:
        return ''
    rows = []
    if path.endswith('.py'):
        try:
            for n in ast.walk(ast.parse(src)):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    kind = 'class' if isinstance(n, ast.ClassDef) else 'def'
                    rows.append((n.lineno, f'L{n.lineno}-{getattr(n, "end_lineno", n.lineno)} {kind} {n.name}'))
        except Exception:
            rows = []
    if not rows:
        for i, l in enumerate(src.splitlines(), 1):
            if _OUT_RX.match(l) and (not l.lstrip().startswith('#') or path.endswith(('.md', '.markdown'))):
                rows.append((i, f'L{i} {l.strip()[:90]}'))
    out, n = [], 0
    for _, r in sorted(rows):
        if n + len(r) + 1 > cap:
            out.append(f'... (+{len(rows) - len(out)} more)')
            break
        out.append(r)
        n += len(r) + 1
    return '\n'.join(out)


def main(argv):
    JS = ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs')
    if not argv or not os.path.isfile(argv[0]) or not argv[0].endswith(('.py',) + JS):
        print('usage: tz compress FILE.py|.js|.ts  (other types NOT YET SUPPORTED)'); return 2
    src = open(argv[0], encoding='utf-8', errors='replace').read()
    sk, ok = (ts_skeleton(src, argv[0].endswith(('.tsx', '.jsx'))) or js_skeleton(src)) if argv[0].endswith(JS) else skeleton(src)
    if not ok:
        print(f'[TOKEN ZOMBIE: could not validate a skeleton, original kept] ({len(src):,} chars)'); return 1
    import tzout
    rid = tzout.spill(src)
    print(f'[TOKEN ZOMBIE skeleton of {argv[0]}: {len(src):,} -> {len(sk):,} chars (MEASURED); full source: tz recall {rid} --grep NAME]')
    print(sk)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
