#!/usr/bin/env python3
# `tz bench replay [--days N] [--root DIR] [--json]`: zero-cost benchmark. Replays real Claude Code chat logs offline
# (no model call, no money) and computes what TOKEN ZOMBIE saves and costs, from the token counts in the logs.
#   MECHANICAL  output trim/crush TZ applies by itself (exact tzout.cut logic, original kept for tz recall)
#   ADVICE      identical Grep/Glob/WebSearch/WebFetch repeats TZ flags; counted only as an upper bound (model may ignore advice)
#   OVERHEAD    every TZ-injected hook text (rules, advice, notes) + its skill listing lines, measured in TZ-on logs
#   REFETCH     tz recall / re-reads after a trim, measured in TZ-on logs (cost of the trim)
# A removed result of C chars at reply r stays in context for k later replies: saved input-eq = C/4 * (cache write + cache read * (k-1)).
# Cache expiry is ignored (every later reply billed as a cache read): that UNDER-counts savings. Compaction ends the carry.
import glob, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tzprice, tzout

tzout.spill = lambda text: 'replay'  # no disk writes: same cut() logic, recall id is a placeholder
CR, CW = tzprice.CACHE['read'], tzprice.CACHE['write_5m']
ADVICE_TOOLS = ('Grep', 'Glob', 'WebSearch', 'WebFetch')
READ_ONLY = ('Read', 'Grep', 'Glob', 'WebSearch', 'WebFetch', 'TodoWrite', 'ToolSearch', 'Skill')
MARK = re.compile(r'TOKEN ZOMBIE (?:trimmed: .*?\((\d+) chars\) not shown|crushed \w+: (\d+) chars removed)')


def _text(c):
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return '\n'.join(b.get('text', '') if isinstance(b, dict) else str(b) for b in c)
    return ''


def would_cut(tool, ti, text):
    """Chars TZ's PostToolUse trim would remove from this result (0 = untouched). Same thresholds and code as tzout."""
    if 'TOKEN ZOMBIE' in text[-400:] or 'TOKEN ZOMBIE trimmed' in text:
        return 0
    if tool == 'Read':
        if ti.get('offset') or ti.get('limit'):
            return 0
        c = tzout.cut(text, tzout.READ_MAX, True)
    elif tool in ('Grep', 'Bash', 'WebFetch') or tool.startswith('mcp__'):
        c = tzout.cut(text, tzout.OTHER_MAX, False)
    else:
        return 0
    return max(0, c[1]) if c else 0


def session(path):
    """One transcript -> dict of measured totals (chars carried as input-eq tokens)."""
    tools, replies, seen = {}, [], set()  # replies: (model, input-eq tokens)
    ev = []  # (reply index when it entered context, segment, kind, chars)
    seg, tz_on, last_gen, gen = 0, False, {}, 0
    trimmed_paths = set()
    for ln in open(path, errors='replace'):
        if '"isCompactSummary":true' in ln or '"type":"summary"' in ln[:40]:
            seg += 1
        try:
            d = json.loads(ln)
        except Exception:
            continue
        m = d.get('message') if isinstance(d.get('message'), dict) else {}
        r = len(replies)
        if d.get('type') == 'assistant':
            u = m.get('usage')
            if isinstance(u, dict) and m.get('id') not in seen:
                seen.add(m.get('id'))
                g = lambda k: u.get(k) or 0
                replies.append((m.get('model') or '', seg, g('input_tokens') + CR * g('cache_read_input_tokens') + CW * g('cache_creation_input_tokens'),
                                g('output_tokens')))
            for b in m.get('content') if isinstance(m.get('content'), list) else []:
                if isinstance(b, dict) and b.get('type') == 'tool_use':
                    tools[b.get('id')] = (b.get('name') or '', b.get('input') or {})
            continue
        content = m.get('content')
        blocks = content if isinstance(content, list) else []
        results = [b for b in blocks if isinstance(b, dict) and b.get('type') == 'tool_result']
        if not results:
            a = d.get('attachment') if isinstance(d.get('attachment'), dict) else {}
            ac = a.get('content')
            if a.get('type') == 'hook_additional_context':  # the text TZ hooks inject into context (hook_success is a duplicate record)
                n = sum(len(x) for x in (ac if isinstance(ac, list) else [ac]) if isinstance(x, str) and 'TOKEN ZOMBIE' in x)
            elif a.get('type') == 'skill_listing' and isinstance(ac, str):  # the plugin's skill descriptions
                n = sum(len(x) for x in ac.splitlines() if 'token-zombie' in x)
            else:
                n = 0
            if n:
                tz_on = True
                ev.append((r, seg, 'overhead', n))
            continue
        for b in results:
            name, ti = tools.get(b.get('tool_use_id'), ('', {}))
            t = _text(b.get('content'))
            for a, c in MARK.findall(t):  # TZ really trimmed this (TZ-on log): measured saving
                tz_on = True
                ev.append((r, seg, 'actual', int(a or c)))
            if name == 'Bash' and 'tz recall' in str(ti.get('command', '')) or (name == 'Read' and ti.get('offset') and ti.get('file_path') in trimmed_paths):
                ev.append((r, seg, 'refetch', len(t)))
            if 'TOKEN ZOMBIE trimmed' in t and name == 'Read':
                trimmed_paths.add(ti.get('file_path'))
            cut = would_cut(name, ti, t)
            if cut:
                ev.append((r, seg, 'mechanical', cut))
                if name == 'Read':
                    trimmed_paths.add(ti.get('file_path'))
            if name in ADVICE_TOOLS:
                key = name + json.dumps(ti, sort_keys=True)
                if key in last_gen and (last_gen[key] == gen or name.startswith('Web')):
                    ev.append((r, seg, 'advice', len(t)))
                last_gen[key] = gen
            elif name not in READ_ONLY:
                gen += 1
    left = {}  # replies after index i in the same segment
    for i in range(len(replies) - 1, -1, -1):
        s = replies[i][1]
        left[i] = 1 + (left.get(i + 1, 0) if i + 1 < len(replies) and replies[i + 1][1] == s else 0)
    model = max((x[0] for x in replies), key=[x[0] for x in replies].count) if replies else ''
    out = dict(path=path, tz_on=tz_on, replies=len(replies), model=model,
               base_ieq=sum(x[2] for x in replies), base_out=sum(x[3] for x in replies),
               base_usd=sum(tzprice.cost_usd(x[0], x[2], x[3]) for x in replies))
    for k in ('mechanical', 'advice', 'overhead', 'actual', 'refetch'):
        out[k] = 0.0
    for r, s, k, chars in ev:
        n = left.get(r, 0) if r < len(replies) and replies[r][1] == s else 0
        if n:
            out[k] += chars / 4 * (CW + CR * (n - 1))
    return out


