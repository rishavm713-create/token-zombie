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


def js_skeleton(src):
    """(skeleton, ok) for JS/TS by brace matching (no parser): function/method/arrow bodies at top level or directly in a class -> `{ ... }`.
    Strings, comments and template literals are skipped while matching; imbalance or a lost function/class name FAILS OPEN (original returned)."""
    import re
    n, out, last, i, stack = len(src), [], 0, 0, []
    sig = re.compile(r'(?:\)\s*(?::\s*[^;{}=]+)?|=>)\s*$')
    ctl = re.compile(r'\b(?:if|for|while|switch|catch|with)\s*\([^{}]*$')
    names = lambda t: sorted(re.findall(r'\b(?:function|class)\s+([A-Za-z_$][\w$]*)', t))

    def skip(j):
        if src.startswith('//', j):
            k = src.find('\n', j); return n if k < 0 else k
        if src.startswith('/*', j):
            k = src.find('*/', j + 2); return n if k < 0 else k + 2
        k = j + 1
        while k < n and src[k] != src[j]:
            k += 2 if src[k] == '\\' else 1
        return k + 1
    skipping = lambda j: src[j] in '"\'`' or src.startswith('//', j) or src.startswith('/*', j)
    while i < n:
        if skipping(i):
            i = skip(i); continue
        c = src[i]
        if c == '{':
            pre = src[max(last, src.rfind(';', 0, i) + 1, src.rfind('}', 0, i) + 1, src.rfind('{', 0, i) + 1):i]
            if (not stack or stack[-1] == 'class') and sig.search(pre) and not ctl.search(pre):
                d, j = 1, i + 1
                while j < n and d:
                    if skipping(j):
                        j = skip(j); continue
                    d += (src[j] == '{') - (src[j] == '}'); j += 1
                if d:
                    return src, False
                out.append(src[last:i]); out.append('{ ... }'); last = i = j
                continue
            stack.append('class' if re.search(r'\b(?:class|interface)\b', pre) else 'other')
        elif c == '}':
            if stack:
                stack.pop()
        i += 1
    out.append(src[last:])
    sk = ''.join(out)
    if names(sk) != names(src) or stack:
        return src, False
    return sk, True


def main(argv):
    JS = ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs')
    if not argv or not os.path.isfile(argv[0]) or not argv[0].endswith(('.py',) + JS):
        print('usage: tz compress FILE.py|.js|.ts  (other types NOT YET SUPPORTED)'); return 2
    src = open(argv[0], encoding='utf-8', errors='replace').read()
    sk, ok = js_skeleton(src) if argv[0].endswith(JS) else skeleton(src)
    if not ok:
        print(f'[TOKEN ZOMBIE: could not validate a skeleton, original kept] ({len(src):,} chars)'); return 1
    import tzout
    rid = tzout.spill(src)
    print(f'[TOKEN ZOMBIE skeleton of {argv[0]}: {len(src):,} -> {len(sk):,} chars (MEASURED); full source: tz recall {rid} --grep NAME]')
    print(sk)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
