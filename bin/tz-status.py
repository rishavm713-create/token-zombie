#!/usr/bin/env python3
# Token-zombie statusline: runs the previous statusline (saved by install.sh) and appends
# "TZ <growth>k/<limit>k | off N skills ~Xk/chat saved". --report prints the same numbers as plain lines;
# --history [days] prints per-day tokens by model from the local chat logs.
# --startup [N] audits what a new chat loads before any work (advice only; see tzstartup.py).
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tzlib import chat_tokens, skills_off, LIMIT

CONF = os.path.expanduser('~/.claude/token-zombie/config.json')

report = '--report' in sys.argv


def history(days, roots):
    """Per-day tokens by model from local chat logs only (ccusage-style). Dedup by message id + request id."""
    import datetime as dt, glob, time
    cut = time.time() - days * 86400
    since = (dt.date.today() - dt.timedelta(days=days - 1)).isoformat()
    seen, rows, chats = set(), {}, set()
    for root in roots:
        for f in glob.glob(os.path.join(root, 'projects', '**', '*.jsonl'), recursive=True):
            if os.path.getmtime(f) < cut:
                continue
            for line in open(f, encoding='utf-8', errors='ignore'):
                if '"usage"' not in line or '"assistant"' not in line:
                    continue
                try:
                    e = json.loads(line)
                    m = e['message']
                    u = m['usage']
                    key = f"{m.get('id')}:{e.get('requestId')}"
                    day = dt.datetime.fromisoformat(e['timestamp'].replace('Z', '+00:00')).astimezone().date().isoformat()
                except Exception:
                    continue
                if key in seen or day < since or m.get('model') == '<synthetic>':
                    continue
                seen.add(key)
                chats.add(f)
                r = rows.setdefault((day, m.get('model') or '?'), [0, 0, 0, 0])
                for i, k in enumerate(('input_tokens', 'output_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens')):
                    r[i] += u.get(k) or 0
    fmt = lambda n: f'{n / 1e6:.1f}M' if n >= 1e6 else f'{n // 1000}k'
    print(f'HISTORY last {days} days (local chat logs; measured; dedup by message+request id)')
    print(f"  {'day':10} {'model':26} {'input':>7} {'output':>7} {'c.write':>7} {'c.read':>7} {'total':>7}")
    for (day, model), r in sorted(rows.items()):
        print(f'  {day:10} {model[:26]:26} ' + ' '.join(f'{fmt(x):>7}' for x in r + [sum(r)]))
    tot = [sum(r[i] for r in rows.values()) for i in range(4)]
    print(f"  {'all':10} {'':26} " + ' '.join(f'{fmt(x):>7}' for x in tot + [sum(tot)]))
    from tzstartup import median_startup
    ms = median_startup(roots[0])
    if ms and sum(tot):
        print(f'  startup: {len(chats)} chats x {ms // 1000}k median start (MEASURED) = ~{fmt(len(chats) * ms)} = ~{100 * len(chats) * ms // sum(tot)}% of all tokens above (EST: counts every log with activity as one new chat; resumed chats are over-counted)')


if '--startup' in sys.argv:
    from tzstartup import startup
    a = sys.argv[sys.argv.index('--startup') + 1:]
    startup(int(a[0]) if a and a[0].isdigit() else 12, '--save' in sys.argv, '--compare' in sys.argv)
    sys.exit(0)
if '--history' in sys.argv:
    a = sys.argv[sys.argv.index('--history') + 1:]
    roots = [os.path.expanduser(r) for r in (os.environ.get('CLAUDE_CONFIG_DIR') or '~/.claude').split(',')]
    history(int(a[0]) if a and a[0].isdigit() else 7, roots)
    sys.exit(0)
raw = '' if (report or sys.stdin.isatty()) else sys.stdin.read()
try:
    data = json.loads(raw) if raw else {}
except Exception:
    data = {}

path = data.get('transcript_path')
if report and not path:  # newest chat log of any project
    import glob
    logs = glob.glob(os.path.expanduser('~/.claude/projects/*/*.jsonl'))
    path = max(logs, key=os.path.getmtime) if logs else None
base, last = chat_tokens(path)
grow = max(0, last - base)
n, tok = skills_off()

