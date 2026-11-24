#!/usr/bin/env python3
"""TOKEN ZOMBIE policy engine: deterministic advice rules, no model call, NEVER blocks a tool call.
evaluate(event, state) is pure (no mutation); update(event, state) records what the rules need.
User overrides: ~/.claude/token-zombie/policy.json (deep-merged over DEFAULT). Kill switch: TZ_POLICY=0."""
import json, os, re, sys

DEFAULT = {'rules': {
    'read_cap_lines': {'id': 'read_cap_lines', 'enabled': True, 'threshold': 800,
        'message': 'Read of {path} (~{n} lines) without offset/limit: grep -n first, then Read a range.'},
    'bash_output_cap': {'id': 'bash_output_cap', 'enabled': True, 'threshold': 200000,
        'message': 'This command may dump a lot of output: add head/tail/-n, grep it, or run it through rtk.'},
    'context_pct': {'id': 'context_pct', 'enabled': True, 'threshold': [70, 85, 95],
        'message': 'Context is {pct}% full: finish the task, write the handoff, then continue in a fresh chat.'},
    'dup_read': {'id': 'dup_read', 'enabled': True, 'threshold': 1,
        'message': '{path} was already read in this session: reuse what you have, or read only a range.'},
    'churn': {'id': 'churn', 'enabled': True, 'threshold': 5,
        'message': '{path} was edited {n} times: stop and re-plan; batch the changes into one edit.'},
    'gate': {'id': 'gate', 'enabled': True,
        'threshold': r'\b(git\s+push|git\s+commit|npm\s+publish|npm\s+install|pip\s+install|brew\s+install|yarn\s+publish|twine\s+upload|gh\s+release|docker\s+push|vercel\s+--prod|deploy|purchase|checkout|stripe)\b',
        'message': 'This looks like publish/commit/push/install/paid work: needs owner approval first.'},
    'fake_green': {'id': 'fake_green', 'enabled': True,
        'threshold': r'(\.skip\(|@pytest\.mark\.skip|@unittest\.skip|\bxfail\b|\bxit\(|\bxdescribe\(|\bt\.Skip\(|#\[ignore\])',
        'message': 'Edit to {path} disables or skips a test: fix the cause instead; a skipped test is a fake green.'},
    'prefix_edit': {'id': 'prefix_edit', 'enabled': True,
        'message': '{path} is part of the cached prompt prefix: editing it mid-chat makes the next turn re-write the whole cache. Batch such edits, or do them between tasks.'},
    'spawn_cap': {'id': 'spawn_cap', 'enabled': True, 'threshold': 6,
        'message': '{n} subagents started this session (each re-sends its report): batch the work or do it here.'},
}}
_cache = {}
WARN = []


def home():
    return os.environ.get('HOME') or os.path.expanduser('~')


def path():
    return os.path.join(home(), '.claude', 'token-zombie', 'policy.json')


