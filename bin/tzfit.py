#!/usr/bin/env python3
"""tzfit: shared hook-output budget fitter + plan re-injection.
fit(): idea adapted from claude-mem src/services/context/ContextBudget.ts (Apache-2.0, Copyright Alex Newman), see NOTICE. Re-written, not copied.
plan_inject(): policy from planning-with-files (MIT, OthmanAdi) hash-change re-read + Continuous-Claude startup pointer (behaviour only), see NOTICE.
Stdlib only; never raises into a hook."""
import glob, hashlib, json, os, re, sys

CAP = 9000
PLAN_FILES = ('task_plan.md', os.path.join('handoffs', 'STATE.md'), 'PLAN.md')
HEAD_LINES, TAIL_LINES, PLAN_CAP = 50, 20, 3500


def _cut_marker(n):
    return f'\n... (+{n} chars cut, tz recall)\n'


def fit(text, cap=CAP):
    """Keep head (60%) and tail (40%) of text on line boundaries; middle sections dropped, marker says how much. <= cap chars always."""
    if not isinstance(text, str) or len(text) <= cap:
        return text
    mk = _cut_marker(len(text))
    room = max(cap - len(mk) - 8, 0)  # 8: slack for the digits of the final count
    hb, tb = int(room * 0.6), room - int(room * 0.6)
    head, tail = text[:hb], text[len(text) - tb:] if tb else ''
    i = head.rfind('\n')
    if i > hb // 2:  # snap to a line end only when it costs < half the head
        head = head[:i]
    j = tail.find('\n')
    if 0 <= j < tb // 2:
        tail = tail[j + 1:]
    cut = len(text) - len(head) - len(tail)
    out = head + _cut_marker(cut) + tail
    return out if len(out) <= cap else out[:cap]


_EMIT = re.compile(r'''['"](additionalContext|systemMessage)['"]\s*:\s*[^'"\s]''')  # key with a non-literal value
_SAFE = re.compile(r'\[\s*:\s*\w+\s*\]|\bfit\(|tzfit|\bCAP\b')


def audit(bindir=None):
    """Report-only: [(file, line, text)] emit sites with no slice / fit / CAP within 3 lines (may exceed the cap)."""
    bindir = bindir or os.path.dirname(os.path.abspath(__file__))
    out = []
    for f in sorted(glob.glob(os.path.join(bindir, '*.py'))):
        try:
            L = open(f, encoding='utf-8', errors='ignore').read().splitlines()
        except OSError:
            continue
        for i, s in enumerate(L):
            if _EMIT.search(s) and not s.lstrip().startswith('#'):
                if not _SAFE.search(' '.join(L[max(0, i - 3):i + 2])):
                    out.append((os.path.basename(f), i + 1, s.strip()[:100]))
    return out


# ---- plan re-injection ----
def _home():
    return os.path.join(os.path.expanduser('~'), '.claude', 'token-zombie')


def find_plan(cwd):
    for r in PLAN_FILES:
        p = os.path.join(cwd, r)
        if os.path.isfile(p) and os.path.getsize(p):
            return p
    return ''


def _state(sid):
    return os.path.join(_home(), 'plan-' + re.sub(r'[^A-Za-z0-9_-]', '', sid or 'x')[:40] + '.json')


def _newest_handoff(cwd):
    d = sorted(glob.glob(os.path.join(cwd, 'handoffs', '*.md')), key=os.path.getmtime)
    return d[-1] if d else ''


def plan_inject(data):
    """SessionStart/PreCompact text ('' = nothing). startup: one pointer line; compact/resume: head 50 + tail 20 lines, only if the plan changed."""
    try:
        from tzlib import feature
        if not feature('plan_reinject'):
            return ''
        cwd = data.get('cwd') or os.getcwd()
        p = find_plan(cwd)
        if not p:
            return ''
        ev = data.get('hook_event_name') or ''
        src = 'compact' if ev == 'PreCompact' else (data.get('source') or 'startup')
        rel = os.path.relpath(p, cwd)
        if src == 'startup':  # Continuous-Claude policy: pointer only on a fresh start
            return f'TOKEN ZOMBIE: plan file {rel} exists; read it only if the task needs it.'
        if src == 'resume' and os.path.abspath(p) == os.path.abspath(_newest_handoff(cwd)):
            return ''  # tz-start already injects the newest handoff head
        raw = open(p, encoding='utf-8', errors='ignore').read()
        sha = hashlib.sha256(raw.encode()).hexdigest()[:16]
        sp = _state(data.get('session_id'))
        try:
            last = json.load(open(sp)).get('sha')
        except (OSError, ValueError):
            last = None
        if last == sha:
            return ''
        L = raw.splitlines()
        body = L if len(L) <= HEAD_LINES + TAIL_LINES else L[:HEAD_LINES] + [f'... ({len(L) - HEAD_LINES - TAIL_LINES} lines cut) ...'] + L[-TAIL_LINES:]
        txt = fit(f'TOKEN ZOMBIE plan ({rel}, head {HEAD_LINES} + progress tail {TAIL_LINES} lines):\n' + '\n'.join(body), PLAN_CAP)
        os.makedirs(_home(), exist_ok=True)
        json.dump({'sha': sha}, open(sp + '.tmp', 'w'))
        os.replace(sp + '.tmp', sp)
        return txt
    except Exception:
        return ''


if __name__ == '__main__':
    for r in audit():
        print('%s:%d  %s' % r)
