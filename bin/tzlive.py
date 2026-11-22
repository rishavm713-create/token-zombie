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
            'dedupe': {'advised': 0, 'compactions': 0}, 'notes': {}, 'instr': {}, 'compact': [], 'events': {}, 'models': [], 'worktrees': {}}


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
            lc = (s.get('compact') or [{}])[-1]
            if lc.get('verdict') == 'weak' and not lc.get('advised'):  # deterministic fallback: summary missed the saved facts
                lc['advised'] = 1
                adv = (f"TOKEN ZOMBIE (check): the compaction summary kept only {lc.get('hit')}/{lc.get('of')} saved key facts; missing: "
                       + ', '.join(lc.get('missing', [])[:6]) + f". The verified continuation note is {lc.get('note')}; read it before continuing.")
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
                d0 = ' '.join(str(ti.get('description', '')).lower().split())
                dup = [a for a in s['agents'].values() if d0 and a.get('status') in ('running', 'starting', 'done')
                       and ' '.join(str(a.get('desc', '')).lower().split()) == d0 and a.get('type') == (ti.get('subagent_type') or 'general')]
                if dup:  # same type + same description already assigned in this chat (advice only)
                    _bump(s['notes'], 'dup_agent_advised')
                    adv = (f"TOKEN ZOMBIE (check): an agent with the same type and description ('{d0[:50]}') was already started in this chat"
                           f" ({dup[0].get('status')}). Reuse its result (SendMessage) unless this is a deliberate re-run; the call is allowed.")
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
        elif ev == 'SubagentStart':  # exact agent identity from the hook (MEASURED)
            aid = data.get('agent_id') or ''
            if aid:
                s['agents'][aid] = dict(type=data.get('agent_type') or 'general', model='inherit', bg=False, status='running',
                                        t0=int(now), desc='', by_hook=1)
        elif ev == 'InstructionsLoaded':  # which instruction files entered context, and why (size is bytes; tokens = EST size/4)
            f = str(data.get('file_path') or '')[:200]
            if f:
                try:
                    sz = os.path.getsize(f)
                except OSError:
                    sz = 0
                s.setdefault('instr', {})[f] = dict(reason=str(data.get('load_reason') or '')[:30], bytes=sz, est_tokens=sz // 4, t=int(now))
        elif ev == 'PostToolBatch':  # batch size only (the host payload's exact fields are not assumed)
            _bump(s.setdefault('events', {}), 'tool_batches')
        elif ev in ('PreModelSwitch', 'PostModelSwitch'):  # attempt vs actual model, both recorded as given by the host
            m = str(data.get('model') or data.get('new_model') or data.get('to') or '')[:60]
            s.setdefault('models', []).append(dict(t=int(now), ev=ev, model=m or 'not-in-payload'))
            s['models'] = s['models'][-20:]
        elif ev in ('WorktreeCreate', 'WorktreeRemove'):
            w = str(data.get('worktree_path') or data.get('path') or data.get('name') or '?')[:120]
            s.setdefault('worktrees', {})[w] = dict(state='created' if ev == 'WorktreeCreate' else 'removed', t=int(now))
        elif ev == 'PostCompact':
            v = verify_compact(data.get('session_id', 'x'), data.get('compact_summary'))
            s.setdefault('compact', []).append(dict(t=int(now), trigger=str(data.get('trigger') or '')[:20], **v))
            s['compact'] = s['compact'][-20:]
        elif ev == 'SessionEnd':  # agents still running when the chat ends were cut off (MEASURED from the two events)
            for a in s['agents'].values():
                if a.get('status') in ('running', 'starting'):
                    a['status'] = 'interrupted'; a['t1'] = int(now)
            _bump(s['notes'], 'session_end')
        elif ev == 'SubagentStop':
            aid = data.get('agent_id') or ''
            if aid and aid in s['agents']:
                s['agents'][aid]['status'] = 'done'; s['agents'][aid]['t1'] = int(now)
                return adv
            run = [a for a in s['agents'].values() if a.get('status') == 'running']
            if len(run) == 1:
                run[0]['status'] = 'done'; run[0]['t1'] = int(now)
            else:  # cannot tell which agent stopped: count it, never guess
                _bump(s['notes'], 'unmatched_subagent_stops')
        return adv
    return edit(data.get('session_id', 'x'), fn)


def agent_costs(sid, home=None):
    """{agent_id: {calls, tok, usd, result_chars}} from this session's subagent transcripts. Tokens MEASURED, $ EST (list price)."""
    import glob, tzopt
    out = {}
    h = home or os.path.expanduser('~')
    for f in sorted(glob.glob(os.path.join(h, f'.claude/projects/*/{sid}/subagents/*.jsonl'))) if sid else []:
        n, ie, o, usd, seen, last = 0, 0, 0, 0.0, set(), 0
        for raw in open(f, 'rb'):
            if b'"usage"' not in raw:
                continue
            try:
                m = (json.loads(raw).get('message') or {}); u = m.get('usage')
            except Exception:
                continue
            if not isinstance(u, dict) or m.get('id') in seen:
                continue
            seen.add(m.get('id')); x, c = tzopt._cost(m.get('model'), u); n += 1; ie += x; o += u.get('output_tokens') or 0; usd += c
            last = sum(len(b.get('text', '')) for b in (m.get('content') or []) if isinstance(b, dict) and b.get('type') == 'text')
        out[os.path.basename(f)[:-6].replace('agent-', '', 1)] = dict(calls=n, tok=int(ie + o), usd=round(usd, 4), result_chars=last)
    return out


SMALL_CALLS, SMALL_TOK = 2, 20000
STALL_SEC = 600


def roi(sid, s=None, home=None):
    """Per-agent cost vs outcome. Flags (EST, advice only): small = could have run inline; empty = no result text; failed; duplicate."""
    s = s or _load(path(sid)); costs = agent_costs(sid, home); rows = []
    seen = {}
    for aid, a in s['agents'].items():
        c = costs.get(aid) or costs.get(aid.replace('toolu_', ''), {})
        d = ' '.join(str(a.get('desc', '')).lower().split())
        fl = []
        if a.get('status') == 'running' and a.get('by_hook'):  # stalled: running by hooks but its transcript has been quiet
            try:
                import glob
                fs = glob.glob(os.path.join(home or os.path.expanduser('~'), f'.claude/projects/*/{sid}/subagents/agent-{aid}.jsonl'))
                if fs and time.time() - max(os.path.getmtime(x) for x in fs) > STALL_SEC:
                    fl.append('stalled')
            except OSError:
                pass
        if c and c['calls'] <= SMALL_CALLS and c['tok'] < SMALL_TOK:
            fl.append('small')
        if c and not c['result_chars'] and a.get('status') == 'done':
            fl.append('empty')
        if a.get('status') == 'failed':
            fl.append('failed')
        if d and (a.get('type'), d) in seen:
            fl.append('duplicate')
        seen[(a.get('type'), d)] = 1
        rows.append(dict(id=aid, type=a.get('type'), status=a.get('status'), desc=a.get('desc', ''), flags=fl, **{k: c.get(k) for k in ('calls', 'tok', 'usd')}))
    for aid, c in costs.items():  # transcripts with no hook record (hooks not registered yet): cost only, labelled
        if aid not in s['agents'] and not any(r['id'].endswith(aid) for r in rows):
            rows.append(dict(id=aid, type='?', status='no-hook-record', desc='', flags=[], calls=c['calls'], tok=c['tok'], usd=c['usd']))
    return rows


def verify_compact(sid, summary, out=None):
    """Compare the PreCompact continuation note with the summary the model kept. Deterministic, text only.
    verdict: ok (>= half of the key terms present) | weak | unknown (no summary text or no note: never guessed)."""
    import re
    note = os.path.join(out or sdir(), f"compact-{sid}.md")
    if not isinstance(summary, str) or not summary.strip() or not os.path.isfile(note):
        return dict(verdict='unknown', note=note if os.path.isfile(note) else '')
    txt = open(note).read()
    terms = []
    for ln in txt.splitlines()[1:]:  # key facts: file names, the owner's last ask words, test command
        for w in re.findall(r"[\w./-]{5,}", ln.split(':', 1)[-1]):
            w = w.strip('./-')
            if len(w) >= 5 and w.lower() not in ('changed', 'files', 'uncommitted', 'recorded', 'before', 'claiming', 'rerun', 'above', 'found', 'asked', 'check', 'summary', 'daily', 'handoff', 'step', 'test') and w not in terms:
                terms.append(w)
    terms = terms[:12]
    s_low = summary.lower()
    miss = [w for w in terms if w.lower() not in s_low]
    hit = len(terms) - len(miss)
    return dict(verdict=('ok' if terms and hit * 2 >= len(terms) else 'weak' if terms else 'unknown'), hit=hit, of=len(terms), missing=miss[:8], note=note)


def discovered(session, names):
    def fn(s):
        for n in names:
            _bump(s['skills']['discovered'], n)
    edit(session, fn)


def timing(session, ev, ms, chars, failed=False):
    def fn(s):
        h = s['hooks'].setdefault(ev, {'n': 0, 'ms': 0.0, 'max': 0.0, 'chars': 0})
        h['fail'] = h.get('fail', 0) + (1 if failed else 0)
        h['samples'] = (h.get('samples', []) + [round(ms, 1)])[-200:]
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
    ap.add_argument('cmd', nargs='?', default='show', choices=['show', 'skills', 'agents', 'roi'])
    ap.add_argument('--session')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    sid = a.session or latest_session()
    s = _load(path(sid)) if sid else blank()
    if a.cmd == 'roi':
        r = roi(sid, s)
        if a.json:
            print(json.dumps(r)); return 0
        tot = sum(x['usd'] or 0 for x in r)
        print(f"agent ROI this session ({sid or 'none'}): {len(r)} agents, ~${tot:.2f} [tokens MEASURED, $ EST list price]; flags are advice, not verdicts")
        for x in r:
            print(f"  {x['status']:14} {x['type']} calls {x['calls']} tok {x['tok']} ~${x['usd'] or 0:.2f} {','.join(x['flags']) or 'ok'} '{x['desc']}'")
        return 0
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
        try:  # per-subagent cost from this session's subagent transcripts [measured tokens, EST $]
            for k, c in agent_costs(sid).items():
                print(f"  {k}: {c['calls']} calls, {c['tok']:,} input-eq+out tok, ~${c['usd']:.2f} [EST API-equivalent list price]")
        except Exception:
            pass
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
