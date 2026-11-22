#!/usr/bin/env python3
# Token-zombie lean start: inject only HANDOFF.md's top block (up to the first '---' line, max 15 lines)
# and the head of the newest handoffs/*.md (max 30 lines), so a huge HANDOFF.md is never read whole.
# source=compact: inject only the continuation note from tz-compact.py.
import glob, json, os, sys

TOP, DAILY, CAP = 15, 30, 2500  # lines, lines, chars
# TZ core rules: one compact block merging the useful caveman, ponytail and Karpathy rules plus the owner's CLAUDE.md
# rules (caveman+ponytail cost ~7.7k chars each chat, ~2k tok per subagent [measured]). Specialist skills stay on demand.
# Injected only when neither plugin is enabled, so nothing is said twice. Off: config "lean_rules": false.
LEAN = ('TOKEN ZOMBIE core rules (lean rules). Replies: answer first, terse; no greeting, recap, filler or offers. Keep every '
        'fact, negation (not/never/only), code, command, path, number and error exact. Full sentences for security warnings, '
        'irreversible steps and questions to the owner. Work: match effort to the task; state assumptions when unclear; '
        'read code before editing it; never re-read a file or re-run a call whose result you have; batch independent calls; '
        'keep decisions already made. Code: smallest complete change; reuse the codebase, stdlib and installed deps before '
        'new code; no unasked features, options or abstractions; touch only what the task needs, match the style, fix root '
        'causes; check security and correctness of what you change; test real changes (one small test for new logic) and '
        'loop until it passes. Review, audit and commit skills only on demand. '
        'End with one line: what you skipped or did not check.')


def lean():
    home = os.path.expanduser('~/.claude')
    try:
        if json.load(open(os.path.join(home, 'token-zombie', 'config.json'))).get('lean_rules') is False:
            return ''
    except Exception:
        pass
    try:
        on = [k for k, v in (json.load(open(os.path.join(home, 'settings.json'))).get('enabledPlugins') or {}).items() if v]
    except Exception:
        on = []
    return '' if any(k.split('@')[0] in ('caveman', 'ponytail') for k in on) else LEAN


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
        else:
            txt = ''
        txt = '\n\n'.join(x for x in (lean(), txt) if x)
        if txt:
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
    L = lean()
    if parts or pk or L:
        txt = (('TOKEN ZOMBIE start context. Use this; do not read the full HANDOFF.md unless the step needs a detail.\n'
               + '\n\n'.join(parts))[:CAP] if parts else '') + ('\n\n' + pk if pk else '')
        txt = '\n\n'.join(x for x in (L, txt.strip()) if x)
        print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': txt}}))
    if d.get('source') != 'resume' and os.environ.get('TZ_FRESH_BG') != '0':  # panel's fresh-chat number; detached, never delays start
        import subprocess
        subprocess.Popen([sys.executable, '-c', 'import sys; sys.path.insert(0, sys.argv[1]); import tzopt; tzopt.fresh_file()',
                          os.path.dirname(os.path.abspath(__file__))], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
except Exception:
    sys.exit(0)
