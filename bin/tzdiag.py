#!/usr/bin/env python3
"""tz diag FILE...: cheap post-edit check; prints one line per problem, nothing when clean (idea: Continuous-Claude-v3 post-edit diagnostics, MIT; own code).
Checks: .py (compile), .json (parse), .sh (bash -n), .js/.mjs (node --check, only if node exists). Exit 1 on any problem. Fail-open: unknown types pass."""
import json, os, shutil, subprocess, sys


def check(path):
    """Error text (one line) or ''."""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == '.py':
            compile(open(path, encoding='utf-8', errors='replace').read(), path, 'exec'); return ''
        if ext == '.json':
            json.load(open(path, encoding='utf-8')); return ''
        cmd = {'.sh': ['bash', '-n'], '.js': ['node', '--check'], '.mjs': ['node', '--check']}.get(ext)
        exe = cmd and shutil.which(cmd[0])
        if not exe:
            return ''
        r = subprocess.run([exe] + cmd[1:] + [path], capture_output=True, text=True, timeout=10)
        return '' if r.returncode == 0 else ' '.join((r.stderr or r.stdout).split())[:200]
    except SyntaxError as e:
        return f'line {e.lineno}: {e.msg}'
    except (ValueError, OSError, subprocess.SubprocessError) as e:
        return str(e).split('\n')[0][:200]


def main(argv):
    bad = 0
    for f in argv:
        e = check(f)
        if e:
            bad += 1; print(f'{f}: {e}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
