#!/usr/bin/env python3
# Four small advice-only tools, all MEASURED from local files, no network, no model calls:
#  tz reconcile            ledger.json savings vs tz.db vault (orig-shown chars/4): do the two records agree?
#  tz vault-find WORDS..   spilled outputs whose tool/target match the words (task-level retrieval; restore with `tz recall ID`)
#  tz overlap [SESSION_DIR] files edited by 2+ subagents of one session (conflict risk)
#  tz skills-outcome [DIR]  per skill: chats it ran in and their average rework score (tzrework); correlation, not proof of effect
import glob, json, os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def reconcile(ledger, db):
    """(ledger_tok, vault_tok, status). ledger = list of ledger.json rows; db = path to tz.db. Tolerance 10%."""
    led = sum(x['tok'] for x in ledger if isinstance(x, dict) and isinstance(x.get('tok'), (int, float))
              and x.get('basis') == 'measured' and x.get('kind') == 'output-trim')  # rtk rows are RTK's own savings, not in TZ's vault; overhead rows are costs
    try:
        c = sqlite3.connect(db)
        v = (c.execute('SELECT COALESCE(SUM(orig-shown),0) FROM vault').fetchone()[0] or 0) // 4
        c.close()
    except Exception:
        return led, None, 'UNAVAILABLE (no vault db)'
    if not led and not v:
        return led, v, 'EMPTY'
    return led, v, 'AGREE' if abs(led - v) <= 0.1 * max(led, v) else 'MISMATCH'


def vault_find(db, words, n=10):
    try:
        c = sqlite3.connect(db)
        rows = c.execute('SELECT id, tool, target, orig, shown FROM vault ORDER BY t DESC').fetchall()
        c.close()
    except Exception:
        return []
    ws = [w.lower() for w in words if len(w) > 2]
    hit = [(sum(w in f'{r[1]} {r[2]}'.lower() for w in ws), r) for r in rows]
    return [r for s, r in sorted(hit, key=lambda x: -x[0]) if s][:n]


def overlap(files):
    """files: agent transcript paths -> {file_path: [agent names]} for files edited by 2+ agents."""
    seen = {}
    for p in files:
        for ln in open(p, errors='replace'):
            try:
                c = (json.loads(ln).get('message') or {}).get('content')
            except Exception:
                continue
            for b in c if isinstance(c, list) else []:
                if isinstance(b, dict) and b.get('type') == 'tool_use' and b.get('name') in ('Edit', 'Write', 'MultiEdit'):
                    f = (b.get('input') or {}).get('file_path')
                    if f:
                        seen.setdefault(f, set()).add(os.path.basename(p)[:-6])
    return {f: sorted(a) for f, a in seen.items() if len(a) > 1}


def skills_outcome(files):
    import re, tzrework
    agg = {}
    for p in files:
        sk = set()
        for ln in open(p, errors='replace'):
            if '"Skill"' in ln:
                sk |= set(re.findall(r'"skill"\s*:\s*"([^"]+)"', ln))
        if sk:
            r = tzrework.analyse(p)
            for s in sk:
                agg.setdefault(s, []).append(r['rework_score'] if r else 0)
    return {s: (len(v), round(sum(v) / len(v))) for s, v in agg.items()}


def export(path, out):
    """Write one JSON line per usage total of a chat log to a LOCAL file (for Grafana/DuckDB/jq). No network. Returns the record."""
    import tzusage
    t = tzusage.totals(path)
    rec = {'schema': 'tz.export.v1', 'source': os.path.basename(path or ''), 'basis': 'MEASURED', 'turns': t['turns'],
           'input_tokens': t['inp'], 'output_tokens': t['out'], 'cache_read_tokens': t['cr'], 'cache_write_tokens': t['cw'],
           'cache_write_5m': t['w5'], 'cache_write_1h': t['w1h'], 'last_context_tokens': t['last']}
    with open(out, 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec) + '\n')
    return rec


def find_notes(root, words, ctx=1):
    """Task-level retrieval over handoff notes: [(file, line_no, line)] where ALL words appear (case-insensitive). Step 1 of 3: index lines; open the file for step 2/3."""
    ws = [w.lower() for w in words if w]
    out = []
    for f in sorted(glob.glob(os.path.join(root, '**', '*.md'), recursive=True), reverse=True):
        try:
            lines = open(f, encoding='utf-8', errors='ignore').read().splitlines()
        except OSError:
            continue
        for n, l in enumerate(lines, 1):
            if ws and all(w in l.lower() for w in ws):
                out.append((f, n, l.strip()[:160]))
    return out


