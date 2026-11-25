#!/usr/bin/env python3
# Stuck detector for Claude Code hook events. check(data) on PostToolUse -> one short advice line or ''. Advice only, never blocks.
# Adapted from OpenHands software-agent-sdk openhands-sdk/openhands/sdk/conversation/stuck_detector.py (MIT, Copyright (c) 2025 All Hands AI), see NOTICE.
# Divergences: events are hook payloads, not SDK event classes; observations are normalised (timestamps/pids stripped) before comparing;
# each pattern speaks once per streak (state file) instead of the SDK's single is_stuck() boolean.
import hashlib, json, os, re, tempfile

TH = dict(obs=4, err=3, mono=3, alt=6)   # OpenHands defaults: action_observation, action_error, monologue, alternating_pattern
WIN = 20                                  # events kept per session (OpenHands MAX_EVENTS_TO_SCAN_FOR_STUCK_DETECTION)
_NOISE = re.compile(r'\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d\S*|\b(?:pid|PID)[ =:]*\d+|\b\d{9,}\b')


def _dir():
    return os.path.join(os.path.expanduser('~'), '.claude', 'token-zombie')


def _path(sid):
    return os.path.join(_dir(), 'stuck-%s.json' % re.sub(r'[^A-Za-z0-9_-]', '_', str(sid))[:60])


def _load(sid):
    try:
        st = json.load(open(_path(sid)))
        if isinstance(st, dict) and isinstance(st.get('ev'), list):
            st.setdefault('said', {})
            return st
    except Exception:
        pass
    return dict(ev=[], said={})


def _save(sid, st):
    try:
        os.makedirs(_dir(), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=_dir(), prefix='.stuck')
        with os.fdopen(fd, 'w') as f:
            json.dump(st, f)
        os.replace(tmp, _path(sid))
    except Exception:
        pass  # fail-open: advice is optional


def _h(s):
    return hashlib.sha1(s.encode('utf-8', 'replace')).hexdigest()[:10]


def _text(r):
    if isinstance(r, str):
        return r
    try:
        return json.dumps(r, sort_keys=True, default=str)
    except Exception:
        return str(r)


def _is_err(data):
    r = data.get('tool_response')
    return bool(data.get('error') or data.get('hook_event_name') == 'PostToolUseFailure'
                or (isinstance(r, dict) and (r.get('is_error') or r.get('error'))))


def event(data):
    """Hook payload -> event row [kind, action_key, observation_key, is_error, tool, err_text]. kind 't' = tool pair, 'm' = assistant message."""
    tool = data.get('tool_name') or ''
    if not tool:
        return ['m', '', '', 0, '', '']
    a = _h(tool + _text(data.get('tool_input') or {}))
    obs = _text(data.get('tool_response') if data.get('tool_response') is not None else data.get('error') or '')
    e = _is_err(data)
    return ['t', a, _h(_NOISE.sub('~', obs)), int(e), tool, _NOISE.sub('~', obs)[:80] if e else '']


def patterns(ev):
    """Which stuck patterns hold for this event window. Returns {name: level}; level 'nudge' or 'stuck'."""
    out, t = {}, [e for e in ev if e[0] == 't']
    n = TH['obs']
    if len(t) >= n and len({(e[1], e[2]) for e in t[-n:]}) == 1:
        out['obs'] = 'stuck'
    streak = 0
    for e in reversed(t):  # trailing run of the same failing action
        if e[3] and e[1] == (t[-1][1] if t else None):
            streak += 1
        else:
            break
    if streak >= TH['err']:
        out['err'] = 'stuck' if streak > TH['err'] else 'nudge'
    mono = 0
    for e in reversed(ev):
        if e[0] != 'm':
            break
        mono += 1
    if mono >= TH['mono']:
        out['mono'] = 'stuck'
    if len(ev) >= TH['alt'] and all(e[0] == 't' for e in ev[-TH['alt']:]):
        w = ev[-TH['alt']:]
        if all(w[i][1] == w[i + 2][1] and w[i][2] == w[i + 2][2] for i in range(TH['alt'] - 2)):
            out['alt'] = 'stuck'
    return out


def _line(name, level, ev):
    last = next((e for e in reversed(ev) if e[0] == 't'), ['', '', '', 0, 'tool', ''])
    if name == 'err':
        s = ('TOKEN ZOMBIE: %s failed %dx the same way (%s). Change the command or read the error before retrying.' % (last[4], TH['err'], last[5])
             if level == 'nudge' else 'TOKEN ZOMBIE stuck: %s keeps failing identically. Stop retrying; try another approach or ask.' % last[4])
    elif name == 'obs':
        s = 'TOKEN ZOMBIE stuck: %s ran %dx with identical input and output. Change approach.' % (last[4], TH['obs'])
    elif name == 'mono':
        s = 'TOKEN ZOMBIE stuck: %d assistant turns in a row with no tool use. Act or ask the user.' % TH['mono']
    else:
        s = 'TOKEN ZOMBIE stuck: alternating between two actions with no new result. Try a third approach.'
    return s[:200]


def check(data):
    """PostToolUse (or a no-tool message event / UserPromptSubmit): returns one advice line or ''. Gated by feature('stuck_detect')."""
    try:
        from tzlib import feature
        if not feature('stuck_detect'):
            return ''
    except Exception:
        return ''
    sid = data.get('session_id') or 'x'
    st = _load(sid)
    if data.get('hook_event_name') == 'UserPromptSubmit':  # window resets after a user message (OpenHands test_reset_after_user_message)
        st['ev'], st['said'] = [], {}
        _save(sid, st)
        return ''
    st['ev'] = (st['ev'] + [event(data)])[-WIN:]
    pat = patterns(st['ev'])
    st['said'] = {k: v for k, v in st['said'].items() if pat.get(k) == v}  # streak ended -> pattern may speak again
    msg = ''
    for name in ('err', 'obs', 'alt', 'mono'):
        if name in pat and st['said'].get(name) != pat[name]:
            st['said'][name] = pat[name]
            msg = _line(name, pat[name], st['ev'])
            break
    _save(sid, st)
    return msg
