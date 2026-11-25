#!/usr/bin/env python3
# Context continuity: one compact authoritative state file + expensive-chat detection + waste self-audit.
#   tz state [--cwd D]                 build/refresh handoffs/STATE.md from the repo (sections rewritten only when their facts change)
#   tz expensive [--cwd D] [--transcript F] [--session S]   real signals -> verified checkpoint + fresh-session startup line
#   tz waste-audit [--cwd D] [--transcript F]             duplicated handoff docs, repeated reads, long/repeated pasted briefs
# Never rewrites HANDOFF.md or dated handoffs; never runs tests or commands other than read-only git.
import glob, hashlib, json, os, re, sys, time

D = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, D)
STATE_MAX = 60      # lines in STATE.md
BRIEF_MIN = 2000    # chars: a user message this long counts as a pasted brief
SPEND_X = 20        # expensive when input-equivalent spend >= SPEND_X * limit (cache read 0.1x, write 1.25x, output 5x)


def _h(s):
    return hashlib.sha1(s.encode()).hexdigest()[:10]


def _lines(p, n=None):
    try:
        L = open(p, encoding='utf-8', errors='ignore').read().splitlines()
    except OSError:
        return []
    return L if n is None else L[:n]


def master(cwd):
    from tzhandoff import memory_tail
    from tzlib import cfg
    obj = next((l.strip('*# ').strip() for l in _lines(os.path.join(cwd, 'README.md'), 40)
                if l.strip() and not l.startswith(('#', '<', '!', '[', '|'))), 'not set (README.md first line)')
    arch = []
    for d in sorted(os.listdir(cwd)) if os.path.isdir(cwd) else []:
        p = os.path.join(cwd, d)
        if os.path.isdir(p) and not d.startswith('.') and d not in ('handoffs', 'node_modules'):
            arch.append(f'{d}/ {len(os.listdir(p))}')
    dec = memory_tail(cwd, 6)
    return ['## Master', f'Objective: {obj[:200]}', 'Architecture: ' + (', '.join(arch[:12]) or 'flat'),
            'Decisions: ' + ('' if dec else 'none yet (tz handoff --remember FACT)'), *[f'  {d}' for d in dec],
            f"Limits: fresh chat at {cfg('limit') // 1000}k, hand off at {cfg('hard') // 1000}k past start; "
            'gates (paid/commit/install/publish) need owner approval']


def current(cwd):
    import tznext, tzhandoff
    ts = tznext.load(cwd)
    rd = {t['id'] for t in tznext.ready(ts)}
    by = {k: [t['id'] for t in ts.values() if f(t)] for k, f in (
        ('done', lambda t: t['status'] == 'done'), ('active', lambda t: t['status'] == 'active'),
        ('blocked', lambda t: t['status'] == 'blocked' or t['status'] == 'pending' and t['id'] not in rd),
        ('pending', lambda t: t['status'] == 'pending' and t['id'] in rd))}
    try:
        h = json.load(open(tzhandoff.newest_task(cwd) or ''))
    except (OSError, ValueError):
        h = {}
    snap = tzhandoff.snapshot(cwd)
    act = tznext.active(cwd)
    te = (act or {}).get('test') or {}
    ht = h.get('test') or {}
    test = (f"{te['cmd']} -> {'PASS' if te['ok'] else 'FAIL'} ({te.get('time', '')})" if te.get('cmd') else
            f"{ht['cmd']} -> {'PASS' if ht['ok'] else 'FAIL' if ht['ok'] is False else 'not run'} ({h.get('time', '')})"
            if ht.get('cmd') else 'none recorded')
    ch = list(snap['changed'])
    return ['## Current work', *[f'{k.capitalize()}: ' + (', '.join(v) or 'none') for k, v in by.items()],
            'Files changed: ' + ((', '.join(ch[:12]) + (f' +{len(ch) - 12} more' if len(ch) > 12 else '')) or 'none'),
            f"Git: {snap['branch']}@{snap['head']}, {len(ch)} uncommitted" if snap['repo'] else 'Git: not a repo',
            f'Tests: {test}',
            'Next action: ' + ((act or {}).get('next') or h.get('next') or 'not set (tz next add / tz handoff --next)')]


def session(cwd):
    hs = [f for f in glob.glob(os.path.join(cwd, 'handoffs', '*.md')) if os.path.basename(f) not in ('STATE.md', 'MASTER.md', 'DAILY.md')]
    new = max(hs, key=os.path.getmtime) if hs else ''
    title = next((l.lstrip('# ').strip() for l in _lines(new, 5) if l.strip()), '') if new else ''
    return ['## Session handoff', f'Newest note: {os.path.relpath(new, cwd) if new else "none"}' + (f' ({title[:80]})' if title else ''),
            'Fresh chat: read only this file, then `tz resume` (verifies git + tests) and `tz next pack`.']


def build(cwd):
    secs = {'master': master(cwd), 'current': current(cwd), 'session': session(cwd)}
    return {k: '\n'.join(v) for k, v in secs.items()}


def write_state(cwd):
    """Rewrite STATE.md only if a section's facts changed. Returns (path, [changed section names])."""
    p = os.path.join(cwd, 'handoffs', 'STATE.md')
    new = build(cwd)
    old = {}
    for l in _lines(p, 3):
        m = re.match(r'<!-- tz-state (.*) -->', l)
        if m:
            old = dict(x.split('=') for x in m.group(1).split())
    hs = {k: _h(v) for k, v in new.items()}
    changed = [k for k in hs if old.get(k) != hs[k]]
    if changed:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        body = ['# STATE (tz, authoritative, compact; refresh: tz state)',
                '<!-- tz-state ' + ' '.join(f'{k}={v}' for k, v in hs.items()) + ' -->',
                f"Updated {time.strftime('%Y-%m-%d %H:%M')}", *'\n'.join(new.values()).splitlines()]
        open(p + '.tmp', 'w', encoding='utf-8').write('\n'.join(body[:STATE_MAX]) + '\n')
        os.replace(p + '.tmp', p)
    return p, changed


