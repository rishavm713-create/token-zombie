#!/usr/bin/env python3
# Token-zombie optimization: duplicate-read + repeated-output detection (live cache and log analysis), output filter,
# task mode + model advice, savings ledger. Advice only: a full read is NEVER blocked here.
# Tokens are est = chars/4. measured = counted from real bytes/log; est = a guess about what the model would have used.
import hashlib, json, os, re, sys, time
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


def ledger(kind, chars, basis, session='x'):
    """Append savings (+) or overhead (-) event. basis: measured|est."""
    p = os.path.join(STATE, 'ledger.json')
    L = _load(p, [])
    L.append({'t': int(time.time()), 'kind': kind, 'tok': ET(chars), 'basis': basis, 's': session})
    _save(p, L[-2000:])


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
    _save(p, c)
    if old and old['h'] == h:
        ledger('dup-read-flagged', st.st_size, 'est', session)
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
    uses, results = [], {}
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


def stats():
    L = _load(os.path.join(STATE, 'ledger.json'), [])
    s = {'measured': 0, 'est': 0, 'overhead': 0}
    for e in L:
        if e['kind'].startswith('overhead'):
            s['overhead'] += e['tok']
        else:
            s[e['basis']] += e['tok']
    s['net_measured'] = s['measured'] - s['overhead']
    s['net_est'] = s['measured'] + s['est'] - s['overhead']
    return s


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
        if not path:
            print('no chat log found (pass --transcript)')
    elif a.cmd == 'stats':
        s = stats()
        print(f"saved [measured] {s['measured']} tok | saved [est] {s['est']} tok | overhead [measured] {s['overhead']} tok")
        print(f"NET measured-only {s['net_measured']} tok | NET incl. estimates {s['net_est']} tok")
        print('Note: guard hook messages are not yet counted as overhead; savings are only counted for events this tool recorded.')
    elif a.cmd == 'filter':
        txt = sys.stdin.read()
        out, b, af = filter_output(txt, a.lines)
        print(out)
        print(f'[tz filter: {b} -> {af} chars measured, ~{ET(b - af)} tok saved est]', file=sys.stderr)
        ledger('filter', max(0, b - af), 'measured')
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
                ledger('overhead-hook', len(adv), 'measured', d.get('session_id', 'x'))
                print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'additionalContext': adv}}))
        except Exception:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
