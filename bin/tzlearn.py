#!/usr/bin/env python3
# `tz learn`: mine repeated tool failures from chat logs and propose corrections. Dry run by default; --apply writes a marked block
# into CLAUDE.local.md (or --target FILE). Local only, MEASURED from logs. Idea seen in Headroom `learn` (Apache-2.0); independent code.
# `tz learn capture|recall|check|review` is the verified-lesson loop in tzcompound.py.
import collections, glob, json, os, re, sys

B, E = '<!-- TZ-LEARN -->', '<!-- /TZ-LEARN -->'
_N = re.compile(r'\d+|0x[0-9a-f]+|/tmp/\S+|[0-9a-f]{8,}', re.I)


def mine(files, min_count=2):
    """[(count, tool, command, error)] repeated failures (same tool+command head and normalized error line), most frequent first."""
    c = collections.Counter(); ex = {}
    for f in files:
        use = {}
        try:
            for line in open(f, encoding='utf-8', errors='ignore'):
                if '"tool_use"' not in line and '"is_error"' not in line:
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                for b in (d.get('message') or {}).get('content') or []:
                    if not isinstance(b, dict):
                        continue
                    if b.get('type') == 'tool_use':
                        i = b.get('input') or {}
                        use[b.get('id')] = (b.get('name'), (i.get('command') or i.get('file_path') or i.get('pattern') or '')[:80].split('\n')[0])
                    elif b.get('type') == 'tool_result' and b.get('is_error'):
                        t = b.get('content')
                        t = ' '.join(x.get('text', '') for x in t if isinstance(x, dict)) if isinstance(t, list) else str(t or '')
                        e = _N.sub('#', next((l for l in t.split('\n') if l.strip() and not l.startswith('Exit code')), ''))[:120]
                        tool, cmd = use.get(b.get('tool_use_id'), ('?', ''))
                        if tool in ('?',) or len(e.replace('#', '').strip()) < 8 or e == '(empty)' or not e or 'user doesn\'t want' in e or 'rejected' in e.lower():
                            continue
                        k = (tool, _N.sub('#', cmd).split(' ')[0] if tool == 'Bash' else tool, e)
                        c[k] += 1; ex.setdefault(k, cmd)
        except OSError:
            continue
    return [(n, k[0], ex[k], k[2]) for k, n in c.most_common() if n >= min_count]


def rules(found, top=8):
    return [f"- `{t}` `{cmd}` failed {n}x with \"{err}\": check this before repeating it" for n, t, cmd, err in found[:top]]


def apply(path, lines):
    old = open(path, encoding='utf-8').read() if os.path.exists(path) else ''
    blk = B + '\n## Repeated failures (tz learn, from chat logs)\n' + '\n'.join(lines) + '\n' + E
    a, b = old.find(B), old.find(E)
    new = (old[:a] + blk + old[b + len(E):]) if a >= 0 and b > a else (old.rstrip('\n') + ('\n\n' if old else '') + blk + '\n')
    open(path, 'w', encoding='utf-8').write(new)


def main(argv):
    import tzcompound
    if argv and argv[0] in tzcompound.COMMANDS:
        return tzcompound.main(argv)
    root = os.path.expanduser('~/.claude/projects')
    cwd = os.getcwd()
    d = os.path.join(root, re.sub(r'[^A-Za-z0-9]', '-', cwd))
    files = glob.glob(os.path.join(d, '*.jsonl')) or glob.glob(os.path.join(root, '**', '*.jsonl'), recursive=True)
    found = mine(files)
    ls = rules(found)
    if not ls:
        print('tz learn: no repeated failures found in ' + str(len(files)) + ' log file(s)'); return 0
    print(f'tz learn [MEASURED from {len(files)} log file(s)]:\n' + '\n'.join(ls))
    tgt = argv[argv.index('--target') + 1] if '--target' in argv else 'CLAUDE.local.md'
    if '--apply' not in argv:
        print(f'Dry run. Add --apply to write this block into {os.path.abspath(tgt)} (only between its markers).'); return 0
    apply(tgt, ls); print('wrote ' + os.path.abspath(tgt)); return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
