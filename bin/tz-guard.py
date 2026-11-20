#!/usr/bin/env python3
# Token-zombie guard: task limit, not number limit. Big chat never stops a task; it moves the rest to a fresh session.
# UserPromptSubmit: from LIMIT growth, each new prompt gets "finish task, then handoff + fresh session for a new task".
# PostToolUse: from HARD growth, once per 25k step, "write handoff and move the rest of this task to a fresh session now".
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tzlib import chat_tokens, cfg, LIMIT, HARD, advice

# prompt words -> skill pack (~/.claude/skillpack). Hint printed once per pack per chat, so it costs ~30 tokens only when matched.
PACKS = {'video': 'video|caption|shorts|reel|podcast|youtube edit', 'motion': 'motion graphic|explainer|animated|manim|launch film',
         'sound': 'sfx|sound effect|audio clean|voice clean', 'remotion': 'remotion|hyperframes', 'design': 'ui design|polish ui|design system|critique',
         'web': 'gsap|clone (a )?site|slides', 'content': 'youtube script|thumbnail|newsletter|seo title', 'linkedin': 'linkedin',
         'social': 'instagram|carousel', 'seo': r'\bseo\b|\bgeo\b', 'book': 'novel|chapter|manuscript|kdp|book cover',
         'jobs': 'job search|cover letter|apply for', 'admin': 'invoice|inbox|meeting notes|expense', 'coding': 'refactor|write tests|tdd|code review|spec'}


def pack_hint(data):
    import re
    if not os.path.exists(os.path.expanduser('~/.claude/skillpack')):
        return ''
    text = (data.get('prompt') or '').lower()
    state = os.path.expanduser(f"~/.claude/token-zombie/packs-{data.get('session_id', 'x')}")
    seen = set(open(state).read().split()) if os.path.exists(state) else set()
    off = os.path.expanduser('~/.claude/skills-off')
    # suggest only packs that are off (have parked skills), not yet suggested in this chat
    hit = [p for p, rx in PACKS.items() if p not in seen and re.search(rx, text)
           and os.path.isdir(f'{off}/{p}') and os.listdir(f'{off}/{p}')]
    if not hit:
        return ''
    os.makedirs(os.path.dirname(state), exist_ok=True)
    open(state, 'a').write(' '.join(hit) + ' ')
    return ('TOKEN ZOMBIE (suggestion): skill pack(s) that match words in this prompt: ' + ', '.join(hit)
            + '. Turn one on (~/.claude/skillpack on <pack>) only if the task really needs it and installed skills do not cover it; off when done.')

def _diag(where, ev=''):
    """Append one local diagnostic line to ~/.claude/token-zombie/errors.log; never raises, never blocks the hook.
    Logs only exception type, a short message and file:line:function frames: no locals, no stdin, no transcript text."""
    try:
        import time, traceback
        et, e, tb = sys.exc_info()
        frames = ' < '.join(f'{os.path.basename(f.filename)}:{f.lineno}:{f.name}' for f in reversed(traceback.extract_tb(tb)))
        d = os.path.expanduser('~/.claude/token-zombie')
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, 'errors.log')
        if os.path.exists(p) and os.path.getsize(p) > 65536:  # keep the log small: drop the older half
            keep = open(p, encoding='utf-8', errors='replace').read()[-32768:]
            open(p, 'w', encoding='utf-8').write(keep[keep.find('\n') + 1:])
        import re  # messages can echo data: blank quoted text and long key/token-like runs
        msg = re.sub(r"'[^']*'|\"[^\"]*\"", "'<redacted>'", ' '.join(str(e).split()))
        msg = re.sub(r'[A-Za-z0-9_\-+/=.]{20,}', '<redacted>', msg)[:200]
        with open(p, 'a', encoding='utf-8') as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {where} ev={ev or '?'} {et.__name__}: {msg} @ {frames}\n")
    except Exception:
        pass


