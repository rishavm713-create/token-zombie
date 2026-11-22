#!/usr/bin/env python3
# Token-zombie usage intelligence. Every number is labelled: [actual] from logs / provider rate_limits,
# [est] computed here. 5h/7d appear ONLY when the provider passes rate_limits; weekly/reset absent => omitted, never invented.
import datetime as dt, glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tzlib import cfg

SPAN = {'five_hour': ('5h', 18000), 'seven_day': ('7d', 604800)}


def totals(path):
    """Sum real usage from a chat log: dict in/out/cache_read/cache_write/last_ctx/turns + first/last timestamps + ctx points."""
    t = dict(inp=0, out=0, cr=0, cw=0, last=0, turns=0, t0=None, t1=None, pts=[], w5=0, w1h=0, think=0)
    seen = set()
    if not path or not os.path.isfile(path):
        return t
    with open(path, 'rb') as f:
        for raw in f:
            line = raw.decode('utf-8', 'ignore')
            if '"usage"' not in line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            m = d.get('message') or {}
            u = m.get('usage')
            if not isinstance(u, dict):
                continue
            key = m.get('id') or d.get('uuid')
            if key and key in seen:  # one API reply can be logged in several lines
                continue
            seen.add(key)
            i, o, cr, cw = (u.get(k) or 0 for k in ('input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens'))
            cc = u.get('cache_creation')  # 5-minute vs 1-hour cache writes [MEASURED when the host logs the split]
            if isinstance(cc, dict):
                t['w5'] += cc.get('ephemeral_5m_input_tokens') or 0; t['w1h'] += cc.get('ephemeral_1h_input_tokens') or 0
            for b in (m.get('content') or []):  # thinking tokens are inside output_tokens; chars/4 is an EST of their share
                if isinstance(b, dict) and b.get('type') == 'thinking':
                    t['think'] += len(b.get('thinking') or '') // 4
            t['inp'] += i; t['out'] += o; t['cr'] += cr; t['cw'] += cw; t['turns'] += 1
            t['last'] = i + cr + cw
            ts = _ts(d.get('timestamp'))
            if ts:
                t['t0'] = t['t0'] or ts
                t['t1'] = ts
                t['pts'].append((ts, t['last']))
    return t


def acct_state(models):
    """Accounting label for a list of model names [MEASURED counts]: Ledger = no model recorded (tokens only), Priced = every reply has a known list price, Mixed = some, Unpriced = none."""
    ms = [m for m in models if m]
    if not ms:
        return 'Ledger'
    k = sum(1 for m in ms if any(f in m.lower() for f in ('opus', 'sonnet', 'haiku')))
    return 'Priced' if k == len(ms) else ('Mixed' if k else 'Unpriced')


def totals_inc(path, state_file):
    """Incremental scan: only bytes after the saved offset, and only up to the last complete line (an unfinished line is left for next time).
    Returns the same dict as totals(); offset + running totals live in state_file. Falls back to a full scan if the log shrank."""
    try:
        st = json.load(open(state_file))
    except Exception:
        st = {}
    try:
        size = os.path.getsize(path)
    except OSError:
        return totals(path)
    if st.get('off', 0) > size or 't' not in st:
        st = {'off': 0, 't': None}
    base = st.get('t') or dict(inp=0, out=0, cr=0, cw=0, last=0, turns=0, t0=None, t1=None, pts=[], w5=0, w1h=0, think=0)
    with open(path, 'rb') as f:
        f.seek(st['off']); chunk = f.read()
    end = chunk.rfind(b'\n') + 1
    if end:
        import tempfile
        with tempfile.NamedTemporaryFile('wb', delete=False) as tmp:
            tmp.write(chunk[:end])
        try:
            d = totals(tmp.name)
        finally:
            os.unlink(tmp.name)
        for k in ('inp', 'out', 'cr', 'cw', 'turns', 'w5', 'w1h', 'think'):
            base[k] += d[k]
        base['last'] = d['last'] or base['last']
        base['t0'] = base['t0'] or d['t0']; base['t1'] = d['t1'] or base['t1']
        base['pts'] = (base['pts'] + d['pts'])[-200:]
        try:
            os.makedirs(os.path.dirname(state_file), exist_ok=True)
            json.dump(dict(off=st['off'] + end, t=base), open(state_file, 'w'))
        except OSError:
            pass
    return base


def _ts(v):
    try:
        return dt.datetime.fromisoformat(str(v).replace('Z', '+00:00')).timestamp()
    except Exception:
        return None


def burn(t, window=None):
    """(context tokens per minute, minutes until the context window is full) from the last <=10 min of log. None if unknowable. [est]"""
    window = window or cfg('ctx_window')
    pts = t['pts']
    if len(pts) < 2:
        return None, None
    end = pts[-1][0]
    rec = [p for p in pts if end - p[0] <= 600] or pts[-2:]
    dtm = (rec[-1][0] - rec[0][0]) / 60
    if dtm < 0.5 or rec[-1][1] <= rec[0][1]:
        return None, None
    rate = (rec[-1][1] - rec[0][1]) / dtm
    return rate, max(0, (window - t['last']) / rate)


def _when(ts, now):
    d = dt.datetime.fromtimestamp(ts)
    return d.strftime('%H:%M' if d.date() == now.date() else '%a %H:%M')


