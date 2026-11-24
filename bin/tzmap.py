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
    """Same session, same token categories: tz (chat log) vs ccusage. A gap is shown per category, never one blended total."""
    from tzusage import totals, find_transcript
    path = find_transcript(os.getcwd())
    sid = os.path.basename(path or '')[:-6]
    t = totals(path)
    mine = dict(input=t['inp'], output=t['out'], cacheRead=t['cr'], cacheWrite=t['cw'])
    print('tz       session %s: ' % (sid or '?') + ', '.join('%s %d' % kv for kv in mine.items()) + ' (MEASURED from the chat log)')
    raw = None
    if '--json' in argv:
        raw = json.load(open(argv[argv.index('--json') + 1]))
    elif shutil.which('ccusage'):
        raw = json.loads(subprocess.run(['ccusage', 'session', '--json'], capture_output=True, text=True, timeout=120).stdout or 'null')
    if raw is None:
        print('ccusage not installed. Cross-check: npm i -g ccusage, then tz xcheck (or tz xcheck --json file). Nothing was downloaded.')
        return 0
    rows = raw.get('sessions', raw) if isinstance(raw, dict) else raw
    row = next((r for r in rows if isinstance(r, dict) and sid and sid in str(r.get('sessionId') or r.get('session') or '')), None)
    if not row:
        print('ccusage has no row for session %s: cannot compare (no blended total shown on purpose).' % sid)
        return 1
    theirs = dict(input=row.get('inputTokens'), output=row.get('outputTokens'), cacheRead=row.get('cacheReadTokens'), cacheWrite=row.get('cacheCreationTokens'))
    bad = 0
    for k, v in mine.items():
        o = theirs[k]
        if o is None:
            print('  %-10s tz %d vs ccusage UNKNOWN (field missing)' % (k, v)); continue
        d = v - int(o)
        bad += abs(d) > max(1, 0.01 * max(v, int(o)))
        print('  %-10s tz %d vs ccusage %d  diff %+d%s' % (k, v, int(o), d, '' if abs(d) <= max(1, 0.01 * max(v, int(o))) else '  <- over 1%: check duplicate-message handling or a live chat still writing'))
    print('MATCH within 1%' if not bad else '%d categories differ' % bad)
    return 0 if not bad else 1


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
