#!/usr/bin/env python3
# `tz budget [check] | set KEY AMOUNT|off`: spend budgets (tokens / EST USD, per chat and per 7 days) with a warning ladder.
# alert_level / is_raised / budget_of adapted from ruvnet/ruflo plugins/ruflo-mods/hooks/cost/budget.ts (MIT, Copyright (c) 2024-2026 ruvnet), see NOTICE.
# This is cumulative SPEND. Chat SIZE warnings (limit/hard, size_gate/size_cap) and provider plan % (plan_warn/stop) live elsewhere.
import datetime as dt, glob, json, math, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tzprice
from tzlib import feature
from tzusage import _ts, find_transcript

LEVELS = (('HARD_STOP', 1.0), ('CRITICAL', 0.9), ('WARNING', 0.75), ('INFO', 0.5))
ORDER = {'OK': 0, 'INFO': 1, 'WARNING': 2, 'CRITICAL': 3, 'HARD_STOP': 4}
KEYS = ('session_tokens', 'session_usd', 'week_tokens', 'week_usd')
ACT = {'INFO': 'half used, no change needed', 'WARNING': 'trim context and prefer cheaper models',
       'CRITICAL': 'finish the active task only and checkpoint', 'HARD_STOP': 'budget used up: start no new work without the owner'}
HOOK_SECS = 0.5  # WHY: a first weekly scan can be large; the rest is read on later calls (sums are lower bounds until then)
WEEK = 7


def alert_level(u):
    """Rung name for utilization u = spent / budget."""
    return next((name for name, at in LEVELS if u >= at), 'OK')


def is_raised(prev, nxt):
    """True only for a strictly higher rung: the one moment to tell."""
    return ORDER[nxt] > ORDER[prev]


def budget_of(x):
    """Finite positive number or numeric string, else None (off, never a zero budget that halts at once)."""
    if isinstance(x, bool) or not isinstance(x, (int, float, str)):
        return None
    try:
        n = float(x)
    except (ValueError, OverflowError):
        return None
    return n if math.isfinite(n) and n > 0 else None


def run_note(before, spent, budget):
    """Per-run ladder (`tz agent --budget`): one line when this step reached a higher rung, else ''. Stateless."""
    b = budget_of(budget)
    if not b or not feature('budget_warn'):
        return ''
    lv = alert_level(spent / b)
    if not is_raised(alert_level(before / b), lv):
        return ''
    return f'TOKEN ZOMBIE budget {lv}: this run used {int(spent):,} of {int(b):,} tokens ({spent * 100 // b:.0f}%): {ACT[lv]}.'


def _dir():
    return os.path.expanduser('~/.claude/token-zombie')


