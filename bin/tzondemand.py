#!/usr/bin/env python3
# On-demand capabilities: optional MCP servers, plugins, single skills and skill packs stay off; `tz cap on X` turns one on for a
# task, SessionEnd turns off what this session turned on. Every change: backup first, re-read to verify, event in caps.jsonl.
# Host limits: MCP servers and plugins load at session start (on/off applies to the NEXT chat); a skill's listing follows the
# skills folder, but text of a skill already invoked stays in the chat. App built-ins (Chrome, computer use, scheduled tasks,
# MCP registry, browser pane, iOS simulator) are managed by the desktop app, not by files TZ may edit: reported, never changed.
import json, os, shutil, subprocess, sys, time

H = os.path.expanduser('~')
C = os.path.join(H, '.claude')
S = os.path.join(C, 'token-zombie')
CJ = os.path.join(H, '.claude.json')
SET = os.path.join(C, 'settings.json')
PARK = os.path.join(S, 'parked-mcp.json')
SOFF = os.path.join(C, 'skills-off', '_tz')
LOG = os.path.join(S, 'caps.jsonl')
BK = os.path.join(S, 'cap-backups')
PROTECT = {'token-zombie', 'token-zombie@token-zombie', 'handoff', 'claude-handoff', 'find-skills'}
APP = {'claude-in-chrome': 'Chrome extension', 'computer-use': 'computer use', 'scheduled-tasks': 'scheduled tasks',
       'mcp-registry': 'MCP registry', 'Claude_Browser': 'browser pane', 'Claude_Code_iOS_Simulator': 'iOS simulator'}
# prompt words -> capability, for the on-demand hint
WANT = {'premiere-pro': r'premiere|\.prproj', 'editsutra': r'edit (my|the|this|a) (video|footage|recording|clip)|footage|cut the silence|retake|talking.head|captions?|shorts|reels?'}


def _j(p, d):
    try:
        return json.load(open(p))
    except Exception:
        return d


def _w(p, v):
    tmp = p + '.tz-tmp'
    json.dump(v, open(tmp, 'w'), indent=2)
    os.replace(tmp, p)


def _backup(p):
    if os.path.exists(p):
        os.makedirs(BK, exist_ok=True)
        dst = os.path.join(BK, f"{os.path.basename(p)}.{time.strftime('%Y%m%d-%H%M%S')}")
        (shutil.copytree if os.path.isdir(p) else shutil.copy2)(p, dst, **({'dirs_exist_ok': True} if os.path.isdir(p) else {}))
        return dst


def _event(cap, act, ok, sid='', note=''):
    os.makedirs(S, exist_ok=True)
    open(LOG, 'a').write(json.dumps({'t': int(time.time()), 'cap': cap, 'act': act, 'ok': ok, 'sid': sid, 'note': note}) + '\n')


def kind(name):
    if name in APP:
        return 'app'
    if name in (_j(CJ, {}).get('mcpServers') or {}) or name in _j(PARK, {}):
        return 'mcp'
    if name in (_j(SET, {}).get('enabledPlugins') or {}):
        return 'plugin'
    if os.path.isdir(os.path.join(C, 'skills', name)) or os.path.isdir(os.path.join(SOFF, name)):
        return 'skill'
    if os.path.isdir(os.path.join(C, 'skills-off', name)) and os.path.exists(os.path.join(C, 'skillpack')):
        return 'pack'
    return None


def state(name):
    k = kind(name)
    if k == 'mcp':
        return name in (_j(CJ, {}).get('mcpServers') or {})
    if k == 'plugin':
        return bool(_j(SET, {}).get('enabledPlugins', {}).get(name))
    if k == 'skill':
        return os.path.isdir(os.path.join(C, 'skills', name))
    if k == 'pack':  # a pack is on when its parked folder is empty
        d = os.path.join(C, 'skills-off', name)
        return not os.listdir(d)
    return None


def set_(name, on, sid=''):
    """Turn one capability on/off. Returns (ok, message). Never touches app built-ins or protected items."""
    k = kind(name)
    if k is None:
        return False, f'{name}: unknown capability'
    if k == 'app':
        return False, f'{name}: {APP[name]} is managed by the desktop app (Settings > Connectors / extensions); TZ cannot toggle it'
    if not on and name in PROTECT:
        return False, f'{name}: protected (essential), not turned off'
    for f in ((CJ, PARK) if k == 'mcp' else (SET,) if k == 'plugin' else ()):
        if os.path.exists(f) and _j(f, None) is None:  # never overwrite a config TZ cannot parse
            _event(name, 'on' if on else 'off', False, sid, f'{f} unreadable')
            return False, f'{name}: {f} is not valid JSON; nothing changed (fix it or run: tz ondemand rollback)'
    if state(name) == on:
        _event(name, 'on' if on else 'off', True, sid, 'already')
        return True, f"{name}: already {'on' if on else 'off'}"
    if k == 'mcp':
        _backup(CJ)
        cj, park = _j(CJ, {}), _j(PARK, {})
        if on:
            cj.setdefault('mcpServers', {})[name] = park.pop(name)
        else:
            park[name] = cj['mcpServers'].pop(name)
        os.makedirs(S, exist_ok=True)
        _w(PARK, park); _w(CJ, cj)  # parked entry written first: nothing is lost if the second write fails
        eff = 'next chat (MCP servers load at session start)'
    elif k == 'plugin':
        _backup(SET)
        st = _j(SET, {}); st['enabledPlugins'][name] = on; _w(SET, st)
        eff = 'next chat (plugins load at session start)'
    elif k == 'skill':
        a, b = os.path.join(SOFF, name), os.path.join(C, 'skills', name)
        src, dst = (a, b) if on else (b, a)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        eff = 'skill list follows the folder; an already-invoked skill text stays in the chat'
    else:
        r = subprocess.run(['zsh', os.path.join(C, 'skillpack'), 'on' if on else 'off', name], capture_output=True, text=True)
        eff = 'skill list follows the folder' + ('' if r.returncode == 0 else f'; skillpack exit {r.returncode}')
    ok = state(name) == on  # verify by re-reading the real state
    _event(name, 'on' if on else 'off', ok, sid, eff)
    return ok, f"{name} ({k}): {'on' if on else 'off'} {'VERIFIED' if ok else 'FAILED verify'}; takes effect: {eff}"


