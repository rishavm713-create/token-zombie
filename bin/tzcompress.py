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


def main(argv):
    if not argv or not os.path.isfile(argv[0]) or not argv[0].endswith('.py'):
        print('usage: tz compress FILE.py  (Python files only; other types NOT YET SUPPORTED)'); return 2
    src = open(argv[0], encoding='utf-8', errors='replace').read()
    sk, ok = skeleton(src)
    if not ok:
        print(f'[TOKEN ZOMBIE: could not validate a skeleton, original kept] ({len(src):,} chars)'); return 1
    import tzout
    rid = tzout.spill(src)
    print(f'[TOKEN ZOMBIE skeleton of {argv[0]}: {len(src):,} -> {len(sk):,} chars (MEASURED); full source: tz recall {rid} --grep NAME]')
    print(sk)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