if report:
    from tzlib import cfg
    home = os.path.expanduser('~/.claude')
    try:
        st = json.load(open(f'{home}/settings.json'))
    except Exception:
        st = {}
    print('ACTUAL (from chat log usage, measured)')
    print(f'  chat start: {base // 1000}k tokens  now: {last // 1000}k  growth: {grow // 1000}k')
    print('  plan 5h/weekly %: use get_usage or the statusline (real provider data only; not guessed here)')
    print('STARTUP OVERHEAD (loads every chat)')
    for f in (f'{home}/CLAUDE.md', f'{home}/RTK.md', os.path.join(os.getcwd(), 'CLAUDE.md')):
        if os.path.isfile(f):
            print(f'  {f}: ~{os.path.getsize(f) // 4} tokens (bytes/4 estimate)')
    print('  MCP tools, system tools, skill list: run /context for the measured split')
    print('LOADED')
    on = [k for k, v in (st.get('enabledPlugins') or {}).items() if v]
    sk = [d for d in os.listdir(f'{home}/skills') if os.path.isfile(f'{home}/skills/{d}/SKILL.md')] if os.path.isdir(f'{home}/skills') else []
    print(f'  plugins on: {len(on)} ({", ".join(on)})  skills on: {len(sk)}')
    tz = [ev for ev, gs in (st.get('hooks') or {}).items() if any('token-zombie' in x.get('command', '') for g in gs for x in g.get('hooks', []))]
    print(f'  token-zombie hooks installed: {", ".join(tz) or "none"}')
    print('ESTIMATED SAVINGS (not measured; upper bounds)')
    print(f'  skills kept off: {n}, descriptions ~{tok // 1000}k tokens; the app caps the skill list, so real saving is lower')
    hm = os.path.join(os.getcwd(), 'HANDOFF.md')
    if os.path.isfile(hm):
        print(f'  HANDOFF.md {os.path.getsize(hm) // 1024} KB: lean start injects <=4000 chars instead (saving only if it would have been read whole)')
    print('ACTIVE RULES (tunable in ~/.claude/token-zombie/config.json)')
    print(f"  fresh session for next task at {cfg('limit') // 1000}k growth; hand off rest at safe point at {cfg('hard') // 1000}k;"
          f" whole-Read nudge > {cfg('read_warn') // 1000} KB (once per file); plan warn {cfg('plan_warn')}% / stop {cfg('plan_stop')}%")
    print('WARNINGS')
    w = []
    if grow >= cfg('limit'):
        w.append(f'chat growth {grow // 1000}k past limit: finish task, next task in a fresh chat')
    if any('chat-size-guard' in x.get('command', '') for gs in (st.get('hooks') or {}).values() for g in gs for x in g.get('hooks', [])):
        w.append('old chat-size-guard.py still installed (counts startup as growth); install.sh replaces it')
    print('  ' + ('\n  '.join(w) if w else 'none'))
    print('  security: run bin/tz-vet.sh <dir> on any new skill before install')
    sys.exit(0)

prev = ''
try:
    cmd = json.load(open(CONF)).get('prev_statusline')
    if cmd:
        prev = subprocess.run(cmd, shell=True, input=raw, capture_output=True, text=True, timeout=3).stdout.strip()
except Exception:
    pass
pct = grow * 100 // LIMIT if LIMIT else 0
color = '32' if pct < 70 else '33' if pct < 100 else '31'
# plan limits, if this Claude Code passes them to the statusline (newer versions: rate_limits)
rl = data.get('rate_limits') or {}
from tzlib import cfg


def rdt(v):  # resets_at: epoch s/ms or ISO string -> local naive datetime, None if bad/absent
    import datetime as dt
    r = v.get('resets_at')
    try:
        return (dt.datetime.fromtimestamp(r / 1000 if r > 1e12 else r) if isinstance(r, (int, float))
                else dt.datetime.fromisoformat(str(r).replace('Z', '+00:00')).astimezone().replace(tzinfo=None))
    except Exception:
        return None


def reset(v):  # " @HH:MM" (or "Mon HH:MM" if not today); '' if absent
    import datetime as dt
    t = rdt(v)
    return '' if t is None else ' @' + t.strftime('%H:%M' if t.date() == dt.date.today() else '%a %H:%M')


def eta(k, v):  # burn-rate forecast: at the pace so far, when does this window hit 100% before it resets?
    import datetime as dt
    span = {'five_hour': 18000, 'seven_day': 604800}.get(k)
    t, u = rdt(v), v.get('used_percentage') or 0
    if not span or t is None or u <= 0 or u >= 100:
        return ''
    el = span - (t - dt.datetime.now()).total_seconds()
    if el < span * 0.05 or el > span:  # too early to extrapolate, or window data inconsistent
        return ''
    full = dt.datetime.now() + dt.timedelta(seconds=(100 - u) * el / u)
    return f' full~{full:%H:%M}' if full < t and full.date() == dt.date.today() else (f' full~{full:%a %H:%M}' if full < t else '')


lim = ' '.join(f"{ {'five_hour': '5h', 'seven_day': '7d'}.get(k, k)} {int(v.get('used_percentage', 0))}%{reset(v)}{eta(k, v)}"
               for k, v in rl.items() if isinstance(v, dict) and 'used_percentage' in v)
if lim and max(int(v.get('used_percentage', 0)) for v in rl.values() if isinstance(v, dict)) >= cfg('plan_warn'):
    lim = f'\033[31m{lim} (handoff ready?)\033[0m'
try:  # mascot emoji from the status bus: file reads only, no AI, never fatal
    import tzbus
    from tzmascot import mascot_state, EMOJI
    _b = tzbus.read_bus()
    mo = EMOJI[mascot_state(_b)] + ' ' if _b else ''
except Exception:
    mo = ''
tz = (f'{lim} | ' if lim else '') + f'{mo}\033[{color}mTZ {grow // 1000}k/{LIMIT // 1000}k\033[0m | off {n} skills ~{tok // 1000}k/chat saved'
print(f'{prev} | {tz}' if prev else tz)
