#!/usr/bin/env python3
# `tz costly`: which kinds of tool output cost the most (MEASURED chars from your chat logs, tokens EST = chars/4), saved to costly.json so
# the policy hook warns before the same kind runs again. `tz noise`: proposed Read-deny rules for noise paths (dry run; --apply writes, with a backup).
import glob, json, os, re, sys
STATE = os.path.expanduser('~/.claude/token-zombie')
NOISE = ['Read(./node_modules/**)', 'Read(**/package-lock.json)', 'Read(**/yarn.lock)', 'Read(**/pnpm-lock.yaml)', 'Read(**/Cargo.lock)',
         'Read(**/poetry.lock)', 'Read(./dist/**)', 'Read(./build/**)', 'Read(./.next/**)', 'Read(./coverage/**)', 'Read(**/*.min.js)']


def kind(tool, ti):
    if tool != 'Bash':
        return tool
    c = re.sub(r'^\s*(cd\s+\S+\s*(&&|;)\s*)+', '', str((ti or {}).get('command') or '')).split('|')[0].split()
    c = [w for w in c if not re.match(r'^\w+=', w)]
    if not c:
        return 'Bash'
    return ' '.join(c[:2]) if c[0] in ('git', 'npm', 'pnpm', 'yarn', 'docker', 'kubectl', 'cargo', 'pip', 'python3 -m') and len(c) > 1 else c[0]


def txt(c):
    if isinstance(c, list):
        c = '\n'.join(x.get('text', '') for x in c if isinstance(x, dict))
    return c if isinstance(c, str) else ''


def scan(files):
    """{kind: [calls, chars]} from tool_use/tool_result pairs. MEASURED chars."""
    agg = {}
    for p in files:
        use = {}
        try:
            for ln in open(p, errors='replace'):
                if '"tool_use"' not in ln and '"tool_result"' not in ln:
                    continue
                try:
                    c = json.loads(ln).get('message', {}).get('content')
                except ValueError:
                    continue
                for b in c if isinstance(c, list) else []:
                    if not isinstance(b, dict):
                        continue
                    if b.get('type') == 'tool_use':
                        use[b.get('id')] = kind(b.get('name', ''), b.get('input'))
                    elif b.get('type') == 'tool_result' and b.get('tool_use_id') in use:
                        a = agg.setdefault(use[b['tool_use_id']], [0, 0])
                        a[0] += 1
                        a[1] += len(txt(b.get('content')))
        except OSError:
            pass
    return agg


def costly(n=15, write=True):
    files = sorted(glob.glob(os.path.expanduser('~/.claude/projects/*/*.jsonl')), key=os.path.getmtime, reverse=True)[:n]
    agg = scan(files)
    rows = sorted(agg.items(), key=lambda kv: -kv[1][1])[:10]
    if not rows:
        print('no tool results found in recent chats')
        return 0
    tot = sum(v[1] for v in agg.values()) or 1
    print(f'biggest tool outputs in the last {len(files)} chats [MEASURED chars, tokens EST = chars/4]:')
    for k, (c, ch) in rows:
        print(f'  {k:22} {c:5} calls  {ch // 4:>9,} tok  avg {ch // 4 // max(1, c):>6,} tok  {100 * ch // tot:>2}%')
    hot = {k: dict(n=c, avg_tok=ch // 4 // c) for k, (c, ch) in agg.items() if c >= 3 and ch // 4 // c >= 1500 and k != 'Read'}
    if write:
        try:
            os.makedirs(STATE, exist_ok=True)
            json.dump(hot, open(os.path.join(STATE, 'costly.json'), 'w'))
            print(f'{len(hot)} kinds averaging >= 1500 tok saved to costly.json: the policy hook now warns before the same command runs (cap its output with | head, --stat, or rtk). Advice only.')
        except OSError:
            pass
    return 0


def noise(cwd, apply=False):
    sp = os.path.join(cwd, '.claude', 'settings.json')
    try:
        cur = json.load(open(sp))
    except (OSError, ValueError):
        cur = {}
    have = set((cur.get('permissions') or {}).get('deny') or [])
    new = [r for r in NOISE if r not in have]
    print('noise-path Read rules (stops node_modules, lockfiles and build output from being read into the chat):')
    for r in NOISE:
        print(('  have ' if r in have else '  add  ') + r)
    if not new:
        print('nothing to add')
        return 0
    if not apply:
        print(f'DRY RUN. Apply to {sp} (backup .bak, edits only permissions.deny): tz noise --apply')
        return 0
    if os.path.exists(sp):
        open(sp + '.bak', 'w').write(open(sp).read())
    os.makedirs(os.path.dirname(sp), exist_ok=True)
    cur.setdefault('permissions', {}).setdefault('deny', []).extend(new)
    json.dump(cur, open(sp, 'w'), indent=2)
    print(f'added {len(new)} rules to {sp}; undo: restore {sp}.bak')
    return 0


def main(argv):
    c = argv[0] if argv else 'costly'
    rest = argv[1:]
    if c == 'noise':
        return noise(os.getcwd(), '--apply' in rest)
    return costly(write='--no-write' not in rest)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
