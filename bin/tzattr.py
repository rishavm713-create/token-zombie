#!/usr/bin/env python3
# `tz attr [LOG] [--json]`: MEASURED per-tool attribution from a chat log: calls and result chars per MCP server and per subagent (Task/Agent) call.
#   Tokens = chars/4 (EST). Result sizes only: input cost of the schemas is in `tz startup`.
# `tz conflicts FILE...`: instruction rules that say both always/never (or must/must not) about the same words across files. Heuristic, advice only.
import json, os, re, sys, collections


def _usage(path):
    """Sum assistant usage in one transcript, deduped by message id. MEASURED tokens; USD EST at list price (tzcont.PRICE)."""
    import tzcont
    r = dict(calls=0, input=0, output=0, cache_read=0, cache_write=0, usd=0.0); seen = set()
    for ln in open(path, errors='replace'):
        if '"usage"' not in ln:
            continue
        try:
            m = json.loads(ln).get('message') or {}; u = m.get('usage')
        except Exception:
            continue
        if not isinstance(u, dict) or (m.get('id') and m['id'] in seen):
            continue
        seen.add(m.get('id'))
        g = lambda k: u.get(k) or 0
        pin, pout = tzcont.PRICE[tzcont._fam(m.get('model'))]
        r['calls'] += 1; r['input'] += g('input_tokens'); r['output'] += g('output_tokens')
        r['cache_read'] += g('cache_read_input_tokens'); r['cache_write'] += g('cache_creation_input_tokens')
        r['usd'] += (g('input_tokens') + 0.1 * g('cache_read_input_tokens') + 1.25 * g('cache_creation_input_tokens')) * pin / 1e6 + g('output_tokens') * pout / 1e6
    return r


def _add(row, u):
    row['replies'] = row.get('replies', 0) + u['calls']  # model replies inside the transcript; 'calls' stays = launches
    for k in ('input', 'output', 'cache_read', 'cache_write', 'usd'):
        row[k] += u[k]


def _row():
    return {'calls': 0, 'result_chars': 0, 'errors': 0, 'invocations': 0, 'models': [], 'input': 0, 'output': 0, 'cache_read': 0, 'cache_write': 0, 'usd': 0.0}


def attribute(path):
    """{key: row}. mcp:<server> and subagent:<type> rows count calls/result chars (EST tok chars/4); subagent rows add MEASURED
    tokens from <log dir>/<session>/subagents/agent-<id>.jsonl; 'main' is the parent session's own usage (MEASURED)."""
    import glob
    calls, out = {}, collections.defaultdict(_row)
    agent_of = {}  # agentId -> subagent key
    for ln in open(path, errors='replace'):
        try:
            d = json.loads(ln); c = (d.get('message') or {}).get('content')
        except Exception:
            continue
        for b in c if isinstance(c, list) else []:
            if not isinstance(b, dict):
                continue
            if b.get('type') == 'tool_use':
                n = b.get('name', ''); i = b.get('input') if isinstance(b.get('input'), dict) else {}
                sub = n in ('Task', 'Agent')
                k = 'mcp:' + n.split('__')[1] if n.startswith('mcp__') and n.count('__') >= 2 else 'subagent:' + str(i.get('subagent_type') or 'general-purpose') if sub else None
                if k:
                    calls[b.get('id')] = k
                    out[k]['calls'] += 1
                    if sub:
                        out[k]['invocations'] += 1
                        if i.get('model') and i['model'] not in out[k]['models']:
                            out[k]['models'].append(i['model'])
            elif b.get('type') == 'tool_result' and b.get('tool_use_id') in calls:
                k = calls[b['tool_use_id']]; e = out[k]
                e['result_chars'] += len(json.dumps(b.get('content')))
                e['errors'] += bool(b.get('is_error'))
                if k.startswith('subagent:'):
                    tr = d.get('toolUseResult'); aid = tr.get('agentId') if isinstance(tr, dict) else None
                    if not aid:
                        m = re.search(r'agentId:\s*([\w-]+)', json.dumps(b.get('content')))
                        aid = m.group(1) if m else None
                    if aid:
                        agent_of[aid] = k
    sdir = os.path.join(os.path.dirname(os.path.abspath(path)), os.path.basename(path).rsplit('.', 1)[0], 'subagents')
    for f in sorted(glob.glob(os.path.join(sdir, '*.jsonl'))):
        aid = os.path.basename(f)[:-6].replace('agent-', '', 1)
        _add(out[agent_of.get(aid, 'subagent:unmatched')], _usage(f))
    _add(out['main'], _usage(path))
    out['main']['calls'] = out['main']['replies']  # main row: calls = its own model replies
    return {k: dict(v, usd=round(v['usd'], 4)) for k, v in out.items()}