ev = ''
try:
    data = json.load(sys.stdin)
    base, last = chat_tokens(data.get('transcript_path'))
    used = max(0, last - base)
    ev = data.get('hook_event_name') or 'UserPromptSubmit'
    try:  # supervisor: records the lifecycle event (measured activity) and ticks on prompt/compact/stop; silent, never blocks
        import tzsup
        tzsup.on_event(data)
    except Exception:
        _diag('supervisor', ev)
    if ev in ('Stop', 'SessionEnd', 'PreCompact', 'SubagentStop'):
        sys.exit(0)
    if ev == 'PreToolUse':  # big Read: nudge once, never block twice (whole file may be truly needed)
        ti = data.get('tool_input') or {}
        f = ti.get('file_path') or ''
        if (ti.get('limit') or ti.get('offset') or not os.path.isfile(f) or os.path.getsize(f) <= cfg('read_warn')
                or f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf', '.ipynb'))):
            if not advice('dup_advice'):
                sys.exit(0)
            try:  # advice only, never a block: same file+range already read this session and unchanged
                from tzopt import read_advice, ledger
                adv = read_advice(data.get('session_id', 'x'), f, ti.get('limit'), ti.get('offset')) if os.path.isfile(f) else ''
                if adv:
                    ledger('overhead-hook', len(adv), 'measured', data.get('session_id', 'x'))
                    print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'additionalContext': adv}}))
            except Exception:
                pass
            sys.exit(0)
        if not advice('read_nudge'):
            sys.exit(0)
        state = os.path.expanduser(f"~/.claude/token-zombie/read-{data.get('session_id', 'x')}")
        seen = open(state).read().splitlines() if os.path.exists(state) else []
        if f in seen:
            sys.exit(0)  # second attempt = Claude decided the whole file is needed: allow
        os.makedirs(os.path.dirname(state), exist_ok=True)
        open(state, 'a').write(f + '\n')
        print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
            'permissionDecisionReason': f'TOKEN ZOMBIE (advice, not a ban): {f} is {os.path.getsize(f) // 1024} KB. '
            'If only part is needed: grep -n, then Read with offset+limit. If the task needs the whole file, '
            'repeat the same Read: it will be allowed.'}}))
        sys.exit(0)
    k = used // 1000
    if ev == 'PostToolUse':
        if used < HARD:
            sys.exit(0)
        # speak once per 25k step so it never costs tokens on every tool call
        state = os.path.expanduser(f"~/.claude/token-zombie/guard-{data.get('session_id', 'x')}")
        step = used // 25000
        try:
            if int(open(state).read()) >= step:
                sys.exit(0)
        except (OSError, ValueError):
            pass
        os.makedirs(os.path.dirname(state), exist_ok=True)
        open(state, 'w').write(str(step))
        msg = (f'TOKEN ZOMBIE: chat is {k}k tokens past start; every step re-sends all of it. Do NOT drop the task. '
               'At the next safe point (not mid-edit, mid-test or mid-file-operation) write the daily handoff '
               '(Status/Done verified/Left/Next step/Changed files/Tests, <=30 lines) and the HANDOFF.md top block, '
               'then move the rest of the task to a fresh session (mcp__ccd_session__hand_off_to_session if available, '
               'else tell the owner: "new chat, say: read <handoff path> and continue").')
    else:
        if used < LIMIT:
            hint = pack_hint(data) if advice('pack_hints') else ''
            if hint:
                print(json.dumps({'hookSpecificOutput': {'hookEventName': ev, 'additionalContext': hint}}))
            sys.exit(0)
        if not advice('next_task'):
            sys.exit(0)
        msg = (f'TOKEN ZOMBIE: chat is {k}k tokens past start. If this prompt continues the unfinished task, keep going until it is done, '
               'no big reads or images. If it is a NEW task: write the handoff first, then start it in a fresh session '
               '(mcp__ccd_session__start_session, context "fresh", short brief + handoff path; else tell the owner to open a new chat).')
    print(json.dumps({'hookSpecificOutput': {'hookEventName': ev, 'additionalContext': msg}}))
except Exception:
    _diag('guard', ev)
    sys.exit(0)