def signals(transcript, session_id='x'):
    """Real signals. Each value is (number, basis). Cache reads are cheap re-sends, weighted 0.1x, never called waste."""
    from tzusage import totals
    from tzopt import STATE, _load
    u = totals(transcript)
    reads = _load(os.path.join(STATE, f'reads-{session_id}.json'), {})
    rep = sum(1 for v in reads.values() if isinstance(v, dict) and v.get('n', 1) >= 2)
    spend = int(u['inp'] + u['cr'] * CR + u['cw'] * CW + u['out'] * 5)
    return {'ctx': (u['last'], 'actual' if u['turns'] else 'unknown'), 'turns': (u['turns'], 'actual'),
            'spend_eq': (spend, 'est' if u['turns'] else 'unknown'), 'repeat_reads': (rep, 'measured'),
            'cache_read': (u['cr'], 'actual')}


def is_expensive(sig):
    from tzlib import cfg
    lim = cfg('limit')
    why = []
    if sig['ctx'][0] >= lim:
        why.append(f"context {sig['ctx'][0] // 1000}k [actual] >= {lim // 1000}k")
    if sig['spend_eq'][0] >= SPEND_X * lim:
        why.append(f"spend ~{sig['spend_eq'][0] // 1000}k input-eq [est]")
    if sig['repeat_reads'][0] >= 3 and sig['ctx'][0] >= lim // 2:
        why.append(f"{sig['repeat_reads'][0]} repeated reads [measured]")
    return why


def startup_line(cwd):
    return (f'MANUAL STEP (the desktop app cannot switch chats for you): open a NEW chat in {cwd} and send only:\n'
            '  Continue from handoffs/STATE.md. Run `tz resume` first; read only the files it names.')


def expensive(cwd, transcript, session_id='x', force=False, growth=None):
    """(text, fired). Fires: checkpoint + STATE.md + verification that STATE.md git line matches git now."""
    sig = signals(transcript, session_id)
    if growth is not None:  # hook: judge context by growth past the chat start (startup load is not this chat's cost)
        sig['ctx'] = (growth, 'actual')
    why = is_expensive(sig)
    L = ['signals: ' + ', '.join(f'{k} {v} [{b}]' for k, (v, b) in sig.items())]
    if not why and not force:
        return '\n'.join(L + ['not expensive yet: keep going']), False
    import tznext, tzhandoff
    tznext.checkpoint(cwd, 'expensive')
    p, _ = write_state(cwd)
    snap = tzhandoff.snapshot(cwd)
    git_now = f"Git: {snap['branch']}@{snap['head']}, {len(snap['changed'])} uncommitted" if snap['repo'] else 'Git: not a repo'
    ok = git_now in _lines(p)
    L += ['EXPENSIVE: ' + ('; '.join(why) or 'forced'),
          f"checkpoint {'VERIFIED' if ok else 'NOT verified (git changed while saving; run tz state)'}: {os.path.relpath(p, cwd)} ({git_now})",
          startup_line(cwd)]
    return '\n'.join(L), True


def on_prompt(data, growth=None):
    """Hook (UserPromptSubmit): fire once per session when expensive. Returns text for additionalContext or ''."""
    from tzopt import STATE
    s = data.get('session_id', 'x')
    mark = os.path.join(STATE, f'cont-{s}')
    if os.path.exists(mark):
        return ''
    cwd = data.get('cwd') or os.getcwd()
    txt, fired = expensive(cwd, data.get('transcript_path'), s, growth=growth)
    if not fired:
        return ''
    os.makedirs(STATE, exist_ok=True)
    open(mark, 'w').write(str(int(time.time())))
    return 'TOKEN ZOMBIE: ' + txt.split('\n', 1)[1] + '\nTell the owner the manual step at the next safe point.'


def _user_texts(transcript):
    out = []
    for l in _lines(transcript or ''):
        if '"user"' not in l:
            continue
        try:
            m = json.loads(l).get('message') or {}
        except ValueError:
            continue
        if m.get('role') != 'user':
            continue
        c = m.get('content')
        t = c if isinstance(c, str) else ''.join(x.get('text', '') for x in c if isinstance(x, dict) and x.get('type') == 'text') if isinstance(c, list) else ''
        if t.strip():
            out.append(t)
    return out


def waste_audit(cwd, transcript=None):
    """Lines of findings. basis tags: measured (counted here) / est (chars//4)."""
    from tzopt import ET, STATE, _load
    L = []
    docs = glob.glob(os.path.join(cwd, 'handoffs', '*.md')) + [p for p in (os.path.join(cwd, 'HANDOFF.md'),) if os.path.exists(p)]
    seen, dup = {}, {}
    for f in docs:
        for l in _lines(f):
            k = ' '.join(l.lower().split())
            if len(k) >= 40:
                seen.setdefault(k, set()).add(os.path.basename(f))
    for k, fs in seen.items():
        if len(fs) > 1:
            dup[k] = fs
    chars = sum(len(k) * (len(fs) - 1) for k, fs in dup.items())
    tot = sum(os.path.getsize(f) for f in docs)
    L.append(f'handoff docs [measured]: {len(docs)} files, {tot // 1000}k chars; {len(dup)} lines repeated across files '
             f'(~{ET(chars)} tok [est] duplicated)' + ('; keep facts in STATE.md/MASTER.md, dated notes <=30 lines' if dup else ''))
    big = sorted(((os.path.getsize(f), os.path.basename(f)) for f in docs if os.path.getsize(f) > 4000), reverse=True)
    for n, f in big[:3]:
        L.append(f'  long note {f} ({n // 1000}k chars, >30-line rule): a fresh chat reading it pays ~{ET(n)} tok [est]')
    rr = []
    for p in glob.glob(os.path.join(STATE, 'reads-*.json')):
        for k, v in _load(p, {}).items():
            if isinstance(v, dict) and v.get('n', 1) >= 2:
                rr.append((v['n'], k.split('|')[0]))
    L.append(f'repeated unchanged reads [measured]: {len(rr)}' + (' (' + ', '.join(f'{os.path.basename(f)} x{n}' for n, f in sorted(rr, reverse=True)[:5]) + ')' if rr else ''))
    us = _user_texts(transcript)
    if transcript:
        briefs = [t for t in us if len(t) >= BRIEF_MIN]
        heads = {}
        for t in briefs:
            heads.setdefault(_h(' '.join(t.split())[:300]), []).append(len(t))
        rep = sum(sum(v[1:]) for v in heads.values() if len(v) > 1)
        L.append(f'pasted briefs [measured]: {len(briefs)} user messages >= {BRIEF_MIN} chars; repeats cost ~{ET(rep)} tok [est] each re-send'
                 + ('; save the brief to a file once and refer to it' if briefs else ''))
    else:
        L.append('pasted briefs: unknown (no chat log; pass --transcript)')
    return L


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='tz state|expensive|waste-audit')
    ap.add_argument('cmd', choices=['state', 'expensive', 'waste-audit', 'replay'])
    ap.add_argument('--cwd', default=os.getcwd())
    ap.add_argument('--transcript')
    ap.add_argument('--session', default='x')
    ap.add_argument('--force', action='store_true', help='expensive: checkpoint now even below the thresholds')
    ap.add_argument('file', nargs='?', help='replay: transcript .jsonl (default: newest of this folder)')
    a = ap.parse_args(argv)
    if a.file:
        a.transcript = a.file
    if not os.path.isdir(a.cwd):
        print(f'tz {a.cmd}: not a directory: {a.cwd}', file=sys.stderr)
        return 1
    if a.cmd != 'state' and not a.transcript:
        from tzusage import find_transcript
        a.transcript = find_transcript(a.cwd)
    if a.cmd == 'state':
        p, ch = write_state(a.cwd)
        print(f"{os.path.relpath(p, a.cwd)}: " + (f"updated sections {', '.join(ch)}" if ch else 'unchanged (no facts changed)'))
    elif a.cmd == 'expensive':
        print(expensive(a.cwd, a.transcript, a.session, a.force)[0])
    elif a.cmd == 'replay':
        print('\n'.join(replay_lines(a.transcript)))
    else:
        print('\n'.join(waste_audit(a.cwd, a.transcript)))
    return 0


