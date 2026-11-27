#!/usr/bin/env python3
"""tz brief start|done|pack: two small offline handoff types (no model call) plus skill-pack automation.
start -> handoffs/YYYY-MM-DD-start.md  (git state, last test, decisions, left/next, suggested pack)
done  -> handoffs/YYYY-MM-DD-done.md   (what was done, test result, git, decisions; turns the packs it turned on off again)
pack on|off P -> ~/.claude/skillpack on|off P, recorded so `done` can undo it. Advice only: never starts a session."""
import json, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tzhandoff as H

SKILLPACK = os.path.expanduser('~/.claude/skillpack')
LOG = os.path.expanduser('~/.claude/token-zombie/packs-on.json')


def _state(cwd):
    try:
        return json.load(open(H.newest_task(cwd) or ''))
    except (OSError, ValueError, TypeError):
        return {}


def _git_line(snap):
    if not snap.get('repo'):
        return 'Git: not a repo'
    ch = list(snap['changed'])
    return f"Git: {snap['branch']}@{snap['head']}, {len(ch)} uncommitted" + (': ' + ', '.join(ch[:8]) + (f' +{len(ch) - 8}' if len(ch) > 8 else '') if ch else '')


def _test_line(st):
    t = st.get('test') or {}
    if not t.get('cmd'):
        return 'Last test: none recorded'
    return f"Last test: `{t['cmd'][:80]}` -> {'pass' if t.get('ok') else 'FAILED' if t.get('ok') is False else 'not run'}"


def _packs():
    try:
        return json.load(open(LOG))
    except (OSError, ValueError):
        return []


def pack(action, name):
    """Run skillpack on/off for one pack; keep the on-list so `done` can turn it off. Returns the skillpack output."""
    if not os.path.exists(SKILLPACK) or not name.replace('-', '').isalnum():
        return 'tz brief pack: no skillpack script or bad pack name'
    out = subprocess.run(['zsh', SKILLPACK, action, name], capture_output=True, text=True, timeout=60).stdout.strip()
    cur = [p for p in _packs() if p != name] + ([name] if action == 'on' else [])
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    json.dump(cur, open(LOG, 'w'))
    return out


def _write(cwd, kind, lines):
    os.makedirs(H.hdir(cwd), exist_ok=True)
    p = os.path.join(H.hdir(cwd), f"{time.strftime('%Y-%m-%d')}-{kind}.md")
    open(p, 'w', encoding='utf-8').write('\n'.join(lines[:30]) + '\n')
    return p


def start(cwd, task=''):
    st, snap = _state(cwd), H.snapshot(cwd)
    task = task or st.get('task') or 'new task'
    mem = H.memory_tail(cwd, 3)
    lines = [f"# Start brief {time.strftime('%Y-%m-%d %H:%M')}: {task}",
             'Previous: ' + ('; '.join(st.get('done') or []) or 'nothing recorded'),
             'Left: ' + ('; '.join(st.get('left') or []) or 'nothing recorded'),
             'Next: ' + (st.get('next') or 'not set'),
             _git_line(snap), _test_line(st)]
    if mem:
        lines.append('Decisions: ' + ' | '.join(m[2:][:100] for m in mem))
    lines.append('Rules: read only this note; one task; build all then test once; no commit without owner OK.')
    return _write(cwd, 'start', lines)


def done(cwd, summary='', decisions=()):
    st, snap = _state(cwd), H.snapshot(cwd)
    for d in decisions:
        H.remember(cwd, d)
    off = []
    for p in _packs():
        pack('off', p)
        off.append(p)
    lines = [f"# Done record {time.strftime('%Y-%m-%d %H:%M')}: {st.get('task') or 'task'}",
             'Result: ' + (summary or '; '.join(st.get('done') or []) or 'nothing recorded'),
             'Open: ' + ('; '.join(st.get('left') or []) or 'none'),
             _git_line(snap), _test_line(st)]
    if decisions:
        lines.append('Decisions: ' + ' | '.join(d[:100] for d in decisions))
    if off:
        lines.append('Packs turned off: ' + ', '.join(off))
    lines.append('Next task: start a NEW session (advice only; nothing started or committed), first read the newest file in handoffs/.')
    return _write(cwd, 'done', lines)


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='tz brief')
    ap.add_argument('cmd', choices=['start', 'done', 'pack'])
    ap.add_argument('rest', nargs='*')
    ap.add_argument('--cwd', default=os.getcwd())
    ap.add_argument('--task', default='')
    ap.add_argument('--summary', default='')
    ap.add_argument('--remember', action='append', default=[])
    a = ap.parse_args(argv)
    cwd = os.path.abspath(a.cwd)
    if a.cmd == 'pack':
        if len(a.rest) != 2 or a.rest[0] not in ('on', 'off'):
            print('usage: tz brief pack on|off PACK'); return 2
        print(pack(*a.rest)); return 0
    p = start(cwd, a.task or ' '.join(a.rest)) if a.cmd == 'start' else done(cwd, a.summary or ' '.join(a.rest), a.remember)
    print(p)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