def _merge(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def load():
    """Default policy + user file, cached by (path, mtime). Bad JSON -> defaults + warning in WARN."""
    p = path()
    try:
        mt = os.stat(p).st_mtime_ns
    except OSError:
        mt = None
    if _cache.get('k') == (p, mt):
        return _cache['v']
    pol = json.loads(json.dumps(DEFAULT))
    del WARN[:]
    if mt is not None:
        try:
            u = json.load(open(p))
            if not isinstance(u, dict):
                raise ValueError('top level must be an object')
            _merge(pol, u)
        except Exception as e:
            pol = json.loads(json.dumps(DEFAULT))
            WARN.append(f'policy.json ignored ({e}); using defaults')
    _cache['k'], _cache['v'] = (p, mt), pol
    return pol


def _r(pol, rid):
    r = (pol.get('rules') or {}).get(rid)
    return r if isinstance(r, dict) and r.get('enabled', True) else None


def _msg(r, **kw):
    try:
        return str(r.get('message', '')).format(**kw)
    except Exception:
        return str(r.get('message', ''))


def _lines(f, need):
    try:
        if os.path.getsize(f) < need:
            return 0
        with open(f, 'rb') as h:
            return h.read(8 << 20).count(b'\n') + 1
    except OSError:
        return 0


def _bigcmd(cmd, cap):
    if re.search(r'\|\s*(head|tail|wc|rtk|less)\b|\brtk\b|\bhead\b|\btail\b|>\s*\S', cmd):
        return False
    m = re.search(r'\bcat\s+(\S+)', cmd)
    if m:
        try:
            return os.path.getsize(os.path.expanduser(m.group(1))) > cap
        except OSError:
            pass
    if re.search(r'\bfind\s+/(\s|$)', cmd):
        return True
    if re.search(r'\bgit\s+log\b', cmd) and not re.search(r'(\s-n\s*\d|\s-\d+\b|--max-count|--oneline\s+-\d)', cmd):
        return True
    return False


def evaluate(event, state=None, pol=None):
    state = state or {}
    pol = pol or load()
    out = []
    tool = event.get('tool_name') or ''
    ti = event.get('tool_input') or {}
    f = ti.get('file_path') or ''

    def add(r, lvl, **kw):
        out.append({'id': r['id'], 'level': lvl, 'message': _msg(r, **kw)})

    r = _r(pol, 'read_cap_lines')
    if r and tool == 'Read' and f and not ti.get('offset') and not ti.get('limit'):
        n = event.get('line_count') or _lines(f, int(r.get('threshold', 800)))
        if n > int(r.get('threshold', 800)):
            add(r, 'warn', path=f, n=n)
    r = _r(pol, 'dup_read')
    if r and tool == 'Read' and f and (state.get('reads') or {}).get(f, 0) >= int(r.get('threshold', 1)):
        add(r, 'info', path=f, n=state['reads'][f])
    r = _r(pol, 'churn')
    if r and tool in ('Edit', 'Write', 'MultiEdit', 'NotebookEdit') and f:
        n = (state.get('edits') or {}).get(f, 0) + 1
        if n > int(r.get('threshold', 5)):
            add(r, 'warn', path=f, n=n)
    r = _r(pol, 'fake_green')
    if r and tool in ('Edit', 'Write', 'MultiEdit') and re.search(r'(^|/)(tests?/|test_[^/]*$|[^/]*(_test|\.test|\.spec)\.\w+$)', f):
        try:
            if re.search(str(r.get('threshold')), str(ti.get('new_string') or ti.get('content') or '')):
                add(r, 'warn', path=f)
        except re.error:
            pass
    r = _r(pol, 'prefix_edit')
    if r and tool in ('Edit', 'Write', 'MultiEdit') and re.search(r'(^|/)(CLAUDE\.md|settings(\.local)?\.json|SKILL\.md|\.mcp\.json)$', f):
        add(r, 'info', path=f)
    r = _r(pol, 'spawn_cap')
    if r and tool in ('Agent', 'Task') and (state.get('spawns', 0) + 1) > int(r.get('threshold', 6)):
        add(r, 'warn', n=state.get('spawns', 0) + 1)
    cmd = ti.get('command') or ''
    if tool == 'Bash' and cmd:
        r = _r(pol, 'bash_output_cap')
        if r and _bigcmd(cmd, int(r.get('threshold', 200000))):
            add(r, 'warn')
        r = _r(pol, 'gate')
        if r:
            try:
                if re.search(str(r.get('threshold')), cmd, re.I):
                    add(r, 'gate')
            except re.error:
                pass
    r = _r(pol, 'context_pct')
    if r:
        pct = event.get('context_pct')
        if pct is None and event.get('context_tokens') and event.get('context_window'):
            pct = 100.0 * event['context_tokens'] / event['context_window']
        if isinstance(pct, (int, float)):
            tiers = sorted(r.get('threshold') or [])
            hit = [t for t in tiers if pct >= t]
            if hit and hit[-1] > state.get('ctx_level', 0):
                add(r, 'alert' if hit[-1] >= 95 else 'warn', pct=int(pct))
    return out


def update(event, state):
    """Record what the rules need (mutates state). Call after evaluate."""
    tool = event.get('tool_name') or ''
    f = (event.get('tool_input') or {}).get('file_path') or ''
    if f and tool == 'Read':
        state.setdefault('reads', {})[f] = state.get('reads', {}).get(f, 0) + 1
    elif f and tool in ('Edit', 'Write', 'MultiEdit', 'NotebookEdit'):
        state.setdefault('edits', {})[f] = state.get('edits', {}).get(f, 0) + 1
    if tool in ('Agent', 'Task'):
        state['spawns'] = state.get('spawns', 0) + 1
    pct = event.get('context_pct')
    if isinstance(pct, (int, float)):
        hit = [t for t in sorted((_r(load(), 'context_pct') or {}).get('threshold') or []) if pct >= t]
        if hit:
            state['ctx_level'] = hit[-1]
    return state


def _spath(sid):
    return os.path.join(home(), '.claude', 'token-zombie', 'policy-' + re.sub(r'\W', '_', sid or 'x') + '.json')


def hook_advice(data):
    """Used by tz-guard on PreToolUse: advice text or ''. Never raises, never blocks."""
    if os.environ.get('TZ_POLICY') == '0':
        return ''
    try:
        tool = data.get('tool_name') or ''
        if tool not in ('Read', 'Edit', 'Write', 'MultiEdit', 'NotebookEdit', 'Bash', 'Agent', 'Task'):
            return ''
        sp = _spath(data.get('session_id'))
        st = {}
        if tool != 'Bash':
            try:
                st = json.load(open(sp))
            except (OSError, ValueError):
                st = {}
        al = evaluate(data, st)
        if tool != 'Bash':
            update(data, st)
            os.makedirs(os.path.dirname(sp), exist_ok=True)
            json.dump(st, open(sp, 'w'))
        if not al:
            return ''
        return '\n'.join('TOKEN ZOMBIE policy (advice, not a block) [%s]: %s' % (a['id'], a['message']) for a in al)
    except Exception:
        return ''


def main(argv):
    a = list(argv)
    cmd = a[0] if a else 'show'
    if cmd == 'show':
        print(json.dumps(load(), indent=2))
        for w in WARN:
            print('warning: ' + w, file=sys.stderr)
        return 0
    if cmd == 'check' and len(a) > 1:
        try:
            ev = json.load(open(a[1]))
        except Exception as e:
            print('bad event file: %s' % e, file=sys.stderr)
            return 2
        load()
        for w in WARN:
            print('warning: ' + w, file=sys.stderr)
        al = evaluate(ev, ev.get('state') or {})
        for x in al:
            print('[%s] %s: %s' % (x['level'], x['id'], x['message']))
        if not al:
            print('no advice')
        return 0
    if cmd == 'init':
        p = path()
        if os.path.exists(p):
            print('exists: ' + p)
            return 0
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(DEFAULT, open(p, 'w'), indent=2)
        print('wrote ' + p)
        return 0
    print('usage: tz policy show|check EVENT.json|init', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
