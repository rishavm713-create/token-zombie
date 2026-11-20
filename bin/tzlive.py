#!/usr/bin/env python3
# Live session ledger, written by the guard on every hook event: hook time, skill states, agent lifecycle, conservative
# tool-call dedupe. File: ~/.claude/token-zombie/live-<session>.json (flock-guarded: parallel tool hooks must not lose updates).
# Dependency-light on purpose (json/os/time/fcntl only): it runs on every tool call.
# Skill states (never mixed): installed = SKILL.md on disk (active + parked + plugin cache); enabled = metadata loads each chat
# (active dir + enabled plugins); discovered = TZ suggested it this session; loaded = body entered the chat (invoked or /slash);
# invoked = the model called the Skill tool. Agents: starting -> running (background) -> done | failed; MEASURED from hooks only.
# Dedupe is ADVICE ONLY, never a deny: only Grep/Glob (read-only, file-state keyed: any possibly-mutating tool invalidates) and
# WebSearch/WebFetch (same input within 30 min). Bash and every other tool are never deduped (side effects). Compaction clears it all.
import fcntl, json, os, time

SAFE_FS = ('Grep', 'Glob')
SAFE_WEB = ('WebSearch', 'WebFetch')
READ_ONLY = SAFE_FS + SAFE_WEB + ('Read', 'Skill', 'TodoWrite', 'ToolSearch', 'TaskOutput', 'TaskList', 'TaskGet', 'ListMcpResourcesTool')
AGENT = ('Agent', 'Task')
WEB_TTL, AGENT_OLD = 1800, 3600


def sdir():
    d = os.path.expanduser('~/.claude/token-zombie')
    os.makedirs(d, exist_ok=True)
    return d


def path(session):
    return os.path.join(sdir(), f"live-{''.join(c for c in str(session) if c.isalnum() or c == '-')[:64] or 'x'}.json")


def blank():
    return {'hooks': {}, 'skills': {'discovered': {}, 'loaded': {}, 'invoked': {}}, 'agents': {}, 'calls': {}, 'gen': 0,
            'dedupe': {'advised': 0, 'compactions': 0}, 'notes': {}}


def _load(p):
    try:
        v = json.load(open(p))
        return v if isinstance(v, dict) and 'hooks' in v else blank()
    except Exception:
        return blank()


def edit(session, fn):
    """Locked read-modify-write; fn(state) returns a value. Never raises past the caller's try."""
    p = path(session)
    with open(p + '.lock', 'w') as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        s = _load(p)
        r = fn(s)
        tmp = f'{p}.{os.getpid()}.tmp'
        json.dump(s, open(tmp, 'w'))
        os.replace(tmp, p)
    return r


def key(data):
    ti = data.get('tool_input') or {}
    return data.get('tool_name', '') + '|' + (data.get('cwd') or '') + '|' + json.dumps(ti, sort_keys=True)[:2000]


def _bump(d, k):
    d[k] = d.get(k, 0) + 1


def on_event(data, now=None):
    """Update the ledger for one hook event. Returns advice text ('' if none). Advice is only ever additionalContext."""
    now = now or time.time()
    ev = data.get('hook_event_name') or ''
    tool = data.get('tool_name') or ''
    tid = data.get('tool_use_id') or ''
    ti = data.get('tool_input') or {}

    def fn(s):
        adv = ''
        if ev == 'PreCompact':  # summary drops earlier tool results: nothing may be called "already in the chat" any more
            s['calls'] = {}; s['gen'] += 1; s['dedupe']['compactions'] += 1
            try:
                os.remove(os.path.join(sdir(), f"reads-{data.get('session_id', 'x')}.json"))
            except OSError:
                pass
        elif ev == 'UserPromptSubmit':
            p = (data.get('prompt') or '').strip()
            if p.startswith('/'):
                name = p[1:].split()[0] if len(p) > 1 else ''
                if name and (':' in name or os.path.isfile(os.path.expanduser(f'~/.claude/skills/{name}/SKILL.md'))):
                    _bump(s['skills']['loaded'], name)
            old = [a for i, a in s['agents'].items() if a.get('status') == 'running' and now - a.get('t0', now) > AGENT_OLD
                   and not s['notes'].get(i)]
            for i, a in s['agents'].items():
                if a in old:
                    s['notes'][i] = int(now)
            if old:
                adv = ('TOKEN ZOMBIE (check): background agent(s) running 60+ min with no stop seen by hooks: '
                       + ', '.join(f"{a.get('type')} '{a.get('desc', '')}'" for a in old[:3])
                       + '. If the result is no longer needed, stop it (TaskStop); otherwise ignore this note.')
        elif ev == 'PreToolUse':
            if tool in AGENT and tid:
                s['agents'][tid] = dict(type=ti.get('subagent_type') or 'general', model=ti.get('model') or 'inherit',
                                        bg=bool(ti.get('run_in_background')), status='starting', t0=int(now), desc=str(ti.get('description', ''))[:60])
            elif tool in SAFE_FS + SAFE_WEB:
                k = key(data); c = s['calls'].get(k)
                fresh = c and not c.get('advised') and not c.get('trimmed') and (c['gen'] == s['gen'] if tool in SAFE_FS else now - c['t'] < WEB_TTL)
                if fresh:
                    c['advised'] = 1; s['dedupe']['advised'] += 1
                    adv = (f"TOKEN ZOMBIE (advice, not a block): an identical {tool} already ran in this chat"
                           + (' and no tool that can change files ran since' if tool in SAFE_FS else f" {int((now - c['t']) // 60)} min ago")
                           + '; its result is still above. Reuse it unless you need a fresh result; repeating the call is allowed.')
        elif ev == 'PostToolUse':
            if tool == 'Skill':
                _bump(s['skills']['invoked'], str(ti.get('skill') or ti.get('name') or '?'))
            if tool in AGENT and tid:
                a = s['agents'].setdefault(tid, dict(type=ti.get('subagent_type') or 'general', model=ti.get('model') or 'inherit',
                                                     bg=bool(ti.get('run_in_background')), t0=int(now), desc=str(ti.get('description', ''))[:60]))
                err = isinstance(data.get('tool_response'), dict) and data['tool_response'].get('is_error')
                a['status'] = 'failed' if err else ('running' if a.get('bg') else 'done')
                if a['status'] != 'running':
                    a['t1'] = int(now)
            if tool in SAFE_FS + SAFE_WEB:
                s['calls'][key(data)] = dict(gen=s['gen'], t=int(now))
            elif tool not in READ_ONLY:  # Bash, Edit, Write, agents, MCP...: may change files -> every fs-keyed result is stale
                s['gen'] += 1
            if len(s['calls']) > 300:  # keep the file small
                s['calls'] = dict(sorted(s['calls'].items(), key=lambda kv: kv[1]['t'])[-200:])
        elif ev == 'SubagentStop':
            run = [a for a in s['agents'].values() if a.get('status') == 'running']
            if len(run) == 1:
                run[0]['status'] = 'done'; run[0]['t1'] = int(now)
            else:  # cannot tell which agent stopped: count it, never guess
                _bump(s['notes'], 'unmatched_subagent_stops')
        return adv
    return edit(data.get('session_id', 'x'), fn)