def run(root, days):
    cut = time.time() - days * 86400 if days else 0
    files = [f for f in glob.glob(os.path.join(root, '**', '*.jsonl'), recursive=True) if os.path.getmtime(f) >= cut]
    return [s for s in (session(f) for f in files) if s['replies']]


def summary(rows):
    out = {}
    for cls, sel in (('all', rows), ('tz_off', [r for r in rows if not r['tz_on']]), ('tz_on', [r for r in rows if r['tz_on']])):
        t = {k: sum(r[k] for r in sel) for k in ('base_ieq', 'base_usd', 'mechanical', 'advice', 'overhead', 'actual', 'refetch')}
        t['sessions'] = len(sel)
        t['replies'] = sum(r['replies'] for r in sel)
        t['usd_per_ieq'] = t['base_usd'] / t['base_ieq'] if t['base_ieq'] else 0
        out[cls] = t
    on = out['tz_on']
    # measured in TZ-on logs, applied to TZ-off logs: overhead per reply, refetch per trimmed token
    out['rates'] = dict(overhead_per_reply=on['overhead'] / on['replies'] if on['replies'] else 0,
                        refetch_ratio=on['refetch'] / on['actual'] if on['actual'] else 0)
    off = out['tz_off']; rt = out['rates']
    # all chats: TZ-on = MEASURED trims; TZ-off = TZ rules replayed (refetch + overhead at TZ-on measured rates)
    saved = on['actual'] - on['refetch'] + off['mechanical'] * (1 - rt['refetch_ratio'])
    ovh = on['overhead'] + rt['overhead_per_reply'] * off['replies']
    without = out['all']['base_ieq'] + on['actual'] - on['refetch'] - on['overhead']  # what the same chats cost with TZ removed
    usd = out['all']['usd_per_ieq']
    if without:
        net = saved - ovh
        out['verdict'] = dict(
            basis='real logs, offline, no model call; TZ-on trims MEASURED, TZ-off chats replayed with TZ rules',
            without_tz_ieq=round(without), trim_saved_ieq=round(saved), overhead_ieq=round(ovh), net_saved_ieq=round(net),
            net_pct=round(100 * net / without, 2), net_usd=round(net * usd, 2),
            advice_upper_ieq=round(out['all']['advice']), advice_upper_pct=round(100 * out['all']['advice'] / without, 2))
    return out


def main(argv):
    days = int(argv[argv.index('--days') + 1]) if '--days' in argv else 0
    root = argv[argv.index('--root') + 1] if '--root' in argv else os.path.expanduser('~/.claude/projects')
    s = summary(run(root, days))
    if '--json' in argv:
        print(json.dumps(s, indent=1, default=round))
        return 0
    k = lambda x: f'{x / 1000:,.0f}k'
    print('TOKEN ZOMBIE replay benchmark [zero cost: real logs replayed offline, no model call]')
    for cls in ('tz_off', 'tz_on'):
        t = s[cls]
        print(f"  {cls:7} {t['sessions']:4} chats  {t['replies']:6} replies  baseline {k(t['base_ieq'])} input-eq  ~${t['base_usd']:,.2f} [EST list price]")
    on = s['tz_on']
    print(f"  TZ-on logs MEASURED: trimmed {k(on['actual'])}, refetched {k(on['refetch'])}, TZ overhead {k(on['overhead'])} input-eq")
    v = s.get('verdict')
    if v:
        print(f"  RESULT all chats: without TZ {k(v['without_tz_ieq'])} input-eq; trims saved {k(v['trim_saved_ieq'])} - TZ overhead {k(v['overhead_ieq'])}"
              f" = NET {k(v['net_saved_ieq'])} = {v['net_pct']}% (~${v['net_usd']:,.2f} EST)")
        print(f"  plus repeat-search advice, only if the model follows it: up to {k(v['advice_upper_ieq'])} = {v['advice_upper_pct']}% [upper bound]")
    print('  quality: mechanical trims keep the original (tz recall); refetches are counted as cost. Not measured: answer quality (needs live A/B).')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