def events(since=0):
    out = []
    for line in open(LOG) if os.path.exists(LOG) else []:
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get('t', 0) >= since:
            out.append(e)
    return out


def session_end(sid):
    """Turn off what this session turned on (newest 'on' by this sid, still on, not protected). Returns messages."""
    if not sid:
        return []
    ev = events(time.time() - 12 * 3600)
    mine = {e['cap'] for e in ev if e.get('sid') == sid and e.get('act') == 'on' and e.get('ok') and e.get('note') != 'already'}

    def others(c):  # another chat asked for it (on, incl. 'already') and has not ended: keep it on
        ended = {e.get('sid') for e in ev if e.get('act') == 'end'}
        return any(e['cap'] == c and e.get('act') == 'on' and e.get('sid') not in (sid, '', None) and e.get('sid') not in ended for e in ev)
    out = [set_(c, False, sid)[1] if not others(c) else f'{c}: kept on (another open chat uses it)'
           for c in sorted(mine) if state(c) and c not in PROTECT]
    _event('*', 'end', True, sid)
    return out


def want(prompt):
    """Capabilities a prompt needs that are off now (hint only)."""
    import re
    p = (prompt or '').lower()
    return [c for c, rx in WANT.items() if re.search(rx, p) and kind(c) and state(c) is False]


# tz-craft: prompt words -> reference file (first match wins; verify last so "fix failing test" routes to debug)
CRAFT = [('debug', r'flaky|failing|fails?\b|crash|exception|traceback|bug|broken|regression'),
         ('tdd', r'\btdd\b|test.first|write (a |the )?tests?'),
         ('refactor', r'refactor|clean ?up|restructure|rename'),
         ('review', r'\breview|code review|\bpr\b|pull request'),
         ('perf', r'slow|perf(ormance)?|latency|optimi[sz]e|memory leak'),
         ('react', r'react|next\.?js|component|jsx|tsx'),
         ('git-safety', r'force.push|hard reset|git clean|delete (the )?branch|rebase'),
         ('plan', r'\bplan\b|roadmap|break (it )?down|design (the|a)'),
         ('learn', r'lesson|never again|remember (this|to)|add a rule'),
         ('verify', r'done\?|is it (done|working)|verify|ready to ship|confirm it works')]


def craft(prompt):
    """tz-craft reference name a prompt needs, or None (hint only, never loads anything)."""
    import re
    p = (prompt or '').lower()
    return next((n for n, rx in CRAFT if re.search(rx, p)), None)


def rollback():
    """Restore the newest backup of ~/.claude.json and settings.json, and move TZ-parked skills back."""
    msg = []
    for p in (CJ, SET):
        bs = sorted(f for f in os.listdir(BK) if f.startswith(os.path.basename(p) + '.')) if os.path.isdir(BK) else []
        if bs:
            shutil.copy2(os.path.join(BK, bs[-1]), p); msg.append(f'restored {p} from {bs[-1]}')
    for n in os.listdir(SOFF) if os.path.isdir(SOFF) else []:
        if not os.path.exists(os.path.join(C, 'skills', n)):
            shutil.move(os.path.join(SOFF, n), os.path.join(C, 'skills', n)); msg.append(f'skill {n} back on')
    _event('*', 'rollback', True, '', '; '.join(msg))
    return msg or ['nothing to roll back']


def status():
    rows = [(n, 'mcp', state(n)) for n in sorted(set(_j(CJ, {}).get('mcpServers') or {}) | set(_j(PARK, {})))]
    rows += [(n, 'plugin', v) for n, v in sorted((_j(SET, {}).get('enabledPlugins') or {}).items())]
    rows += [(n, 'skill', False) for n in sorted(os.listdir(SOFF))] if os.path.isdir(SOFF) else []
    rows += [(n, 'app', None) for n in APP]
    return rows


def main(argv):
    a = argv[0] if argv else 'status'
    sid = os.environ.get('CLAUDE_SESSION_ID', '')
    if '--session' in argv:
        i = argv.index('--session'); sid = argv[i + 1]; argv = argv[:i] + argv[i + 2:]
    if a in ('on', 'off') and len(argv) > 1:
        rc = 0
        for n in argv[1:]:
            ok, m = set_(n, a == 'on', sid); print(m); rc |= not ok
        return rc
    if a == 'end':
        print('\n'.join(session_end(sid)) or 'nothing this session turned on')
    elif a == 'rollback':
        print('\n'.join(rollback()))
    elif a == 'log':
        for e in events(time.time() - 86400):
            print(time.strftime('%H:%M', time.localtime(e['t'])), e['act'], e['cap'], 'ok' if e['ok'] else 'FAIL', e.get('note', ''))
    else:
        for n, k, v in status():
            print(f"{n:45} {k:7} {'on' if v else 'off' if v is False else 'app-managed (not toggled by TZ)'}")
        print('usage: tz cap on|off NAME... [--session SID] | end --session SID | log | rollback')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