def limits(rl, now=None):
    """List of provider windows present in rl: {name,pct,reset,full}. Absent windows are not listed. [actual]; full is [est]."""
    now = now or dt.datetime.now()
    out = []
    for k, v in (rl or {}).items():
        if not isinstance(v, dict) or 'used_percentage' not in v:
            continue
        name, span = SPAN.get(k, (k, 0))
        u = v.get('used_percentage') or 0
        r = v.get('resets_at')
        try:
            rt = (r / 1000 if r > 1e12 else r) if isinstance(r, (int, float)) else _ts(r)
        except Exception:
            rt = None
        full = None
        if span and rt and 0 < u < 100:
            el = span - (rt - now.timestamp())
            if span * 0.05 <= el <= span:  # too early / inconsistent window => no forecast
                f = now.timestamp() + (100 - u) * el / u
                full = f if f < rt else None
        out.append(dict(name=name, pct=int(u), reset=_when(rt, now) if rt else '', full=_when(full, now) if full else ''))
    return out


def state(ctx_pct, lims):
    """ok | warn | stop from context % and plan %. Plan thresholds from config plan_warn/plan_stop."""
    plan = max([l['pct'] for l in lims] or [0])
    if plan >= cfg('plan_stop') or ctx_pct >= 95:
        return 'stop'
    return 'warn' if plan >= cfg('plan_warn') or ctx_pct >= 80 else 'ok'


def level(ctx_pct, lims):
    """NORMAL | ELEVATED | APPROACHING LIMIT | CRITICAL | EXHAUSTED from context % and provider plan % (plan % only if provided)."""
    plan = max([l['pct'] for l in lims] or [0])
    top = max(plan, ctx_pct)
    if plan >= 100 or ctx_pct >= 100:
        return 'EXHAUSTED'
    if plan >= cfg('plan_stop') or ctx_pct >= 95:
        return 'CRITICAL'
    if plan >= cfg('plan_warn') or ctx_pct >= 85:
        return 'APPROACHING LIMIT'
    return 'ELEVATED' if top >= 60 else 'NORMAL'


LEVEL_ACT = {'NORMAL': '', 'ELEVATED': 'skip optional research and background agents', 'APPROACHING LIMIT': 'finish the active task only; checkpoint (tz checkpoint)',
             'CRITICAL': 'tz handoff now, continue in a fresh session', 'EXHAUSTED': 'save progress; resume when capacity returns (tz resume). tz cannot bypass provider limits'}


def find_transcript(cwd):
    base = os.path.expanduser('~/.claude/projects')
    enc = ''.join(c if c.isalnum() else '-' for c in cwd)
    fs = glob.glob(os.path.join(base, enc, '*.jsonl')) or glob.glob(os.path.join(base, '*', '*.jsonl'))
    return max(fs, key=os.path.getmtime) if fs else None


def report(path, rl=None, now=None):
    """(text, info dict). Plain lines, each labelled."""
    t = totals(path)
    win = cfg('ctx_window')
    pct = t['last'] * 100 // win if win else 0
    lims = limits(rl, now)
    rate, mins = burn(t)
    st = state(pct, lims)
    L = []
    if not t['turns']:
        L.append('usage [actual]: no token usage found in the chat log' if path else 'usage: no chat log found (pass --transcript)')
    else:
        L.append(f"context [actual] {t['last'] // 1000}k tokens = {pct}% of {win // 1000}k window [est: window size is a setting, ctx_window]")
        L.append(f"tokens [actual] input {t['inp']} output {t['out']} cache_read {t['cr']} cache_write {t['cw']} ({t['turns']} replies)")
        L.append(f"burn [est] ~{int(rate)} ctx tokens/min, window full in ~{int(mins)} min" if rate else 'burn [est]: not enough timed replies to forecast')
    for l in lims:
        L.append(f"{l['name']} [actual] {l['pct']}%" + (f" resets {l['reset']}" if l['reset'] else '') + (f", at this pace full ~{l['full']} [est]" if l['full'] else ''))
    if not lims:
        L.append('5h/7d: not provided by this Claude Code build or login; not shown (never guessed)')
    lv = level(pct, lims)
    L.append(f'level: {lv}' + (f' - {LEVEL_ACT[lv]}' if LEVEL_ACT[lv] else ''))
    L.append(f'state: {st.upper()}' + (' - write handoff, continue in a fresh chat' if st != 'ok' else ''))
    return '\n'.join(L), dict(state=st, ctx_pct=pct, rate=rate, mins=mins, limits=lims, totals={k: v for k, v in t.items() if k != 'pts'})


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='tz status|forecast')
    ap.add_argument('cmd', nargs='?', default='status', choices=['status', 'forecast'])
    ap.add_argument('--transcript')
    ap.add_argument('--cwd', default=os.getcwd())
    ap.add_argument('--rate-limits', help='JSON like {"five_hour":{"used_percentage":40,"resets_at":...}}')
    a = ap.parse_args(argv)
    try:
        rl = json.loads(a.rate_limits) if a.rate_limits else None
    except ValueError:
        print('tz: --rate-limits is not valid JSON', file=sys.stderr)
        return 2
    path = a.transcript or find_transcript(os.path.abspath(a.cwd))
    text, info = report(path, rl)
    if a.cmd == 'forecast':
        text = '\n'.join(l for l in text.splitlines() if l.startswith(('burn', '5h', '7d', 'state')) or 'at this pace' in l)
    print(text)
    return 0 if info['state'] != 'stop' else 3


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
