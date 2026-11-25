#!/usr/bin/env python3
# tz go: one command. Checks install state and prints the single next step. Dry-run by default; --yes runs install.sh.
# tz gain: same data as `tz stats` under the name people expect.
import json, os, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))


def check(cfg=None):
    cfg = cfg or os.environ.get('CLAUDE_CONFIG_DIR') or os.path.join(os.path.expanduser('~'), '.claude')
    p = os.path.join(cfg, 'settings.json')
    if not os.path.exists(p):
        return 'missing', p
    try:
        s = json.load(open(p))
    except (OSError, ValueError):
        return 'broken', p
    if not isinstance(s, dict):
        return 'broken', p
    if any(str(k).startswith('token-zombie') for k in (s.get('enabledPlugins') or {})):
        return 'plugin', p
    txt = json.dumps(s.get('hooks', {}))
    return ('ok' if 'tz-guard' in txt else 'nohooks'), p


MSG = {
    'ok': 'Token Zombie is installed (hooks active). Nothing to do. See savings: tz gain',
    'plugin': 'Token Zombie is installed as a plugin. Nothing to do. See savings: tz gain',
    'missing': 'Not installed: no settings.json at {p}.',
    'nohooks': 'settings.json at {p} has no Token Zombie hooks.',
    'broken': 'settings.json at {p} is not valid JSON. Fix or restore it first; nothing was changed.',
}


def main(a):
    if a[:1] == ['gain']:
        return subprocess.call([sys.executable, os.path.join(ROOT, 'bin', 'tz'), 'stats'] + a[1:])
    st, p = check()
    print(MSG[st].format(p=p))
    if st in ('missing', 'nohooks'):
        if '--yes' in a:
            return subprocess.call(['bash', os.path.join(ROOT, 'install.sh')])
        print('Next: run  tz go --yes   (runs ./install.sh; backs up settings.json). Nothing changed yet.')
    return 1 if st == 'broken' else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