def _json(path):
    try:
        d = json.load(open(path))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _write(path, d):
    """Atomic JSON write."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = '%s.tmp%d' % (path, os.getpid())
    with open(tmp, 'w') as f:
        json.dump(d, f)
    os.replace(tmp, path)


def budgets():
    """{key: amount} for the budgets that are on: env TZ_BUDGET_<KEY> beats config.json "budget"."""
    conf = _json(os.path.join(_dir(), 'config.json')).get('budget')
    conf = conf if isinstance(conf, dict) else {}
    out = {k: budget_of(os.environ.get('TZ_BUDGET_' + k.upper(), conf.get(k))) for k in KEYS}
    return {k: v for k, v in out.items() if v}


def _add(entry, line, fallback_ts):
    """Add one log line's usage to the entry's day bucket [tokens, usd]; repeated reply ids count once."""
    try:
        d = json.loads(line)
        m = d.get('message') or {}
        u = m.get('usage')
        if not isinstance(u, dict):
            return
        key = m.get('id') or d.get('uuid')
        if key and key in entry['ids']:
            return
        g = lambda src, k: src.get(k) or 0
        i, o, cr, cw = (g(u, k) for k in ('input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens'))
        cc = u.get('cache_creation') if isinstance(u.get('cache_creation'), dict) else {}
        long = g(cc, 'ephemeral_1h_input_tokens')
        usd = tzprice.cost_usd(m.get('model'), i, o, cr, max(0, cw - long), long)
        day = dt.date.fromtimestamp(_ts(d.get('timestamp')) or fallback_ts).isoformat()
        row = entry['days'].setdefault(day, [0, 0.0])
        row[0] += i + o + cr + cw
        row[1] += usd
        if key:  # WHY kept in state: one reply is logged on several lines and a hook can run between them
            entry['ids'] = (entry['ids'] + [key])[-20:]
    except Exception:
        pass


def scan(paths, files, deadline=None):
    """Read only the new complete lines of each log into files[path]; False when the deadline cut the scan short."""
    for p in paths:
        try:
            size, mt = os.path.getsize(p), os.path.getmtime(p)
        except OSError:
            continue
        e = files.get(p)
        if not e or e['off'] > size:
            e = files[p] = dict(off=0, ids=[], days={}, mt=mt)
        e['mt'] = mt
        if e['off'] >= size:
            continue
        if deadline and time.time() >= deadline:
            return False
        with open(p, 'rb') as f:
            f.seek(e['off'])
            for n, raw in enumerate(f, 1):
                if not raw.endswith(b'\n'):
                    break  # unfinished line: next time
                e['off'] += len(raw)
                if b'"usage"' in raw:
                    _add(e, raw.decode('utf-8', 'ignore'), mt)
                if deadline and n % 500 == 0 and time.time() >= deadline:
                    return False
    return True


def session_logs(transcript):
    """The chat log plus its subagent logs."""
    if not transcript or not os.path.isfile(transcript):
        return []
    sub = os.path.join(glob.escape(os.path.splitext(transcript)[0]), 'subagents', '**', '*.jsonl')
    return [transcript] + sorted(glob.glob(sub, recursive=True))


def week_logs(now):
    """Every local chat and subagent log touched in the last 7 days, newest first."""
    base = glob.escape(os.path.expanduser('~/.claude/projects'))
    found = glob.glob(os.path.join(base, '*', '*.jsonl')) + glob.glob(os.path.join(base, '*', '*', 'subagents', '**', '*.jsonl'), recursive=True)
    fresh = []
    for p in found:
        try:
            mt = os.path.getmtime(p)
        except OSError:
            continue
        if now - mt <= WEEK * 86400:
            fresh.append((mt, p))
    return [p for _, p in sorted(fresh, reverse=True)]


def _sum(files, paths, since=''):
    rows = [v for p in paths for day, v in files.get(p, {}).get('days', {}).items() if day >= since]
    return sum(r[0] for r in rows), sum(r[1] for r in rows)


def status(transcript, limits, deadline=None, now=None):
    """One row per active budget: key, spent, limit, level, partial. Saves the scan cache."""
    now = now or time.time()
    path = os.path.join(_dir(), 'budget.json')
    st = _json(path)
    files = st.get('files') if isinstance(st.get('files'), dict) else {}
    mine = session_logs(transcript) if any(k.startswith('session_') for k in limits) else []
    week = week_logs(now) if any(k.startswith('week_') for k in limits) else []
    ok_mine = scan(mine, files, deadline)
    ok_week = scan(week, files, deadline)
    since = (dt.date.fromtimestamp(now) - dt.timedelta(days=WEEK - 1)).isoformat()
    sums = {'session': (_sum(files, mine), ok_mine, bool(mine)), 'week': (_sum(files, week, since), ok_week, True)}
    rows = []
    for k in KEYS:
        scope, unit = k.split('_')
        (tok, usd), complete, known = sums[scope]
        if k in limits and known:  # no chat log => session spend unknown, so no row (never shown as zero)
            spent = tok if unit == 'tokens' else usd
            rows.append(dict(key=k, spent=spent, limit=limits[k], level=alert_level(spent / limits[k]), partial=not complete))
    keep = set(mine)
    st['files'] = {p: e for p, e in files.items() if p in keep or now - e.get('mt', 0) <= (WEEK + 1) * 86400}
    _write(path, st)
    return rows


def line(r):
    """Human text for one status row, numbers labelled."""
    scope, unit = r['key'].split('_')
    if unit == 'tokens':
        nums = f"{int(r['spent']):,} of {int(r['limit']):,} tokens [{'actual' if scope == 'session' else 'est'} from local logs]"
    else:
        nums = f"${r['spent']:.2f} of ${r['limit']:.2f} [est, {tzprice.LABEL.replace('EST ', '')}]"
    name = 'this chat' if scope == 'session' else 'last 7 days'
    more = ' (partial scan: at least this much)' if r['partial'] else ''
    return f"{name}: {nums}, {r['spent'] * 100 / r['limit']:.0f}%{more}"


def _said_key(data, r):
    """Rung memory is per chat for chat budgets, shared for weekly ones; a changed limit starts a new ladder."""
    owner = data.get('session_id', 'x') if r['key'].startswith('session_') else 'all'
    return f"{owner}:{r['key']}:{r['limit']:g}"


def _remember(name, key, value):
    path = os.path.join(_dir(), 'budget.json')
    st = _json(path)
    d = st.get(name) if isinstance(st.get(name), dict) else {}
    d.pop(key, None)
    if value is not None:
        d[key] = value  # newest last
    st[name] = {k: d[k] for k in list(d)[-100:]}
    _write(path, st)


def prompt_advice(data, now=None):
    """UserPromptSubmit advice: one line per budget that reached a higher rung since last told; '' otherwise."""
    limits = budgets() if feature('budget_warn') else {}
    if not limits:
        return ''
    rows = status(data.get('transcript_path'), limits, time.time() + HOOK_SECS, now)
    said = _json(os.path.join(_dir(), 'budget.json')).get('said') or {}
    out = []
    for r in rows:
        k = _said_key(data, r)
        prev = said.get(k, 'OK')
        if is_raised(prev, r['level']):
            _remember('said', k, r['level'])
            out.append(f"TOKEN ZOMBIE budget {r['level']}: {line(r)}. Tell the owner in one line; {ACT[r['level']]}.")
        elif prev != 'OK' and r['level'] == 'OK' and not r['partial']:
            _remember('said', k, None)  # the weekly window rolled off: warn again on the next climb
    return '\n'.join(out)


def block_reason(data, now=None):
    """Opt-in (budget_block): why a new prompt is refused at HARD_STOP, else ''. Slash commands and Fresh chat pass."""
    prompt = (data.get('prompt') or '').strip()
    if not feature('budget_block') or prompt.startswith('/') or re.fullmatch(r'(?i)fresh chat[.!]?', prompt):
        return ''
    limits = budgets()
    if not limits:
        return ''
    hit = [r for r in status(data.get('transcript_path'), limits, time.time() + HOOK_SECS, now) if r['level'] == 'HARD_STOP']
    if not hit:
        return ''
    key = '|'.join(_said_key(data, r) for r in hit)
    saved = (_json(os.path.join(_dir(), 'budget.json')).get('saved') or {}).get(key)
    if not saved:  # handoff first, once per budget hit
        import tztips
        saved = tztips.save_handoff(data.get('cwd') or os.getcwd(), 'auto-saved at a spend budget stop, session %s.\nChat log: %s\nNext: read this file, check git status, continue.'
                                    % (data.get('session_id', 'x'), data.get('transcript_path')))
        if saved:
            _remember('saved', key, saved)
    return ('TOKEN ZOMBIE budget HARD_STOP: %s. Your last message was not sent; %s. Raise the budget (tz budget set %s AMOUNT), '
            'or turn the block off: TZ_FEAT_BUDGET_BLOCK=0, or "features": {"budget_block": 0} in ~/.claude/token-zombie/config.json.'
            % ('; '.join(map(line, hit)), 'handoff saved to ' + saved if saved else 'handoff could NOT be saved (run `tz handoff save`)', hit[0]['key']))


def set_budget(key, amount):
    """Write or remove one budget in config.json, keeping every other setting; returns an error text or ''."""
    if key not in KEYS or (amount != 'off' and not budget_of(amount)):
        return 'usage: tz budget set <%s> <positive number|off>' % '|'.join(KEYS)
    path = os.path.join(_dir(), 'config.json')
    conf = _json(path)
    if not conf and os.path.exists(path) and open(path).read().strip() not in ('', '{}'):
        return 'config.json is not valid JSON: fix it first (not overwritten)'
    b = conf.get('budget') if isinstance(conf.get('budget'), dict) else {}
    b.pop(key, None)
    if amount != 'off':
        b[key] = budget_of(amount)
    conf['budget'] = b
    _write(path, conf)
    return ''


def main(argv=None):
    """show (default) | check (exit 1 at HARD_STOP) | set KEY AMOUNT|off."""
    a = list(sys.argv[1:] if argv is None else argv)
    if a[:1] == ['set'] and len(a) == 3:
        err = set_budget(a[1], a[2])
        print(err or f'budget {a[1]}: {a[2]}')
        return 2 if err else 0
    if a not in ([], ['show'], ['check']):
        print('usage: tz budget [show|check] | tz budget set <%s> <positive number|off>' % '|'.join(KEYS))
        return 2
    limits = budgets()
    if not limits:
        print('no budget set (off). Example: tz budget set week_usd 20   keys: ' + ' '.join(KEYS))
        return 0
    rows = status(find_transcript(os.getcwd()), limits)
    for r in rows:
        print(f"{r['level']:9} {line(r)}")
    shown = {r['key'] for r in rows}
    for k in limits:
        if k not in shown:
            print(f'UNKNOWN   {k}: no chat log found')
    print('warnings %s, blocking %s' % tuple('on' if feature(f) else 'off' for f in ('budget_warn', 'budget_block')))
    return 1 if a == ['check'] and any(r['level'] == 'HARD_STOP' for r in rows) else 0


if __name__ == '__main__':
    sys.exit(main())