def totals(r):
    t = {k: sum(v[k] for v in r.values()) for k in ('calls', 'input', 'output', 'cache_read', 'cache_write', 'result_chars')}
    t['usd'] = round(sum(v['usd'] for v in r.values()), 4)
    return t


def conflicts(texts):
    """texts {name: str} -> [(a_file, b_file, topic)]: an 'always/must X' in one file and 'never/must not X' in another about the same 2+ content words."""
    pos, neg = [], []
    for nm, t in texts.items():
        for ln in t.split('\n'):
            m = re.search(r"\b(never|do not|don't|must not|avoid)\b(.*)", ln, re.I) or None
            w = lambda s: frozenset(x for x in re.findall(r'[a-z]{4,}', s.lower()) if x not in ('that', 'this', 'with', 'from', 'when', 'your', 'have', 'then', 'only'))
            if m:
                neg.append((nm, w(m.group(2))))
            else:
                m = re.search(r'\b(always|must)\b(.*)', ln, re.I)
                if m:
                    pos.append((nm, w(m.group(2))))
    res = []
    for a, wa in pos:
        for b, wb in neg:
            common = wa & wb
            if a != b and len(common) >= 2 and len(common) * 2 >= min(len(wa), len(wb)):
                res.append((a, b, ' '.join(sorted(common))[:60]))
    return list(dict.fromkeys(res))


def main(argv):
    a = [x for x in argv if not x.startswith('--')]
    if argv[:1] == ['conflicts'] or (argv and argv[0] == 'conflicts'):
        files = [x for x in a[1:] if os.path.isfile(x)]
        r = conflicts({os.path.basename(f): open(f, errors='replace').read() for f in files})
        for x, y, t in r:
            print(f'CONFLICT? {x} says always/must, {y} says never/avoid: "{t}" (heuristic, review by hand)')
        print(f'{len(r)} possible conflicts in {len(files)} files')
        return 0
    p = a[1] if len(a) > 1 else None
    if not p:
        import tzusage
        p = tzusage.find_transcript(os.getcwd())
    if not p or not os.path.isfile(p):
        print('tz attr: no chat log found (UNAVAILABLE)'); return 1
    r = attribute(p); t = totals(r)
    if '--json' in argv:
        print(json.dumps(dict(rows=r, total=t))); return 0
    print(f'attribution {os.path.basename(p)}: tokens MEASURED from usage fields (in/out/cache; $ EST list price); result tok EST chars/4')
    for k, v in sorted(r.items(), key=lambda x: -(x[1]['usd'] or x[1]['result_chars'])):
        if k == 'main' or k.startswith('subagent:'):
            m = f"  [{','.join(v['models'])}]" if v['models'] else ''
            print(f"  {k:30} {v['calls']:>4} calls  in {v['input']} out {v['output']} cache r{v['cache_read']}/w{v['cache_write']} MEASURED  ${v['usd']:.4f}  ~{v['result_chars'] // 4} result tok EST{m}")
        else:
            print(f"  {k:30} {v['calls']:>4} calls  ~{v['result_chars'] // 4} result tok EST  {v['errors']} errors")
    print(f"  {'TOTAL':30} {t['calls']:>4} calls  in {t['input']} out {t['output']} cache r{t['cache_read']}/w{t['cache_write']} MEASURED  ${t['usd']:.4f}  ~{t['result_chars'] // 4} result tok EST")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