def doctor():
    """One-screen health check, every line MEASURED from local files. Returns list of (status, text)."""
    st = os.path.expanduser('~/.claude/token-zombie')
    r = []
    r.append(('OK' if os.path.isfile(os.path.join(st, 'tz.db')) else 'WARN', 'tz.db ledger ' + ('present' if os.path.isfile(os.path.join(st, 'tz.db')) else 'missing (no savings recorded yet)')))
    try:
        led = json.load(open(os.path.join(st, 'ledger.json')))
        l, v, s = reconcile(led, os.path.join(st, 'tz.db'))
        r.append(('OK' if s in ('AGREE', 'EMPTY') else 'WARN', f'savings records: {s} (ledger {l:,} vs vault {v if v is None else format(v, ",")} tok)'))
    except Exception:
        r.append(('WARN', 'ledger.json unreadable or missing'))
    sj = os.path.expanduser('~/.claude/settings.json')
    try:
        hk = json.load(open(sj)).get('hooks', {})
        n = sum(1 for k in hk for g in hk[k] for h in g.get('hooks', []) if 'tz' in h.get('command', '') or 'token-zombie' in h.get('command', ''))
        r.append(('OK' if n else 'WARN', f'{n} TZ hook(s) registered in settings.json' + ('' if n else ' (plugin-delivered hooks are not checked here; else run install.sh)')))
    except Exception:
        r.append(('WARN', 'settings.json unreadable'))
    r.append(('OK' if os.path.isfile('CLAUDE.md') and 'TZ-MODEL-RULES' in open('CLAUDE.md', errors='ignore').read() else 'INFO', 'model rules block in CLAUDE.md: ' + ('yes' if os.path.isfile('CLAUDE.md') and 'TZ-MODEL-RULES' in open('CLAUDE.md', errors='ignore').read() else 'no (tz route --write --yes)')))
    return r


def main(argv):
    c, a = argv[0], argv[1:]
    state = os.path.expanduser('~/.claude/token-zombie')
    db = os.path.join(state, 'tz.db')
    if c == 'reconcile':
        try:
            led = json.load(open(os.path.join(state, 'ledger.json')))
        except Exception:
            led = []
        l, v, st = reconcile(led, db)
        print(f'savings reconcile [MEASURED]: ledger.json {l:,} tok vs vault {v if v is None else format(v, ",")} tok -> {st}')
        if st == 'MISMATCH':
            print('  the two records disagree by >10%: do not quote the dashboard figure until explained (some cuts are ledger-only or vault-only).')
        return 0
    if c == 'export':
        import tzusage
        src = a[0] if a else tzusage.find_transcript(os.getcwd())
        out = a[a.index('--out') + 1] if '--out' in a else 'tz-export.jsonl'
        r = export(src, out); print(f'appended 1 record ({r["turns"]} turns, MEASURED) to {os.path.abspath(out)}; local file, nothing sent anywhere')
        return 0
    if c == 'find':
        root = 'handoffs' if os.path.isdir('handoffs') else '.'
        r = find_notes(root, a)
        for f, n, l in r[:20]:
            print(f'  {f}:{n}  {l}')
        print(f'{len(r)} line(s) in handoff notes' + (' (first 20 shown)' if len(r) > 20 else '') + '; open the file for full context')
        return 0
    if c == 'doctor':
        for stt, tx in doctor():
            print(f'  [{stt}] {tx}')
        return 0
    if c == 'vault-find':
        r = vault_find(db, a)
        for i, t, tg, o, s in r:
            print(f'  {i}  {t:8} {str(tg)[:60]}  {o:,}->{s:,} chars   restore: tz recall {i}')
        print(f'{len(r)} spilled outputs match' if r else 'no spilled output matches')
        return 0
    if c == 'overlap':
        d = a[0] if a else ''
        fs = glob.glob(os.path.join(d, 'subagents', 'agent-*.jsonl')) if d else []
        r = overlap(fs)
        for f, ag in r.items():
            print(f'  OVERLAP {f}: edited by {", ".join(ag)}')
        print(f'{len(r)} files edited by 2+ agents ({len(fs)} agent logs) [MEASURED]')
        return 0
    if c == 'skills-outcome':
        d = a[0] if a else os.path.expanduser('~/.claude/projects')
        r = skills_outcome(glob.glob(os.path.join(d, '**', '*.jsonl'), recursive=True))
        for s, (n, sc) in sorted(r.items(), key=lambda x: -x[1][0])[:15]:
            print(f'  {s:32} chats {n:>3}  avg rework score {sc}/100')
        print('correlation only (a skill may be used on harder tasks); not proof a skill helps or hurts.')
        return 0
    print(__doc__); return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