# ---- replay and skill effectiveness (read-only over local transcripts) ----
def _tooluses(d):
    c = (d.get('message') or {}).get('content')
    return [b for b in c if isinstance(b, dict) and b.get('type') == 'tool_use'] if isinstance(c, list) else []


def replay(path, top=10):
    """Per API reply: input-eq [measured from usage] + tools used. Returns (total, steps, top, repeated)
    steps = [(n, ieq, tools)], top = costliest `top`, repeated = [(fingerprint label, count)] for tool+input seen 2+ times."""
    msgs, order = {}, []
    for l in _lines(path or ''):
        if '"usage"' not in l and '"tool_use"' not in l:
            continue
        try:
            d = json.loads(l)
        except ValueError:
            continue
        m = d.get('message') or {}
        mid = m.get('id')
        if d.get('type') != 'assistant' or not mid:
            continue
        r = msgs.get(mid)
        if r is None:
            r = msgs[mid] = {'u': None, 'tools': []}
            order.append(mid)
        if isinstance(m.get('usage'), dict):
            r['u'] = m['usage']
        r['tools'] += [(b.get('name') or '?', _h(json.dumps(b.get('input'), sort_keys=True, default=str)), b.get('input') or {}) for b in _tooluses(d)]
    steps, fp = [], {}
    for n, mid in enumerate(order, 1):
        r = msgs[mid]
        u = r['u'] or {}
        c = (0, *(u.get(k) or 0 for k in ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens', 'output_tokens')), '', _w1h(u))
        names = [t[0] for t in r['tools']]
        steps.append((n, ieq(c), names))
        for name, h, ti in r['tools']:
            lab = name + ' ' + str(ti.get('command') or ti.get('file_path') or ti.get('pattern') or ti.get('skill') or '')[:60]
            e = fp.setdefault((name, h), [lab.strip(), 0])
            e[1] += 1
    rep = sorted(((v[0], v[1]) for v in fp.values() if v[1] > 1), key=lambda x: -x[1])
    return sum(x[1] for x in steps), steps, sorted(steps, key=lambda x: -x[1])[:top], rep


def replay_lines(path):
    tot, steps, top, rep = replay(path)
    if not steps:
        return ['replay: no assistant replies with usage in this transcript']
    out = [f'REPLAY {len(steps)} replies, {tot / 1000:.0f}k input-eq [measured usage: input 1x, cache read 0.1x, cache write 1.25x, 1 h-TTL write 2x]',
           'costliest steps:']
    out += [f"  #{n:<4} {v / 1000:7.1f}k  {100 * v / (tot or 1):4.1f}%  {', '.join(t) or '(text only)'}" for n, v, t in top]
    out.append('repeated tool calls (same tool + input):' if rep else 'repeated tool calls: none')
    out += [f'  {c}x  {lab}' for lab, c in rep[:10]]
    return out


_PASS = re.compile(r'\b\d+\s+passed\b|\b\d+/0\b|all tests? passed|\bOK \(\d+ tests?\)|\b0 failed\b', re.I)
_FAIL = re.compile(r'(?i:\b[1-9]\d*\s+(?:failed|failures?)\b|\b\d+/[1-9]\d*\s+fail)|\bFAILED\b')


def _result_text(d):
    c = (d.get('message') or {}).get('content')
    if not isinstance(c, list):
        return ''
    out = []
    for b in c:
        if isinstance(b, dict) and b.get('type') == 'tool_result':
            x = b.get('content')
            out.append(x if isinstance(x, str) else ' '.join(y.get('text', '') for y in x if isinstance(y, dict)) if isinstance(x, list) else '')
    return ' '.join(out)


def skill_effect(root=None, days=30, now=None):
    """Per skill invoked via the Skill tool, from ~/.claude/projects/**/*.jsonl (local, last `days` days):
    {skill: {'uses', 'chats', 'avg_tok' (input-eq of the chat AFTER first use, mean), 'pass', 'tests'}}.
    pass/tests = chats with a test line where the LAST test line passed. Attribution is EST: tokens after a skill are not caused by it."""
    from tzusage import _ts
    root = root or os.path.expanduser('~/.claude/projects')
    now = now or time.time()
    agg = {}
    for p in glob.glob(os.path.join(root, '**', '*.jsonl'), recursive=True):
        if '/subagents/' in p or now - os.path.getmtime(p) > days * 86400:
            continue
        first, uses, last_test, after = {}, {}, None, {}
        seen = set()
        for l in _lines(p):
            if '"Skill"' not in l and '"usage"' not in l and 'tool_result' not in l:
                continue
            try:
                d = json.loads(l)
            except ValueError:
                continue
            ts = _ts(d.get('timestamp')) or 0
            for b in _tooluses(d):
                if b.get('name') == 'Skill' and (b.get('input') or {}).get('skill'):
                    k = str(b['input']['skill'])
                    uses[k] = uses.get(k, 0) + 1
                    first.setdefault(k, ts)
                    after.setdefault(k, 0.0)
            m = d.get('message') or {}
            u = m.get('usage')
            if isinstance(u, dict) and m.get('id') not in seen:
                seen.add(m.get('id'))
                v = ieq((0, *(u.get(k) or 0 for k in ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens', 'output_tokens')), '', _w1h(u)))
                for k in first:
                    after[k] += v
            if d.get('type') == 'user':
                t = _result_text(d)
                if t and _FAIL.search(t):
                    last_test = False
                elif t and _PASS.search(t):
                    last_test = True
        for k, n in uses.items():
            a = agg.setdefault(k, {'uses': 0, 'chats': 0, 'tok': 0.0, 'pass': 0, 'tests': 0})
            a['uses'] += n
            a['chats'] += 1
            a['tok'] += after[k]
            if last_test is not None:
                a['tests'] += 1
                a['pass'] += bool(last_test)
    for a in agg.values():
        a['avg_tok'] = a['tok'] / a['chats']
    return agg


def skill_effect_lines(agg):
    if not agg:
        return ['skill effectiveness: no Skill-tool use found in the last 30 days of local logs']
    out = ['SKILL EFFECTIVENESS [EST, local logs 30 d; tokens = input-eq of the chat after the first use, not caused by the skill alone]',
           f"{'skill':<34}{'uses':>5}{'chats':>6}{'avg tok after':>14}{'tests passing':>15}"]
    for k, a in sorted(agg.items(), key=lambda x: -x[1]['uses']):
        pas = f"{a['pass']}/{a['tests']}" if a['tests'] else 'no test line'
        out.append(f"{k[:33]:<34}{a['uses']:>5}{a['chats']:>6}{a['avg_tok'] / 1000:>13.0f}k{pas:>15}")
    return out


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))


# Early churn detection (advice only, never blocks). PostToolUse counts, UserPromptSubmit judges; tiny JSON per session.
CHURN_N = 3          # same file edited/re-read N+ times, N+ images, same instruction N times
GROW_FAST = 30000    # tokens grown since last prompt ...
EDIT_SMALL = 2000    # ... while edits stayed under this many chars
DOCS = ('.md', '.txt', '.rst', '.png', '.jpg', '.jpeg', '.gif', '.webp')
TEST_RE = re.compile(r'\b(pytest|unittest|jest|vitest|mocha|go test|cargo test|rspec|phpunit|(npm|yarn|pnpm|bun)( run)? test|make test|run_all\.sh|tests?/\S+\.sh)\b')
FAIL_RE = re.compile(r'\b[1-9]\d* (failed|failing|errors?)\b|\bFAIL(ED)?\b|Traceback|AssertionError|exit code [1-9]')
IMG = ('.png', '.jpg', '.jpeg', '.gif', '.webp')


def _churn_path(s):
    from tzopt import STATE
    return os.path.join(STATE, f'churn-{s}.json')


def _churn_rw(s, fn):
    from tzopt import _load
    p = _churn_path(s)
    st = _load(p, {})
    st = st if isinstance(st, dict) else {}
    for k in ('files', 'said', 'prompts'):
        st.setdefault(k, {})
    out = fn(st)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p + '.tmp', 'w').write(json.dumps(st))
    os.replace(p + '.tmp', p)
    return out


def churn_tool(data):
    """PostToolUse: count per-file edits/reads, image reads, edit chars since the last prompt."""
    tool = data.get('tool_name') or ''
    if tool == 'Bash':
        return code_test(data)
    if tool not in ('Read', 'Edit', 'Write', 'MultiEdit', 'NotebookEdit'):
        return
    ti = data.get('tool_input') or {}
    f = ti.get('file_path') or ti.get('notebook_path') or ''

    def up(st):
        if tool != 'Read' and f and not f.lower().endswith(DOCS):
            c = st.setdefault('code', {})
            c['edits'] = c.get('edits', 0) + 1
            c['unt'] = c.get('unt', 0) + 1
            _pub_code(data.get('session_id', 'x'), c)
        if tool == 'Read' and f.lower().endswith(IMG):
            st['img'] = st.get('img', 0) + 1
        elif f:
            st['files'][f] = st['files'].get(f, 0) + 1
        if tool != 'Read':
            st['edit_chars'] = st.get('edit_chars', 0) + len(json.dumps(ti))
    _churn_rw(data.get('session_id', 'x'), up)


def _pub_code(sid, c):
    """coding.json: latest coding counters for the panel's OPTIMIZATIONS pane (one tiny atomic write per edit/test run)."""
    from tzopt import STATE
    try:
        p = os.path.join(STATE, 'coding.json')
        open(p + '.tmp', 'w').write(json.dumps({'ts': int(time.time()), 'sid': sid, **{k: c.get(k) for k in ('edits', 'runs', 'last', 'unt')}}))
        os.replace(p + '.tmp', p)
    except OSError:
        pass


def code_test(data):
    """PostToolUse Bash: a test command ran -> clear untested edits, keep the last result (heuristic on the output text)."""
    cmd = (data.get('tool_input') or {}).get('command') or ''
    if not TEST_RE.search(cmd):
        return
    r = data.get('tool_response')
    txt = json.dumps(r) if not isinstance(r, str) else r
    res = 'fail' if FAIL_RE.search(txt or '') else 'pass'

    def up(st):
        c = st.setdefault('code', {})
        c['unt'], c['runs'], c['last'] = 0, c.get('runs', 0) + 1, res
        _pub_code(data.get('session_id', 'x'), c)
    _churn_rw(data.get('session_id', 'x'), up)


def code_line(sid):
    """`tz stats`: coding quality row, '' if no code was edited in this chat. Counts are MEASURED from tool calls; pass/fail is read from output text."""
    c = _churn_rw(sid, lambda st: dict(st.get('code') or {}))
    if not c.get('edits'):
        return ''
    return (f"coding [MEASURED counts, result read from output text]: {c['edits']} code edits, {c.get('runs', 0)} test runs, "
            f"last test {c.get('last', 'none')}, {c.get('unt', 0)} edits untested")


def untested_advice(data):
    """Stop: code edited and no test since -> one advice line per edit count; never blocks."""
    def chk(st):
        c = st.get('code') or {}
        k = 'U%d' % c.get('edits', 0)
        if not c.get('unt') or k in st['said']:
            return ''
        st['said'][k] = 1
        return (f"TOKEN ZOMBIE: {c['unt']} code edit(s) with no test run since; run the tests before calling it done"
                + (' (last test failed)' if c.get('last') == 'fail' else ''))
    return _churn_rw(data.get('session_id', 'x'), chk)


def churn_step(data):
    """PostToolUse (any tool): steps and last activity time, for the stay-or-fresh estimate."""
    def up(st):
        st['steps'] = st.get('steps', 0) + 1
        st['t'] = time.time()
    _churn_rw(data.get('session_id', 'x'), up)


def churn_prompt(data, used):
    """UserPromptSubmit: one line of checkpoint advice per NEW signal (each fires once per session), or ''."""
    prompt = ' '.join((data.get('prompt') or '').lower().split())

    def judge(st):
        sig = []
        for f, n in st['files'].items():
            if n >= CHURN_N and f not in st['said']:
                st['said'][f] = 1
                sig.append(f'{os.path.basename(f)} edited/read {n}x')
        if st.get('img', 0) >= CHURN_N and 'img' not in st['said']:
            st['said']['img'] = 1
            sig.append(f"{st['img']} images in chat")
        if len(prompt) >= 12:  # short "ok"/"yes" replies are not repeated instructions
            h = _h(prompt)
            st['prompts'][h] = st['prompts'].get(h, 0) + 1
            if st['prompts'][h] >= CHURN_N and 'p' + h not in st['said']:
                st['said']['p' + h] = 1
                sig.append(f"same instruction {st['prompts'][h]}x")
        last = st.get('used')
        if (last is not None and used - last >= GROW_FAST and st.get('edit_chars', 0) < EDIT_SMALL
                and 'grow' not in st['said']):
            st['said']['grow'] = 1
            sig.append(f'+{(used - last) // 1000}k tokens since last prompt, edits small')
        st['used'], st['edit_chars'] = used, 0
        st['n_prompts'] = st.get('n_prompts', 0) + 1
        gap = time.time() - st['t'] if st.get('t') else 0
        st['t'] = time.time()
        st.setdefault('off0', _packs_off())  # skill packs parked at this chat's first prompt
        idle = idle_advice(data, used, gap)  # t is reset here, so each idle gap speaks once
        w = set(re.findall(r'[a-z0-9_./-]{4,}', prompt))
        old = set(st.get('words', []))
        ov = len(w & old) / len(w) if w and old else 1.0  # share of this prompt's words already used in this chat
        st['words'] = list(old | w)[-400:]
        from tzlib import cfg
        tasks = st.get('tasks', 0)  # task starts so far: first prompt + long prompts that share few words with the chat
        if not old or (len(prompt) >= 12 and ov * 100 < cfg('fresh_overlap')):
            st['tasks'] = tasks + 1
        return sig, stay_or_fresh(used, _base(data), st.get('steps', 0), tasks + 1, gap, len(prompt), ov), idle
    sig, fresh, idle = _churn_rw(data.get('session_id', 'x'), judge)
    out = [idle] if idle else []
    stall = stall_advice(data)
    if stall:
        out.append(stall)
    if sig:
        out.append(f"TOKEN ZOMBIE churn ({'; '.join(sig)}; chat {used // 1000}k): advice only, do not stop mid-task. "
                   'At the next safe point write a checkpoint (`tz state`) and offer the owner a fresh chat before 100k.')
    if fresh:
        out.append(fresh)
    return '\n'.join(out)


PACK = 2000  # tokens: task pack + STATE.md a fresh chat starts from (tz next pack caps it near 2k)


def _base(data):
    """Startup size of this chat [measured, cached by tz-guard]; a fresh chat pays it again. None if unknown."""
    from tzopt import STATE
    try:
        return int(open(os.path.join(STATE, f"base-{data.get('session_id', 'x')}")).read())
    except (OSError, ValueError):
        return None


def stay_or_fresh(used, base, steps, prompts, gap, plen, overlap=0.0):
    """Context-dependent, no fixed size: cost of staying vs a fresh chat for the NEXT task, in input-token equivalents.
    stay  = history re-sent every step at cache-read 0.1x (or re-written at 1.25x once if the cache expired while idle).
    fresh = startup written once at 1.25x + the task pack. Steps per task = this chat's own steps / prompts.
    overlap = share of the prompt's words already seen in this chat [measured]: high => likely a follow-up => stay.
    Returns one line when fresh is cheaper, else ''. Only the model knows if the prompt is a new task, so it decides."""
    from tzlib import cfg
    if (plen < 12 or prompts < 2 or used < PACK * 5 or used >= cfg('limit')
            or overlap * 100 >= cfg('fresh_overlap')):  # past limit the guard's own new-task line speaks  # "ok"/"yes" continue the task; first prompt has no history
        return ''
    b, bb = (base, 'measured') if base else (20000, 'est')
    n = max(1, round(steps / max(1, prompts - 1)))  # prompts = task starts incl. this one: steps per earlier task
    expired = gap > cfg('cache_ttl')
    stay = n * CR * used + (CW * used if expired else 0)
    fresh = CW * (b + PACK) + n * CR * PACK
    compact = CR * used + CW * (b + SUMMARY) + n * CR * SUMMARY  # summary call reads the cached history once
    if stay <= fresh:
        return ''
    why = f"history {used // 1000}k x ~{n} steps/task, {int(overlap * 100)}% word overlap" + (f", cache expired after {int(gap // 60)} min idle" if expired else '')
    return (f"TOKEN ZOMBIE stay-or-fresh [est]: if this prompt is a NEW task, a fresh session is cheaper "
            f"(~{int(stay) // 1000}k vs ~{int(fresh) // 1000}k input-eq, /compact ~{int(compact) // 1000}k; {why}; startup {b // 1000}k [{bb}]). "
            "New task: save `tz handoff` + `tz state` first, then start it fresh (mcp__ccd_session__start_session, brief = task handoff + handoffs/STATE.md only). "
            "Same task or a small fix: stay here.")


# Session Economics [EST, from MEASURED usage]: continue / compact / fresh over the next N user turns; API-equivalent $ only.
import tzprice
PRICE = tzprice.PRICES  # USD per Mtok in/out, list price [EST]; single table in tzprice.py (alias)
SUMMARY = 3000   # tokens: compaction summary a compacted chat restarts from (output once, then history)
TURNS = (5, 10, 20)


_fam = tzprice.family  # alias
CR, CW, CW1 = tzprice.CACHE['read'], tzprice.CACHE['write_5m'], tzprice.CACHE['write_1h']  # cache multipliers (single table)


def _w1h(u):
    """Tokens of this reply's cache writes made with the 1 h TTL (priced 2x input, not 1.25x) [measured, 0 if the field is absent]."""
    cc = u.get('cache_creation')
    return (cc.get('ephemeral_1h_input_tokens') or 0) if isinstance(cc, dict) else 0


def calls(path):
    """[(ts, input, cache_read, cache_write, output, model)] per API reply, deduped by message id [measured]."""
    from tzusage import _ts
    out, seen = [], set()
    for l in _lines(path or ''):
        if '"usage"' not in l:
            continue
        try:
            d = json.loads(l)
        except ValueError:
            continue
        m = d.get('message') or {}
        u = m.get('usage')
        if not isinstance(u, dict) or (m.get('id') and m.get('id') in seen):
            continue
        seen.add(m.get('id'))
        out.append((_ts(d.get('timestamp')) or 0, *(u.get(k) or 0 for k in ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens', 'output_tokens')), m.get('model') or '', _w1h(u)))
    return out


def ieq(c):
    """Input-equivalent tokens of one reply: input 1x, cache read 0.1x, cache write 1.25x (2x for the 1 h TTL part, c[6])."""
    return c[1] + CR * c[2] + CW * c[3] + ((CW1 - CW) * c[6] if len(c) > 6 else 0)


def measure(path):
    """This chat's own numbers [measured]: history, startup, steps/turn, growth/step, cache hit, output/step, model. None if < 2 replies."""
    cs = calls(path)
    if len(cs) < 2:
        return None
    ctx = [c[1] + c[2] + c[3] for c in cs]
    tot = sum(ctx) or 1
    return dict(used=ctx[-1], base=ctx[0], steps=len(cs) / max(1, len(_user_texts(path))), grow=max(0, (ctx[-1] - ctx[0]) / (len(cs) - 1)),
                hit=sum(c[2] for c in cs) / tot, out=sum(c[4] for c in cs) / len(cs), model=next((c[5] for c in reversed(cs) if c[5]), ''),
                t=cs[-1][0], n=len(cs))


def econ(m, gap=0, turns=TURNS):
    """{N: {continue|compact|fresh: (input-eq tokens, $)}} for the next N user turns. Every call re-sends the history:
    the cached share (measured hit rate) at 0.1x, the rest written at 1.25x; a cold start writes its whole start once."""
    from tzlib import cfg
    pin, pout = PRICE[_fam(m['model'])]
    r = m['hit'] * CR + (1 - m['hit']) * CW

    def run(h0, k, cold):
        return (k * h0 + m['grow'] * k * (k - 1) / 2) * r + (h0 * (CW - r) if cold else 0)
    res = {}
    for n in turns:
        k = max(1, round(n * m['steps']))
        o = k * m['out']
        tok = {'continue': run(m['used'], k, gap > cfg('cache_ttl')),
               'compact': m['used'] * r + run(m['base'] + SUMMARY, k, True),
               'fresh': run(m['base'] + PACK, k, True)}
        res[n] = {x: (int(v), (v * pin + (o + (SUMMARY if x == 'compact' else 0)) * pout) / 1e6) for x, v in tok.items()}
        res[n]['calls'] = k
    return res


def next_call(m, gap=0):
    """Cost of ONE more call now [EST]: the whole history is re-read at 0.1x while the cache is warm, re-written at 1.25x once it expired.
    Returns (state, input-eq tokens, $ incl. one average reply)."""
    from tzlib import cfg
    pin, pout = PRICE[_fam(m['model'])]
    cold = gap > cfg('cache_ttl')
    tok = m['used'] * (CW if cold else CR)
    return ('cold' if cold else 'warm'), int(tok), (tok * pin + m['out'] * pout) / 1e6


def best(e, n=10):
    return min(('continue', 'compact', 'fresh'), key=lambda x: e[n][x][1])


def econ_lines(path, now=None):
    """`tz stats` / `tz route` block; also keeps econ.json (panel + projected-vs-actual). [] if the chat is too short."""
    m = measure(path)
    if not m:
        return []
    now = now or time.time()
    e = econ(m, now - m['t'])
    L = [f"SESSION ECONOMICS [EST from measured usage; $ = API-equivalent list price, {_fam(m['model'])}; plan quota is separate]",
         f"  measured: history {m['used'] // 1000}k, startup {m['base'] // 1000}k, {m['steps']:.1f} steps/turn, +{m['grow'] / 1000:.1f}k/step, "
         f"cache hit {m['hit'] * 100:.0f}%, {m['out']:.0f} out/step"]
    st, nt, nd = next_call(m, now - m['t'])
    L.append(f"  next call ({st} cache): {nt // 1000}k input-eq, ${nd:.3f} (one reply of history {m['used'] // 1000}k)")
    for n in TURNS:
        L.append(f"  next {n:>2} turns: " + ' | '.join(f"{x} {e[n][x][0] // 1000}k ${e[n][x][1]:.2f}" for x in ('continue', 'compact', 'fresh'))
                 + f" -> {best(e, n)}")
    L += econ_track(path, m, e, now)
    return L


def econ_track(path, m, e, now):
    """econ.json: one projection per chat (kept until 10 turns of actual replies exist), latest numbers for the panel.
    Actual after a switch: a later chat in the same project = fresh; same chat with context below half = compact; else continue."""
    from tzopt import STATE, _load
    p = os.path.join(STATE, 'econ.json')
    st = _load(p, {})
    st = st if isinstance(st, dict) else {}
    pj = st.get('proj') if isinstance(st.get('proj'), dict) else {}
    proj, L = os.path.dirname(path), []
    cs = calls(path)
    for tp, rec in list(pj.items()):
        if not isinstance(rec, dict) or os.path.dirname(tp) != proj:
            continue
        if tp == path:
            after = [c for c in cs if c[0] > rec['ts']]
            kind = 'compact' if any(c[1] + c[2] + c[3] < rec['used'] / 2 for c in after) else 'continue'
        elif cs and cs[0][0] >= rec['ts']:
            after, kind = cs, 'fresh'
        else:
            continue
        k = rec['calls']
        if not after:
            continue
        act = sum(ieq(c) for c in after[:k])
        pr = rec['tok'][kind] * min(1, len(after) / k)  # projection scaled to the replies seen so far
        L.append(f"  projected vs actual ({kind}, {min(len(after), k)}/{k} calls): ~{int(pr) // 1000}k vs {int(act) // 1000}k input-eq "
                 f"[{'measured' if len(after) >= k else 'partial'}]")
        if len(after) >= k:
            pj.pop(tp)
    if path not in pj:
        pj[path] = {'ts': m['t'], 'used': m['used'], 'calls': e[10]['calls'], 'tok': {x: e[10][x][0] for x in ('continue', 'compact', 'fresh')}}
    pj = dict(sorted(pj.items(), key=lambda kv: kv[1]['ts'])[-20:])
    st = {'proj': pj, 'now': {'ts': int(now), 'turns': 10, 'model': _fam(m['model']), 'best': best(e),
                             **{x: round(e[10][x][1], 4) for x in ('continue', 'compact', 'fresh')}, 'basis': 'EST API-equivalent'}}
    try:
        os.makedirs(STATE, exist_ok=True)
        open(p + '.tmp', 'w').write(json.dumps(st))
        os.replace(p + '.tmp', p)
    except OSError:
        pass
    return L


def compact_line(cwd):
    """The exact /compact line, built from the saved handoff (objective, done, next, decisions). '' when no handoff exists."""
    try:
        import tzintegrity
        st = tzintegrity._load(cwd)
    except Exception:
        return ''
    if not st:
        return ''
    cut = lambda x, n: ' '.join(str(x).split())[:n]
    bits = []
    if st.get('objective'):
        bits.append('task: ' + cut(st['objective'], 120))
    if st.get('done'):
        bits.append('done: ' + '; '.join(cut(x, 60) for x in st['done'][-3:]))
    if st.get('next'):
        bits.append('next: ' + cut(st['next'], 120))
    if st.get('decisions'):
        bits.append('decisions: ' + '; '.join(cut(x, 60) for x in st['decisions'][-3:]))
    if not bits:
        return ''
    return '/compact keep ' + ' | '.join(bits) + ' | drop file dumps, logs, old reads'


def compact_hint(data, used):
    """Stop: context past 70% of the window (the handoff is already checkpointed there) or past the limit -> give the exact /compact line,
    once per 25k step. Advice only. '' otherwise."""
    from tzlib import cfg
    if used < min(cfg('limit'), int(0.7 * cfg('ctx_window'))):
        return ''
    step = used // 25000

    def chk(st):
        if st.get('compact_step', -1) >= step:
            return False
        st['compact_step'] = step
        return True
    if not _churn_rw(data.get('session_id', 'x'), chk):
        return ''
    line = compact_line(data.get('cwd') or os.getcwd())
    return (f'TOKEN ZOMBIE: chat is {used // 1000}k tokens. If this task is done, run /compact now '
            '(the note keeps only done, left and next), then send the next task.'
            + (f'\nPaste this: {line}' if line else '\nNo handoff yet: run tz handoff save --next "<next step>" first, then /compact.'))


# Loop detection, claim board, idle-cache and cleanup advice (advice only, never blocks).
LOOP_N, LOOP_WIN = 3, 10   # same tool+input N times within the last WIN calls
CLAIM_TTL = 7200           # seconds a file claim by another chat stays a warning
STALL_S = 600              # subagent transcript silent this long while mid-work = stalled
IDLE_MIN_USED = 20000


def _claims_rw(fn):
    from tzopt import STATE, _load
    p = os.path.join(STATE, 'claims.json')
    c = _load(p, {})
    c = c if isinstance(c, dict) else {}
    out = fn(c)
    os.makedirs(STATE, exist_ok=True)
    open(p + '.tmp', 'w').write(json.dumps(c))
    os.replace(p + '.tmp', p)
    return out


def tool_advice(data):
    """PostToolUse (any tool): loop line (same tool+input N times in the last WIN calls, once per hash) and claim-board
    line (another chat edited this file within CLAIM_TTL, once per file). '' when nothing to say."""
    sid, tool, ti = data.get('session_id', 'x'), data.get('tool_name') or '', data.get('tool_input') or {}
    h = _h(tool + json.dumps(ti, sort_keys=True, default=str))
    out = []

    def loop(st):
        r = (st.get('recent', []) + [h])[-LOOP_WIN:]
        st['recent'] = r
        if r.count(h) >= LOOP_N and 'L' + h not in st['said']:
            st['said']['L' + h] = 1
            return f'TOKEN ZOMBIE loop: {tool} same input {r.count(h)}x: stop and change approach'
        return ''
    m = _churn_rw(sid, loop)
    if m:
        out.append(m)
    f = ti.get('file_path') or ti.get('notebook_path') or ''
    if tool in ('Edit', 'Write', 'MultiEdit', 'NotebookEdit') and f:
        now = time.time()

        def claim(c):
            o = c.get(f)
            c[f] = {'sid': sid, 't': now, 'pid': os.getppid(), 'exp': now + CLAIM_TTL}
            for k in [k for k, v in c.items() if now - (v.get('t') or 0) > CLAIM_TTL]:
                del c[k]
            return o if o and o.get('sid') != sid and now - o.get('t', 0) <= CLAIM_TTL else None
        o = _claims_rw(claim)
        if o:
            def warn(st):
                if f in st.setdefault('claim_said', {}):
                    return False
                st['claim_said'][f] = 1
                return True
            if _churn_rw(sid, warn):
                out.append(f"TOKEN ZOMBIE: another chat {str(o['sid'])[:8]} edited {os.path.basename(f)} "
                           f"{int((now - o['t']) // 60)} min ago: check it before overwriting")
    return '\n'.join(out)


def _alive(pid):
    from tzlive import pid_alive
    return pid_alive(pid)


def file_guard(data):
    """PreToolUse Edit/Write/MultiEdit/NotebookEdit: another LIVE chat claimed this file (< CLAIM_TTL, pid alive,
    claim not expired) -> one warning line BEFORE the write, once per file. Advice only. '' when nothing to say."""
    sid, ti = data.get('session_id', 'x'), data.get('tool_input') or {}
    f = ti.get('file_path') or ti.get('notebook_path') or ''
    if not f or (data.get('tool_name') or '') not in ('Edit', 'Write', 'MultiEdit', 'NotebookEdit'):
        return ''
    now = time.time()
    o = _claims_rw(lambda c: c.get(f))
    if (not o or o.get('sid') == sid or now - o.get('t', 0) > CLAIM_TTL or now > o.get('exp', now + 1)
            or (o.get('pid') and not _alive(o['pid']))):
        return ''

    def warn(st):
        if f in st.setdefault('claim_said', {}):
            return False
        st['claim_said'][f] = 1
        return True
    if not _churn_rw(sid, warn):
        return ''
    return (f"TOKEN ZOMBIE: another live chat {str(o['sid'])[:8]} edited {os.path.basename(f)} "
            f"{int((now - o['t']) // 60)} min ago: check it before this write")


FAIL_N = 3   # same tool (or same Bash command) failing N times in a row -> stop retrying, ask the owner


def _failed(data):
    """True when the tool result reports an error (PostToolUseFailure, is_error, error key, Bash non-zero exit)."""
    if data.get('hook_event_name') == 'PostToolUseFailure' or data.get('error'):
        return True
    r = data.get('tool_response')
    if isinstance(r, dict):
        if r.get('is_error') or r.get('error') or r.get('success') is False:
            return True
        rc = r.get('exitCode', r.get('exit_code', r.get('returncode')))
        return isinstance(rc, int) and rc != 0
    return False


def breaker(data):
    """Circuit breaker, advice only: same tool failing FAIL_N times in a row, or the same failing Bash command
    FAIL_N times in a row -> one line per fingerprint per chat. A success of that tool resets its count."""
    sid, tool, ti = data.get('session_id', 'x'), data.get('tool_name') or '', data.get('tool_input') or {}
    bad = _failed(data)
    keys = [('T', tool, tool)]
    if tool == 'Bash' and ti.get('command'):
        keys.insert(0, ('B', 'Bash command', _h(str(ti['command']))))

    def step(st):
        fl, out = st.setdefault('fails', {}), []
        for k, label, fp in keys:
            key = k + fp
            if not bad:
                fl.pop(key, None)
                continue
            fl[key] = fl.get(key, 0) + 1
            if fl[key] >= FAIL_N and 'F' + key not in st['said']:
                st['said']['F' + key] = 1
                out.append(f'TOKEN ZOMBIE circuit breaker: {label if k == "B" else tool} failed {fl[key]}x in a row: '
                           'stop retrying, tell the owner what fails and ask how to proceed')
        return out
    r = _churn_rw(sid, step)
    return r[0] if r else ''


def release_claims(sid):
    """SessionEnd: drop this chat's claims."""
    def rel(c):
        for k in [k for k, v in c.items() if v.get('sid') == sid]:
            del c[k]
    _claims_rw(rel)


def idle_advice(data, used, gap):
    """UserPromptSubmit: idle past cache_ttl with a big history -> the prompt cache expired; once per gap. gap = seconds idle."""
    from tzlib import cfg
    if used <= IDLE_MIN_USED or gap <= cfg('cache_ttl'):
        return ''
    return (f'TOKEN ZOMBIE: idle {int(gap // 60)} min, the prompt cache likely expired: this message re-writes '
            f'~{used // 1000}k history at 1.25x (~{int(used * CW) // 1000}k input-eq)')


def stall_advice(data):
    """UserPromptSubmit: a subagent transcript of this chat silent > STALL_S while mid-work (last line not a final answer)."""
    sid, now, out = data.get('session_id', 'x'), time.time(), []
    for p in glob.glob(os.path.expanduser(f'~/.claude/projects/*/{sid}/subagents/*.jsonl')):
        try:
            age = now - os.path.getmtime(p)
            if not STALL_S < age < 7200:
                continue
            L = _lines(p)
            last = json.loads(L[-1]) if L else {}
        except Exception:
            continue
        if (last.get('message') or {}).get('stop_reason') == 'end_turn' or any('"SubagentHandback"' in l for l in L[-4:]):
            continue  # finished normally (final answer, or the hand-back report call and its result)
        out.append(f'{os.path.basename(p)[:-6]} silent {int(age // 60)} min')
    return ('TOKEN ZOMBIE: subagent may be stalled (' + '; '.join(out[:3]) + '): check it or stop it') if out else ''


def _packs_off():
    d = os.path.expanduser('~/.claude/skills-off')
    try:
        return sorted(p for p in os.listdir(d) if os.path.isdir(f'{d}/{p}') and os.listdir(f'{d}/{p}'))
    except OSError:
        return []


def pack_cleanup(data):
    """Stop: packs that were off at this chat's first prompt and are on now; once per distinct set."""
    def chk(st):
        off0 = st.get('off0')
        if off0 is None:
            return ''
        on = sorted(set(off0) - set(_packs_off()))
        if not on or st.get('pack_said') == on:
            return ''
        st['pack_said'] = on
        return 'TOKEN ZOMBIE: skill packs still on: ' + ', '.join(on) + ' (' + '; '.join(f'~/.claude/skillpack off {p}' for p in on) + ')'
    return _churn_rw(data.get('session_id', 'x'), chk)
