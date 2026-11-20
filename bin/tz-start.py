#!/usr/bin/env python3
# Token-zombie lean start: inject only HANDOFF.md's top block (up to the first '---' line, max 15 lines)
# and the head of the newest handoffs/*.md (max 30 lines), so a huge HANDOFF.md is never read whole.
# source=compact: inject only the continuation note from tz-compact.py.
import glob, json, os, sys

TOP, DAILY, CAP = 15, 30, 4000  # lines, lines, chars


def head(path, n, stop_at_rule):
    out = []
    with open(path, encoding='utf-8', errors='ignore') as f:
        for i, line in enumerate(f):
            if i >= n or (stop_at_rule and i and line.strip() == '---'):
                break
            out.append(line.rstrip())
    return '\n'.join(out)


try:
    d = json.load(sys.stdin)
    cwd = d.get('cwd') or os.getcwd()
    parts, pk = [], ''
    if d.get('source') == 'compact':  # after compaction: only the continuation note tz-compact.py saved
        note = os.path.expanduser(f"~/.claude/token-zombie/compact-{d.get('session_id', 'x')}.md")
        if os.path.isfile(note):
            txt = 'TOKEN ZOMBIE continuation (saved just before compaction; facts from git + chat log):\n' + open(note).read()[:1500]
            print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': txt}}))
        sys.exit(0)
    master = os.path.join(cwd, 'HANDOFF.md')
    if os.path.isfile(master):
        parts.append(f'## {master} (top block only)\n' + head(master, TOP, True))
    daily = sorted(glob.glob(os.path.join(cwd, 'handoffs', '*.md')), key=os.path.getmtime)
    if daily:
        parts.append(f'## {daily[-1]} (newest handoff)\n' + head(daily[-1], DAILY, False))
    try:  # active task pack (<=2k tok), when handoffs/tasks has one
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import tznext
        pk = tznext.pack(cwd)
    except Exception:
        pass
    if parts or pk:
        txt = ('TOKEN ZOMBIE start context. Use this; do not read the full HANDOFF.md unless the step needs a detail.\n'
               + '\n\n'.join(parts))[:CAP] + ('\n\n' + pk if pk else '')
        print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': txt}}))
except Exception:
    sys.exit(0)
