#!/usr/bin/env python3
# Public API compatibility for Python: compares the public functions, classes and methods of a file at HEAD with the working tree.
# Used by `tz gate` so a worker cannot silently change an existing public interface (rename/remove/reorder params, drop a default,
# replace named params with *args, add a required param). Python only (ast); JS/TS exports are NOT checked. Stdlib only.
import ast, os, subprocess, sys


def _sig(fn):
    a = fn.args
    pos = [x.arg for x in a.posonlyargs + a.args]
    nd = len(a.defaults)
    defaulted = set(pos[len(pos) - nd:]) if nd else set()
    kw = {x.arg: d is not None for x, d in zip(a.kwonlyargs, a.kw_defaults)}
    return {'pos': pos, 'def': defaulted, 'kw': kw, 'va': a.vararg is not None, 'kwa': a.kwarg is not None}


def sigs(src):
    """{qualified public name: signature dict | 'class'}. Methods of public classes count; __init__ is the constructor signature."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    out = {}
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith('_'):
            out[n.name] = _sig(n)
        elif isinstance(n, ast.ClassDef) and not n.name.startswith('_'):
            out[n.name] = 'class'
            for m in n.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and (not m.name.startswith('_') or m.name == '__init__'):
                    out['%s.%s' % (n.name, m.name)] = _sig(m)
    return out


def compare(old, new):
    """Breaking differences between two sigs() maps, as readable strings."""
    bad = []
    for k, o in old.items():
        n = new.get(k)
        if n is None:
            bad.append('removed public %s' % k); continue
        if o == 'class' or n == 'class':
            if o != n:
                bad.append('%s changed between class and function' % k)
            continue
        if n['pos'][:len(o['pos'])] != o['pos']:
            bad.append('%s(%s) -> (%s): positional parameters renamed, reordered or removed' % (k, ', '.join(o['pos']), ', '.join(n['pos']) + (', *args' if n['va'] else '')))
            continue
        lost = [p for p in o['pos'] if p in o['def'] and p not in n['def']]
        if lost:
            bad.append('%s: default removed for %s' % (k, ', '.join(lost)))
        extra = [p for p in n['pos'][len(o['pos']):] if p not in n['def']]
        if extra:
            bad.append('%s: new required parameter %s' % (k, ', '.join(extra)))
        newkw = [p for p, d in n['kw'].items() if not d and p not in o['kw']]
        if newkw:
            bad.append('%s: new required keyword-only parameter %s' % (k, ', '.join(newkw)))
        gone = [p for p in o['kw'] if p not in n['kw'] and not n['kwa']]
        if gone:
            bad.append('%s: keyword-only parameter removed: %s' % (k, ', '.join(gone)))
        if (o['va'] and not n['va']) or (o['kwa'] and not n['kwa']):
            bad.append('%s: *args/**kwargs removed' % k)
    return bad


def is_test_file(f):
    b = os.path.basename(f)
    return b.startswith('test_') or b.endswith('_test.py') or b == 'conftest.py' or '/tests/' in '/' + f or '/test/' in '/' + f


def check(files, cwd):
    """files: changed tracked paths. Compares each non-test .py file with its HEAD version. Returns list of problems."""
    bad = []
    for f in files:
        if not f.endswith('.py') or is_test_file(f):
            continue
        r = subprocess.run(['git', 'show', 'HEAD:' + f], cwd=cwd, capture_output=True, text=True)
        if r.returncode != 0:
            continue  # new file: nothing to break
        old = sigs(r.stdout)
        try:
            new_src = open(os.path.join(cwd, f)).read()
        except OSError:
            new_src = ''  # deleted
        new = sigs(new_src) if new_src else {}
        if old is None or new is None:
            continue  # unparsable: the syntax check reports it
        bad += ['%s: %s' % (f, b) for b in compare(old, new)]
    return bad


if __name__ == '__main__':
    p = subprocess.run(['git', 'diff', '--name-only', 'HEAD'], capture_output=True, text=True).stdout.split()
    b = check(p, os.getcwd())
    print('\n'.join(b) or 'public API unchanged')
    sys.exit(1 if b else 0)