def discovered(session, names):
    def fn(s):
        for n in names:
            _bump(s['skills']['discovered'], n)
    edit(session, fn)


def timing(session, ev, ms, chars):
    def fn(s):
        h = s['hooks'].setdefault(ev, {'n': 0, 'ms': 0.0, 'max': 0.0, 'chars': 0})
        h['n'] += 1; h['ms'] = round(h['ms'] + ms, 2); h['max'] = round(max(h['max'], ms), 2); h['chars'] += chars
    edit(session, fn)


def skill_inventory(home=None):
    """installed / enabled counts from disk (MEASURED). Plugin skills count as enabled only for enabledPlugins in settings."""
    cl = os.path.join(home or os.path.expanduser('~'), '.claude')
    def count(root):
        return sum('SKILL.md' in fs for _, _, fs in os.walk(root)) if os.path.isdir(root) else 0
    active, parked = count(os.path.join(cl, 'skills')), count(os.path.join(cl, 'skills-off'))
    cache = os.path.join(cl, 'plugins', 'cache')
    try:
        en = [k for k, v in (json.load(open(os.path.join(cl, 'settings.json'))).get('enabledPlugins') or {}).items() if v]
    except Exception:
        en = []
    plug_all = count(cache)
    plug_on = sum(count(os.path.join(cache, k.split('@')[-1], k.split('@')[0])) for k in en if '@' in k)
    return dict(installed=active + parked + plug_all, enabled=active + plug_on, active_dir=active, parked=parked,
                plugin_all=plug_all, plugin_enabled=plug_on)


def latest_session():
    fs = [f for f in os.listdir(sdir()) if f.startswith('live-') and f.endswith('.json')]
    return max(fs, key=lambda f: os.path.getmtime(os.path.join(sdir(), f)))[5:-5] if fs else None


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='tz live')
    ap.add_argument('cmd', nargs='?', default='show', choices=['show', 'skills', 'agents'])
    ap.add_argument('--session')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    sid = a.session or latest_session()
    s = _load(path(sid)) if sid else blank()
    if a.cmd == 'skills':
        inv = skill_inventory(); sk = s['skills']
        r = dict(**inv, discovered=len(sk['discovered']), loaded=len(set(sk['loaded']) | set(sk['invoked'])), invoked=len(sk['invoked']),
                 invoked_names=sorted(sk['invoked']), session=sid)
        if a.json:
            print(json.dumps(r)); return 0
        print(f"skills [MEASURED] installed {r['installed']} (active {inv['active_dir']}, parked {inv['parked']}, plugin cache {inv['plugin_all']})"
              f" | enabled {r['enabled']} | this session ({sid or 'none'}): discovered {r['discovered']}, loaded {r['loaded']}, invoked {r['invoked']}"
              + (f" ({', '.join(r['invoked_names'])})" if r['invoked_names'] else ''))
        return 0
    if a.cmd == 'agents':
        if a.json:
            print(json.dumps(s['agents'])); return 0
        st = {}
        for x in s['agents'].values():
            _bump(st, x.get('status', '?'))
        print(f"agents this session ({sid or 'none'}) [MEASURED from hooks]: " + (', '.join(f'{k} {v}' for k, v in sorted(st.items())) or 'none')
              + (f" | unmatched stops {s['notes']['unmatched_subagent_stops']}" if s['notes'].get('unmatched_subagent_stops') else ''))
        for i, x in s['agents'].items():
            print(f"  {x.get('status'):8} {x.get('type')} model={x.get('model')} bg={x.get('bg')} '{x.get('desc', '')}'")
        return 0
    if a.json:
        print(json.dumps(s)); return 0
    print(f"session {sid or 'none'}: dedupe advices {s['dedupe']['advised']}, compactions {s['dedupe']['compactions']}, tracked calls {len(s['calls'])}")
    for k, v in sorted(s['hooks'].items()):
        print(f"  hook {k:16} n {v['n']:5} body {v['ms']:8.0f} ms (max {v['max']:.0f}) injected ~{v['chars'] // 4} tok [EST]")
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv[1:]))
