#!/usr/bin/env python3
# `tz map [dir]`: compact repo map (file -> top-level defs), the idea from Aider's repo-map, so a chat reads ~1 page instead of many files.
# `tz xcheck [--json FILE]`: cross-check tz token totals against ccusage (MIT, npm) if installed; never downloads anything itself.
import ast, glob, json, os, re, shutil, subprocess, sys
SKIP = {'.git', 'node_modules', 'dist', 'build', '.next', 'coverage', '__pycache__', '.venv', 'venv'}
JS = re.compile(r'^(?:export\s+)?(?:async\s+)?(?:function\s+(\w+)|class\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s*)?\()', re.M)


def defs(path):
    try:
        s = open(path, encoding='utf-8', errors='ignore').read()
    except Exception:
        return []
    if path.endswith('.py'):
        try:
            return [('class ' if isinstance(n, ast.ClassDef) else '') + n.name for n in ast.parse(s).body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        except Exception:
            return []
    if path.endswith(('.js', '.ts', '.tsx', '.jsx', '.mjs')):
        return [next(g for g in m.groups() if g) for m in JS.finditer(s)]
    return [m.group(1) for m in re.finditer(r'^(?:function\s+)?(\w+)\(\)\s*\{', s, re.M)] if path.endswith('.sh') else []


def build(root, limit=40):
    out = []
    for dp, dn, fn in os.walk(root):
        dn[:] = sorted(d for d in dn if d not in SKIP and not d.startswith('.'))
        for f in sorted(fn):
            d = defs(os.path.join(dp, f))
            if d:
                out.append('%s: %s' % (os.path.relpath(os.path.join(dp, f), root), ' '.join(d[:limit])))
    return '\n'.join(out)


def xcheck(argv):
    from tzusage import totals, find_transcript
    t = totals(find_transcript(os.getcwd()))
    mine = t['inp'] + t['out'] + t['cr'] + t['cw']
    print('tz   : %d tokens in the newest chat of this folder (MEASURED from the chat log)' % mine)
    raw = None
    if '--json' in argv:
        raw = json.load(open(argv[argv.index('--json') + 1]))
    elif shutil.which('ccusage'):
        raw = json.loads(subprocess.run(['ccusage', 'session', '--json'], capture_output=True, text=True, timeout=120).stdout or 'null')
    if raw is None:
        print('ccusage not installed. Cross-check: npm i -g ccusage, then tz xcheck (or tz xcheck --json file). Nothing was downloaded.')
        return 0
    rows = raw.get('sessions', raw) if isinstance(raw, dict) else raw
    tot = sum(int(r.get('totalTokens') or 0) for r in rows if isinstance(r, dict))
    print('ccusage: %d tokens over %d sessions (all chats, so only compare per session id)' % (tot, len(rows)))
    return 0


def main(argv):
    if argv and argv[0] == 'map':
        argv = argv[1:]
    if argv and argv[0] == 'xcheck':
        return xcheck(argv[1:])
    root = os.path.abspath(argv[0] if argv else '.')
    m = build(root)
    print(m)
    print('# ~%d tokens EST (chars/4)' % (len(m) // 4), file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
