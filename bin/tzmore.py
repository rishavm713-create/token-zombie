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
              and x.get('basis') == 'measured' and not str(x.get('kind', '')).startswith('overhead'))
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
