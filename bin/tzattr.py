#!/usr/bin/env python3
# `tz attr [LOG] [--json]`: MEASURED per-tool attribution from a chat log: calls and result chars per MCP server and per subagent (Task/Agent) call.
#   Tokens = chars/4 (EST). Result sizes only: input cost of the schemas is in `tz startup`.
# `tz conflicts FILE...`: instruction rules that say both always/never (or must/must not) about the same words across files. Heuristic, advice only.
import json, os, re, sys, collections


def attribute(path):
    calls, out = {}, collections.defaultdict(lambda: {'calls': 0, 'result_chars': 0, 'errors': 0})
    for ln in open(path, errors='replace'):
        try:
            c = (json.loads(ln).get('message') or {}).get('content')
        except Exception:
            continue
        for b in c if isinstance(c, list) else []:
            if not isinstance(b, dict):
                continue
            if b.get('type') == 'tool_use':
                n = b.get('name', '')
                k = 'mcp:' + n.split('__')[1] if n.startswith('mcp__') and n.count('__') >= 2 else 'subagent' if n in ('Task', 'Agent') else None
                if k:
                    calls[b.get('id')] = k
                    out[k]['calls'] += 1
            elif b.get('type') == 'tool_result' and b.get('tool_use_id') in calls:
                e = out[calls[b['tool_use_id']]]
                e['result_chars'] += len(json.dumps(b.get('content')))
                e['errors'] += bool(b.get('is_error'))
    return dict(out)


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
    r = attribute(p)
    if '--json' in argv:
        print(json.dumps(r)); return 0
    print(f'attribution [MEASURED counts/chars; tokens EST chars/4] {os.path.basename(p)}:')
    for k, v in sorted(r.items(), key=lambda x: -x[1]['result_chars']):
        print(f"  {k:24} {v['calls']:>4} calls  ~{v['result_chars'] // 4} result tok  {v['errors']} errors")
    if not r:
        print('  no MCP or subagent calls in this log')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
