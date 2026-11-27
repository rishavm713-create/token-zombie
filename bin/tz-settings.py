#!/usr/bin/env python3
"""Recommended Claude Code settings for Token Zombie (thinking budget, MCP tool search).
Adds only keys you have not set yourself, backs up settings.json first, never overwrites a value of yours.
Usage: tz settings [--dry-run] [--revert]   Env TZ_SETTINGS_AUTO=0 stops the automatic first-run apply.
Applies to NEW chats only."""
import json, os, shutil, sys, time

WANT = {'MAX_THINKING_TOKENS': '10000',          # simple work stops thinking at 10k; raise or delete for hard builds
        'ENABLE_TOOL_SEARCH': 'auto'}            # MCP tool definitions load on demand instead of every turn
# Auto-compact is NOT here: a window of 150000 makes Claude compact at ~118k and, on a machine with a big base context
# (many skills/MCP tools), it loops "Context window was full". Opt-in only: python3 bin/tz-autocompact.py
HOME = os.path.expanduser('~/.claude')
P = os.path.join(os.environ.get('CLAUDE_CONFIG_DIR') or HOME, 'settings.json')
MARK = os.path.join(HOME, 'token-zombie', 'settings-applied.json')


def apply(dry=False):
    s = json.load(open(P)) if os.path.exists(P) else {}  # a broken file raises: never overwrite what we cannot read
    env = s.setdefault('env', {})
    add = {k: v for k, v in WANT.items() if k not in env}
    if not add or dry:
        return add
    if os.path.exists(P):
        shutil.copy2(P, f"{P}.bak-tz-settings-{time.strftime('%Y%m%d-%H%M%S')}")
    env.update(add)
    tmp = P + '.tz-tmp'
    json.dump(s, open(tmp, 'w'), indent=2)
    json.load(open(tmp))
    os.replace(tmp, P)
    os.makedirs(os.path.dirname(MARK), exist_ok=True)
    json.dump(add, open(MARK, 'w'))
    return add


def revert():
    added = json.load(open(MARK)) if os.path.exists(MARK) else {}
    s = json.load(open(P))
    for k, v in added.items():
        if s.get('env', {}).get(k) == v:
            del s['env'][k]
    json.dump(s, open(P, 'w'), indent=2)
    os.remove(MARK) if os.path.exists(MARK) else None
    return added


def loop_warn():
    """Every session: a small auto-compact window makes Claude compact on every message ("Context window was full" loop)."""
    try:
        env = (json.load(open(P)).get('env') or {}) if os.path.exists(P) else {}
        w = os.environ.get('CLAUDE_CODE_AUTO_COMPACT_WINDOW') or env.get('CLAUDE_CODE_AUTO_COMPACT_WINDOW')
        if w and w.isdigit() and int(w) < 200000:
            return (f'TOKEN ZOMBIE WARNING: CLAUDE_CODE_AUTO_COMPACT_WINDOW={w} is below 200000 and can make Claude compact on every '
                    'message. Fix: delete that key (and CLAUDE_AUTOCOMPACT_PCT_OVERRIDE) from the "env" block of ' + P + ', or run: '
                    'python3 bin/tz-autocompact.py 200000')
    except Exception:
        pass
    return ''


def auto():
    """SessionStart: loop warning every time; recommended settings once per machine. Returns a note or ''."""
    w = loop_warn()
    if os.environ.get('TZ_SETTINGS_AUTO') == '0' or os.path.exists(MARK):
        return w
    try:
        add = apply()
        os.makedirs(os.path.dirname(MARK), exist_ok=True)
        if not os.path.exists(MARK):
            json.dump({}, open(MARK, 'w'))
        return ('TOKEN ZOMBIE set in settings.json (new chats, backup made): ' + ', '.join(f'{k}={v}' for k, v in add.items())
                + '. Undo: tz settings --revert' + ('\n' + w if w else '')) if add else w
    except Exception:
        return ''


def main(argv):
    if '--revert' in argv:
        print('removed:', ', '.join(revert()) or 'nothing')
        return 0
    add = apply('--dry-run' in argv)
    print(('would add: ' if '--dry-run' in argv else 'added: ') + (', '.join(f'{k}={v}' for k, v in add.items()) or 'nothing (all already set)'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
