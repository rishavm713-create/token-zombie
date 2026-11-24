# Test stub with the py-tree-sitter shape TZ uses (Language, Parser.parse().root_node, node fields). Not tree-sitter itself.
import re
class N:
    def __init__(s, t, a, z, kids=(), body=None): s.type, s.start_byte, s.end_byte, s.children, s._b, s.has_error = t, a, z, list(kids), body, False
    def child_by_field_name(s, f): return s._b if f == 'body' else None
def Language(x): return x
class _T:
    def __init__(s, r): s.root_node = r
class Parser:
    def __init__(s, lang): pass
    def parse(s, b):
        kids = []
        for m in re.finditer(rb'function \w+\([^)]*\) (\{[^{}]*\})', b):
            kids.append(N('function_declaration', m.start(), m.end(), body=N('statement_block', m.start(1), m.end(1))))
        r = N('program', 0, len(b), kids); r.has_error = b'@@' in b; return _T(r)
