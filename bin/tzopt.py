#!/usr/bin/env python3
# Token-zombie optimization: duplicate-read + repeated-output detection (live cache and log analysis), output filter,
# task mode + model advice, savings ledger. Advice only: a full read is NEVER blocked here.
# Tokens are est = chars/4. measured = counted from real bytes/log; est = a guess about what the model would have used.
import hashlib, json, os, re, sys, time
import tzprice
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STATE = os.path.expanduser('~/.claude/token-zombie')
ET = lambda chars: chars // 4  # est tokens


def _load(p, d):
    try:
        return json.load(open(p))
    except Exception:
        return d


def _save(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(o, open(p + '.tmp', 'w'))
    os.replace(p + '.tmp', p)


def ledger(kind, chars, basis, session='x', src=''):
    """Append savings (+, or - to reverse one) or overhead event. basis: measured|est. Each entry keeps time, source and calc."""
    p = os.path.join(STATE, 'ledger.json')
    L = _load(p, [])
    L.append({'t': int(time.time()), 'kind': kind, 'tok': ET(chars) if chars >= 0 else -ET(-chars), 'basis': basis, 's': session,
              'src': src[:120], 'calc': f'{chars} chars / 4'})
    _save(p, L[-2000:])
    if chars > 0 and basis == 'measured' and not kind.startswith('overhead'):  # a real saving: mascot cheers
        try:
            import tzbus
            tzbus.mood('save')
        except Exception:
            pass


def rtk_delta(session='x'):
    """After a Bash call: log rtk's newly measured saving (its total_saved grew) to the ledger. First call only sets the baseline."""
    import subprocess
    try:
        j = json.loads(subprocess.run(['rtk', 'gain', '-f', 'json'], capture_output=True, text=True, timeout=2).stdout)
        now = int(j['summary']['total_saved'])
    except Exception:
        return 0
    p = os.path.join(STATE, 'rtk-last.json')
    last = _load(p, {}).get('saved')
    _save(p, {'saved': now})
    d = now - last if isinstance(last, int) else 0
    if d > 0:  # ledger() takes chars; x4 keeps the measured token count exact
        ledger('rtk', d * 4, 'measured', session, 'rtk gain total_saved delta')
    return d


def read_advice(session, path, limit=None, offset=None):
    """Live Read check (path + mtime + content hash). Returns advice text or ''. Invalidates cache when file changed."""
    try:
        st = os.stat(path)
    except OSError:
        return ''
    p = os.path.join(STATE, f'reads-{session}.json')
    c = _load(p, {})
    key = f'{path}|{limit or ""}|{offset or ""}'
    h = hashlib.sha1(open(path, 'rb').read(2_000_000)).hexdigest()[:12]
    old = c.get(key)
    c[key] = {'mt': st.st_mtime, 'h': h, 'n': (old['n'] + 1 if old else 1) if (not old or old['h'] == h) else 1}
    if old and old['h'] == h:  # keep read-guard flags (trimmed / already denied once) while the file is unchanged
        c[key].update({k: old[k] for k in ('trim', 'den') if k in old})
    _save(p, c)
    if old and old['h'] == h:
        ledger('dup-read-flagged', st.st_size, 'est', session, 'advice on unchanged re-read: ' + path)
        return (f'TOKEN ZOMBIE: {os.path.basename(path)} was already read this session and is unchanged (hash {h}). '
                'Use what you have; re-read only the lines you need (grep -n, Read offset+limit).')
    return ''


def _text(c):
    if isinstance(c, list):
        c = '\n'.join(x.get('text', '') for x in c if isinstance(x, dict))
    return c if isinstance(c, str) else ''


def analyze(path):
    """Scan a chat log: duplicate Reads (same path, no Edit/Write between), repeated Bash commands with identical output.
    Returns dict; wasted tokens are est from the repeated result sizes."""
    r = dict(reads=0, dup_reads=[], dup_cmds=[], wasted_chars=0, big_full_reads=[], dup_research=[], dup_explore=[], big_outputs=[])
    if not path or not os.path.isfile(path):
        return r
    uses, results, ids = [], {}, set()
    with open(path, 'rb') as f:
        for raw in f:
            line = raw.decode('utf-8', 'ignore')
            if '"tool_use"' not in line and '"tool_result"' not in line:
                continue
            try:
                c = json.loads(line).get('message', {}).get('content')
            except Exception:
                continue
            for b in c if isinstance(c, list) else []:
                if isinstance(b, dict) and b.get('type') == 'tool_use':
                    if b.get('id') and b['id'] in ids:
                        continue  # the host can log one call on several lines; count it once
                    ids.add(b.get('id'))
                    uses.append(b)
                elif isinstance(b, dict) and b.get('type') == 'tool_result':
                    results[b.get('tool_use_id')] = len(_text(b.get('content')))
    seen_read, seen_cmd, seen_rs, seen_ex = {}, {}, set(), set()
    for b in uses:
        i, n = b.get('input') or {}, b.get('name')
        sz0 = results.get(b.get('id'), 0)
        if sz0 > 30000 and n != 'Read':
            r['big_outputs'].append((n, sz0))
        if n in ('WebSearch', 'WebFetch', 'Agent', 'Task'):
            k = (n, str(i.get('query') or i.get('url') or i.get('prompt') or i.get('description') or '').strip().lower()[:200])
            if k[1] and k in seen_rs:
                r['dup_research'].append((n, k[1][:50], sz0))
                r['wasted_chars'] += sz0
            seen_rs.add(k)
        elif n in ('Glob', 'Grep') or (n == 'Bash' and re.match(r'\s*(ls|find|tree)\b', str(i.get('command', '')))):
            k = (n, json.dumps(i, sort_keys=True))
            if k in seen_ex:
                r['dup_explore'].append((n, sz0))
                r['wasted_chars'] += sz0
            seen_ex.add(k)
        if n in ('Edit', 'Write', 'NotebookEdit'):
            seen_read.pop(i.get('file_path'), None)
        elif n == 'Read' and i.get('file_path'):
            r['reads'] += 1
            sz = results.get(b.get('id'), 0)
            if not (i.get('limit') or i.get('offset')) and sz > 40000:
                r['big_full_reads'].append((i['file_path'], sz))
            if i['file_path'] in seen_read and not (i.get('limit') or i.get('offset')):
                r['dup_reads'].append((i['file_path'], sz))
                r['wasted_chars'] += sz
            seen_read[i['file_path']] = 1
        elif n == 'Bash' and i.get('command'):
            k = i['command'].strip()
            sz = results.get(b.get('id'), 0)
            if k in seen_cmd and seen_cmd[k] == sz and sz > 200 and not k.startswith(('git ', 'ls', 'pwd')):
                r['dup_cmds'].append((k[:60], sz))
                r['wasted_chars'] += sz
            seen_cmd[k] = sz
    return r


def filter_output(text, max_lines=40):
    """Keep errors/warnings/summary, collapse repeated lines, cap length. Returns (filtered, before_chars, after_chars)."""
    lines = text.splitlines()
    out, prev, rep = [], None, 0
    for l in lines:
        if l == prev:
            rep += 1
            continue
        if rep:
            out.append(f'  (previous line repeated {rep}x)')
        prev, rep = l, 0
        out.append(l)
    if rep:
        out.append(f'  (previous line repeated {rep}x)')
    if len(out) > max_lines:
        key = [l for l in out if re.search(r'error|fail|traceback|exception|warn|panic|fatal', l, re.I)][:max_lines // 2]
        head, tail = out[:5], out[-(max_lines - 5 - len(key)):]
        out = head + [f'... {len(lines) - len(head) - len(tail)} lines omitted (full output: save to a file and grep it) ...'] + key + tail
    res = '\n'.join(out)
    return res, len(text), len(res)


MODES = [('AUDIT', r'\baudit|security review|vulnerab|review the (repo|codebase)'),
         ('RESEARCH', r'research|compare|investigate|find out|survey|look up|literature'),
         ('ENGINEERING', r'architect|design|refactor|migrat|implement|build|debug|race condition|performance'),
         ('CREATIVE', r'write (a )?(story|script|post|copy)|brainstorm|logo|thumbnail|caption|hook'),
         ('QUICK', r'\btypo\b|rename|one line|what is|which|count|validate json|list |show me')]
MODEL = {'QUICK': 'script or cheapest model (Haiku)', 'STANDARD': 'Sonnet', 'ENGINEERING': 'Sonnet; strong model only for architecture/hard debugging',
         'RESEARCH': 'Haiku subagents to gather, Sonnet to synthesise', 'AUDIT': 'strong model review + deterministic scans (tz security)',
         'CREATIVE': 'Sonnet'}


def classify(prompt):
    """(mode, model advice, subagents useful?). Keyword rules: a heuristic, not a promise. User instructions override."""
    p = prompt.lower()
    mode = next((m for m, rx in MODES if re.search(rx, p)), 'STANDARD')
    return mode, MODEL[mode], mode in ('RESEARCH', 'AUDIT') or len(p) > 600


DENY_MIN = 2000  # chars: below this a re-read costs less than the risk of a wrong deny


def read_decision(data):
    """PreToolUse Read -> hookSpecificOutput or None. Config read_guard: 'advice' (default) | 'deny' | 'off'.
    deny: same file+range, unchanged hash, not trimmed, main agent only, >= DENY_MIN chars -> denied ONCE; an identical
    retry is allowed (Claude decided it needs it). tzlive deletes reads-<session>.json on PreCompact, so nothing is denied
    after the summary dropped the old result."""
    try:
        mode = _load(os.path.join(STATE, 'config.json'), {}).get('read_guard', 'advice')
        ti, s = data.get('tool_input') or {}, data.get('session_id', 'x')
        f = ti.get('file_path') or ''
        if mode == 'off' or not os.path.isfile(f):
            return None
        p = os.path.join(STATE, f'reads-{s}.json')
        key = f'{f}|{ti.get("limit") or ""}|{ti.get("offset") or ""}'
        prev = _load(p, {}).get(key, {})
        adv = read_advice(s, f, ti.get('limit'), ti.get('offset'))
        if not adv:
            return None
        if mode == 'deny' and prev.get('den') == 1:  # identical retry: the denied read happened after all, take the saving back
            c = _load(p, {})
            c.setdefault(key, {})['den'] = 2
            _save(p, c)
            ledger('dup-read-denied', -os.path.getsize(f), 'measured', s, 'retry after deny: ' + f)
        if (mode == 'deny' and not data.get('agent_id') and not prev.get('trim') and not prev.get('den')
                and os.path.getsize(f) >= DENY_MIN):
            c = _load(p, {})
            c.setdefault(key, {})['den'] = 1
            _save(p, c)
            ledger('dup-read-denied', os.path.getsize(f), 'measured', s, 'Read denied (unchanged re-read): ' + f)
            sk = ''
            try:
                from tzlib import feature
                if feature('dup_skeleton'):
                    from tzcompress import outline
                    o = outline(f)
                    sk = f' Outline (read only the part you need with offset+limit):\n{o}' if o else ''
            except Exception:
                sk = ''
            return {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', 'permissionDecisionReason':
                    adv + ' Denied once to save tokens; repeat the same Read if you truly need it again.' + sk}
        return {'hookEventName': 'PreToolUse', 'additionalContext': adv}
    except Exception:
        return None


def rtk_gain():
    """rtk's own MEASURED Bash savings (`rtk gain -f json`). Kept apart from TZ numbers: never added to TZ totals."""
    import shutil, subprocess
    if not shutil.which('rtk'):
        return None
    try:
        out = subprocess.run(['rtk', 'gain', '-f', 'json'], capture_output=True, text=True, timeout=5).stdout
        return json.loads(out[out.index('{'):]).get('summary')
    except Exception:
        return None


def stats():
    L = _load(os.path.join(STATE, 'ledger.json'), [])
    s = {'measured': 0, 'est': 0, 'overhead': 0, 'unknown': 0}
    s['kinds'] = {}
    for e in L:
        k = s['kinds'].setdefault(f"{e['kind']} [{e.get('basis', 'unknown')}]", [0, 0])
        k[0] += e.get('tok', 0); k[1] += 1
        if e['kind'].startswith('overhead'):
            s['overhead'] += e['tok']
        elif e.get('basis') in ('measured', 'est'):
            s[e['basis']] += e['tok']
        else:  # size not known: counted as an event, never as tokens
            s['unknown'] += 1
    s['net_measured'] = s['measured'] - s['overhead']
    s['net_est'] = s['measured'] + s['est'] - s['overhead']
    return s


def _cost(model, u):
    """EST API-equivalent list price: (input-eq tokens, USD). cache_read 0.1x, cache_write 1.25x input price [tzcont.PRICE]."""
    import tzcont
    import tzprice
    pin, pout = tzprice.price(model)
    i, cr, cw, o = (u.get(k) or 0 for k in ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens', 'output_tokens'))
    ie = i + tzprice.CACHE['read'] * cr + tzprice.CACHE['write_5m'] * cw
    return ie, (ie * pin + o * pout) / 1e6


def day(now=None, hours=24, root=None):
    """Rolling window: real usage rows from chat logs (main + subagents, deduped by message id) and ledger entries."""
    import glob
    from tzusage import _ts
    now = now or time.time(); t0 = now - hours * 3600
    root = root or os.path.expanduser('~/.claude/projects')
    use = {}  # (main|agent, model) -> [calls, input+cache, output, est $]
    ag = {}   # subagent transcript id -> [calls, input-eq tok, output, est $, model]
    for f in glob.glob(os.path.join(root, '**', '*.jsonl'), recursive=True):
        if os.path.getmtime(f) < t0:
            continue
        who, seen = ('agent' if os.sep + 'subagents' + os.sep in f else 'main'), set()
        for raw in open(f, 'rb'):
            if b'"usage"' not in raw:
                continue
            try:
                d = json.loads(raw)
            except Exception:
                continue
            m = d.get('message') or {}; u = m.get('usage'); ts = _ts(d.get('timestamp'))
            if not isinstance(u, dict) or not ts or ts < t0 or m.get('id') in seen:
                continue
            seen.add(m.get('id'))
            r = use.setdefault((who, m.get('model') or '?'), [0, 0, 0, 0.0])
            ie, usd = _cost(m.get('model'), u); r[3] += usd
            if who == 'agent':
                a = ag.setdefault(os.path.basename(f)[:-6], [0, 0, 0, 0.0, m.get('model') or '?'])
                a[0] += 1; a[1] += ie; a[2] += u.get('output_tokens') or 0; a[3] += usd
            r[0] += 1; r[1] += sum(u.get(k) or 0 for k in ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens')); r[2] += u.get('output_tokens') or 0
    L = [e for e in _load(os.path.join(STATE, 'ledger.json'), []) if isinstance(e, dict) and isinstance(e.get('t'), (int, float)) and e['t'] >= t0]
    led = {'measured': 0, 'est': 0, 'overhead': 0}
    for e in L:
        k = 'overhead' if str(e.get('kind', '')).startswith('overhead') else e.get('basis')
        if k in led:
            led[k] += e.get('tok', 0)
    return {'hours': hours, 'use': use, 'agents': ag, 'ledger': led, 'n': len(L)}


def keep_day(d, now=None):
    """History: one snapshot per local date in history.json (newest overwrites the same date)."""
    p = os.path.join(STATE, 'history.json'); h = _load(p, {})
    h[time.strftime('%Y-%m-%d', time.localtime(now or time.time()))] = {
        'used': sum(v[1] + v[2] for v in d['use'].values()), 'calls': sum(v[0] for v in d['use'].values()), **d['ledger']}
    try:
        os.makedirs(STATE, exist_ok=True); json.dump(h, open(p, 'w'))
    except Exception:
        pass
    return h


def _work_dir(path):
    """Project a chat worked in [measured]: its most frequent logged cwd other than home (a chat opened in ~ that works in
    ~/proj belongs to ~/proj). Falls back to the log's own project folder."""
    import collections, re
    norm = lambda p: os.path.normcase(os.path.normpath(p))  # Windows: case and slash style differ
    home, n = os.path.expanduser('~'), collections.Counter()
    for raw in open(path, 'rb'):
        m = re.search(rb'"cwd":"([^"]+)"', raw)
        if m:
            d = m.group(1).decode('utf-8', 'ignore').replace('\\\\', '\\')  # raw JSON doubles Windows backslashes
            if norm(d) != norm(home):
                n[d] += 1
    return n.most_common(1)[0][0] if n else os.path.dirname(path)


def fresh_saved(now=None, hours=24, root=None, gap_h=24, big=50000):
    """Counterfactual [EST from MEASURED contexts]: a chat that started within gap_h after a big chat in the same project
    (by the folder it worked in, not the folder it was opened in) re-sent its own context each call, not the old chat's
    last context. All inputs MEASURED from logs; result in input-equivalent tokens:
      saved = n x 0.1 x (old last ctx - new startup ctx)      old history re-sent as cache reads on each of the n calls
            - (new first call's real cost - 0.1 x startup ctx)  the new chat's extra startup write (measured)
    Can be negative (a loss). Each old chat links to at most one new chat. Assumes the same calls with a warm cache."""
    import glob
    from tzusage import totals
    now = now or time.time(); t0 = now - hours * 3600
    root = root or os.path.expanduser('~/.claude/projects')
    by = {}
    for f in glob.glob(os.path.join(root, '*', '*.jsonl')):
        if os.path.getmtime(f) < t0 - gap_h * 3600:
            continue
        t = totals(f)
        t['path'] = f
        if t['t0']:
            by.setdefault(_work_dir(f), []).append(t)
    out, linked = [], set()
    for proj, ch in by.items():
        ch.sort(key=lambda t: t['t0'])
        for i, s in enumerate(ch):
            prev = [p for p in ch[:i] if p['t1'] and p['t1'] <= s['t0'] and s['t0'] - p['t1'] <= gap_h * 3600 and p['last'] >= big
                    and id(p) not in linked]  # an old chat could have been continued by ONE new chat only: no double count
            if not prev:
                continue
            linked.add(id(prev[-1]))
            old = prev[-1]['last']
            import tzcont
            cs = tzcont.calls(s['path'])
            c0 = cs[0][1] + cs[0][2] + cs[0][3]
            n = len([c for c in cs if c[0] >= t0])
            start = tzcont.ieq(cs[0]) - 0.1 * c0 if cs[0][0] >= t0 else 0  # paid once, only if the start is in the window
            sv = int(tzprice.CACHE['read'] * n * max(0, old - c0) - start)
            if sv:
                out.append((os.path.basename(proj), old, len([1 for ts, _ in s['pts'] if ts >= t0]), sv))
    return out


def fresh_file(fs=None):
    """fresh.json for the toolbar panel: {ts, tok, n, basis}."""
    fs = fresh_saved() if fs is None else fs
    try:
        os.makedirs(STATE, exist_ok=True)
        now = time.time(); mid = time.mktime(time.localtime(now)[:3] + (0, 0, 0) + time.localtime(now)[6:])
        today = fresh_saved(now, (now - mid) / 3600)  # same window as the TOKENS SAVED tile (since local midnight)
        json.dump({'ts': int(now), 'tok': sum(x[3] for x in fs), 'n': len(fs), 'today': sum(x[3] for x in today), 'n_today': len(today),
                   'basis': 'EST counterfactual from measured ctx'},
                  open(os.path.join(STATE, 'fresh.json'), 'w'))
    except Exception:
        pass
    return fs


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='tz optimize|stats|filter|classify')
    ap.add_argument('cmd', choices=['optimize', 'stats', 'filter', 'classify', 'hook'])
    ap.add_argument('arg', nargs='*')
    ap.add_argument('--transcript')
    ap.add_argument('--lines', type=int, default=40)
    a = ap.parse_args(argv)
    if a.cmd == 'optimize':
        from tzusage import find_transcript
        path = a.transcript or find_transcript(os.getcwd())
        r = analyze(path)
        print(f"reads [actual] {r['reads']}; duplicate full reads {len(r['dup_reads'])}; repeated commands w/ same output {len(r['dup_cmds'])}")
        for f, n in r['dup_reads'][:5]:
            print(f'  re-read, no edit between: {f} (~{ET(n)} tok [est])')
        for c, n in r['dup_cmds'][:5]:
            print(f'  same command, same output: `{c}` (~{ET(n)} tok [est])')
        for n_, q, n in r['dup_research'][:5]:
            print(f'  repeated {n_} "{q}" (~{ET(n)} tok [est])')
        if r['dup_explore']:
            print(f"  repeated Glob/Grep/ls exploration: {len(r['dup_explore'])} calls (~{ET(sum(n for _, n in r['dup_explore']))} tok [est])")
        for n_, n in r['big_outputs'][:3]:
            print(f'  oversized {n_} output {n // 1000}k chars: filter it (tz filter)')
        for f, n in r['big_full_reads'][:5]:
            print(f'  big full read: {f} ({n // 1000}k chars): try grep -n + Read offset/limit')
        print(f"avoidable [est] ~{ET(r['wasted_chars'])} tokens (what the repeats cost; avoiding them is advice, not guaranteed)")
        from tzusage import totals
        u = totals(path)
        if u['turns']:
            # every model call re-sends the whole chat; usually the biggest cost in a long chat
            per = (u['inp'] + u['cr'] + u['cw']) // u['turns']
            print(f"model calls [actual] {u['turns']}; context re-sent per call avg ~{per // 1000}k [actual], total {(u['inp'] + u['cr'] + u['cw']) // 1000}k")
            # list-price multipliers relative to fresh input (cache read 0.1x, cache write 1.25x, output 5x): shares, not dollars
            w = dict(input=u['inp'], cache_read=u['cr'] * __import__('tzprice').CACHE['read'], cache_write=u['cw'] * __import__('tzprice').CACHE['write_5m'], output=u['out'] * 5)
            tw = sum(w.values()) or 1
            print('  cost share [est, input-equivalent weights]: ' + ', '.join(f'{k} {v * 100 / tw:.0f}%' for k, v in w.items()))
            print(f"  each tool round trip you avoid (batch independent calls in one message) saves ~{per // 1000}k re-sent [est]")
        if not path:
            print('no chat log found (pass --transcript)')
    elif a.cmd == 'stats':
        s = stats()
        print(f"saved [measured] {s['measured']} tok | saved [est] {s['est']} tok | overhead [measured] {s['overhead']} tok")
        print(f"NET measured-only {s['net_measured']} tok | NET incl. estimates {s['net_est']} tok")
        if s['kinds']:  # each kind kept apart; every entry holds time, source and calc (ledger.json)
            print('by kind: ' + ' | '.join(f'{k} {v[0]} tok n={v[1]}' for k, v in sorted(s['kinds'].items())))
        print(f"unknown-size events {s['unknown']} (not counted) | cache reads are cheap re-sends, never counted as waste or savings")
        print('NET = verified (measured) avoided - TZ overhead. Savings are only counted for events this tool recorded.')
        g = rtk_gain()
        if g:  # separate tool, separate count: Bash output is rtk's, TZ never filters Bash, so nothing is double-counted
            print(f"rtk (Bash, separate tool) [measured by rtk]: saved {g['total_saved']} of {g['total_input']} tok "
                  f"({g['avg_savings_pct']:.1f}%) over {g['total_commands']} commands, avg {g['avg_time_ms']} ms")
        d = day()
        tot = sum(v[1] + v[2] for v in d['use'].values())
        print(f"LAST 24H (rolling) used [measured, chat logs, incl. cache reads] {tot:,} tok in {sum(v[0] for v in d['use'].values())} model calls"
              f" | saved [measured] {d['ledger']['measured']} [est] {d['ledger']['est']} | TZ overhead [measured] {d['ledger']['overhead']}")
        for (who, mod), v in sorted(d['use'].items(), key=lambda x: -x[1][1]):
            print(f"  {who:5} {mod}: {v[0]} calls, {v[1] + v[2]:,} tok ({(v[1] + v[2]) * 100 // max(tot, 1)}%) ~${v[3]:.2f}")
        if d['use']:
            sub = sum(v[1] + v[2] for k, v in d['use'].items() if k[0] == 'agent')
            print(f"  total ~${sum(v[3] for v in d['use'].values()):.2f} [EST API-equivalent list price; plan quota separate]"
                  f" | subagents did {sub * 100 // max(tot, 1)}% of tokens, main {100 - sub * 100 // max(tot, 1)}% [measured]")
        for k, v in sorted(d['agents'].items(), key=lambda x: -x[1][3])[:5]:
            print(f"  top subagent {k}: {v[0]} calls, {int(v[1] + v[2]):,} input-eq+out tok, ~${v[3]:.2f} [EST] {v[4]}")
        try:
            import tzondemand
            ev = tzondemand.events(time.time() - 86400)
            print(f"on-demand events 24h [measured, caps.jsonl]: {len(ev)}" + ''.join(
                f"\n  {time.strftime('%H:%M', time.localtime(e['t']))} {e['act']} {e['cap']} {'ok' if e['ok'] else 'FAIL'}" for e in ev[-10:]))
        except Exception:
            pass
        fs = fresh_saved(); fresh_file(fs)
        if fs:
            n = sum(x[3] for x in fs)
            print(f"fresh-chat saving 24h [EST counterfactual from MEASURED ctx]: {len(fs)} chats started after a big one; "
                  f"~{n:,} input-eq tok = old history re-sent per call (cache reads 0.1x) minus the new chat's startup write; all inputs measured, one new chat per old chat; vs /compact it is less")
            for pr, old, c, sv in sorted(fs, key=lambda x: -x[3])[:3]:
                print(f"  {pr}: old chat {old // 1000}k, new chat {c} calls, ~{sv:,} tok")
        h = keep_day(d)
        from tzusage import find_transcript
        import tzcont
        tp = a.transcript or find_transcript(os.getcwd())
        for l in tzcont.econ_lines(tp):
            print(l)
        cl = tp and tzcont.code_line(os.path.basename(tp)[:-6])
        if cl:
            print(cl)
        print('history (per day, used / saved measured): ' + ' | '.join(f"{k} {v['used'] // 1000}k/{v['measured']}" for k, v in sorted(h.items())[-7:]))
    elif a.cmd == 'filter':
        txt = sys.stdin.read()
        out, b, af = filter_output(txt, a.lines)
        print(out)
        print(f'[tz filter: {b} -> {af} chars measured, ~{ET(b - af)} tok saved est]', file=sys.stderr)
        ledger('filter', max(0, b - af), 'measured', 'x', f'tz filter {b} -> {af} chars')
    elif a.cmd == 'classify':
        m, mod, sub = classify(' '.join(a.arg))
        sub = {'QUICK': 'haiku', 'RESEARCH': 'haiku', 'AUDIT': 'sonnet (+ tz security)', 'CREATIVE': 'sonnet', 'ENGINEERING': 'sonnet', 'STANDARD': 'sonnet'}[m]
        print(f'mode {m} | model: {mod} | subagent model param: {sub} | subagents: {"yes" if sub else "no"} | (heuristic; main-session model is changed by you, not by tz)')
    else:  # hook: PreToolUse Read JSON on stdin -> additionalContext if duplicate
        try:
            d = json.load(sys.stdin)
            ti = d.get('tool_input') or {}
            adv = read_advice(d.get('session_id', 'x'), ti.get('file_path', ''), ti.get('limit'), ti.get('offset'))
            if adv:
                ledger('overhead-hook', len(adv), 'measured', d.get('session_id', 'x'), 'read advice text')
                print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'additionalContext': adv}}))
        except Exception:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
