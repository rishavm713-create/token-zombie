#!/usr/bin/env python3
# Four small advice-only tools, all MEASURED from local files, no network, no model calls:
#  tz reconcile            ledger.json savings vs tz.db vault (orig-shown chars/4): do the two records agree?
#  tz vault-find WORDS..   spilled outputs whose tool/target match the words (task-level retrieval; restore with `tz recall ID`)
#  tz overlap [SESSION_DIR] files edited by 2+ subagents of one session (conflict risk)
#  tz skills-outcome [DIR]  per skill: chats it ran in and their average rework score (tzrework); correlation, not proof of effect
import glob, json, os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def reconcile(ledger, db):
    """(ledger_tok, vault_tok, status). Only ledger rows from the vault's first row onward are compared (the vault may start later than the ledger). Tolerance 10%."""
    try:
        c = sqlite3.connect(db)
        v, t0 = c.execute('SELECT COALESCE(SUM(orig-shown),0), MIN(t) FROM vault').fetchone()
        c.close(); v = (v or 0) // 4
    except Exception:
        return 0, None, 'UNAVAILABLE (no vault db)'
    led = sum(x['tok'] for x in ledger if isinstance(x, dict) and isinstance(x.get('tok'), (int, float))
              and x.get('basis') == 'measured' and x.get('kind') == 'output-trim'  # rtk rows are RTK's own savings; overhead rows are costs
              and (t0 is None or not isinstance(x.get('t'), (int, float)) or x['t'] >= t0 - 5))
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


def otlp(rec, preview=False):
    """OTLP/JSON metrics payload (resourceMetrics) from one export record. Counters only, no prompt content, no file paths."""
    t = int(__import__('time').time() * 1e9)
    def g(name, v):
        return {'name': name, 'unit': '{token}', 'sum': {'aggregationTemporality': 2, 'isMonotonic': True,
                'dataPoints': [{'asInt': str(int(v)), 'timeUnixNano': str(t), 'attributes': [{'key': 'tz.basis', 'value': {'stringValue': rec.get('basis', 'MEASURED')}}]}]}}
    ms = [g('tz.' + k, rec[k]) for k in ('input_tokens', 'output_tokens', 'cache_read_tokens', 'cache_write_tokens')]
    return {'resourceMetrics': [{'resource': {'attributes': [{'key': 'service.name', 'value': {'stringValue': 'token-zombie'}}]},
            'scopeMetrics': [{'scope': {'name': 'tz.export.v1'}, 'metrics': ms}]}]}


WORKFLOWS = {
    'plan': ['State the goal and acceptance check in 2 lines.', 'List files to read (grep first, no whole-file reads).', 'Write the smallest plan; name what is out of scope.', 'CHECKPOINT: user approves the plan before any edit.'],
    'build': ['One step at a time; smallest complete change; reuse existing code.', 'After each step run the single relevant check.', 'CHECKPOINT: tz handoff if the chat passes ~100k tokens.'],
    'test': ['Add one real test for new logic.', 'Run it; loop until it passes; never weaken the test.', 'Run the full suite once at the end (background if > 2 min).'],
    'review': ['Read the diff only, not whole files.', 'List correctness and security findings, most severe first.', 'CHECKPOINT: user decides which findings to fix.'],
}


def workflow(name=None):
    """Checklist text for plan|build|test|review (or all). Advice only; nothing runs and no agent is spawned."""
    names = [name] if name in WORKFLOWS else list(WORKFLOWS)
    return '\n'.join(f'{n}:\n' + '\n'.join(f'  {i}. {x}' for i, x in enumerate(WORKFLOWS[n], 1)) for n in names)


def worktree_cmd(task, base='HEAD'):
    """The git command that isolates one task/agent in its own worktree+branch (never run by TZ)."""
    slug = ''.join(ch if ch.isalnum() else '-' for ch in task.lower()).strip('-')[:40] or 'task'
    return f'git worktree add ../{slug} -b tz/{slug} {base}'


# Real worktrees (P0 item 3): one worktree+branch per task, plus a file-ownership map in the tz state dir.
# A file owned by one live task is refused to any other task; `remove` releases. Fail-open: no git -> ownership only.
def _slug(task):
    return ''.join(ch if ch.isalnum() else '-' for ch in task.lower()).strip('-')[:40] or 'task'


def _own(state, fn):
    """Run fn(map) under an exclusive lock on worktrees.json; saves the map fn leaves behind."""
    import fcntl
    os.makedirs(state, exist_ok=True)
    p = os.path.join(state, 'worktrees.json')
    with open(p + '.lock', 'w') as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            m = json.load(open(p))
        except Exception:
            m = {}
        for k in [k for k, v in m.items() if v.get('path') and not os.path.isdir(v['path'])]:
            del m[k]  # worktree gone outside TZ: the task is no longer live, its files are free
        r = fn(m)
        tmp = p + '.tmp'; json.dump(m, open(tmp, 'w'), indent=1); os.replace(tmp, p)
        return r


def _conflicts(m, slug, files):
    return [(f, k) for f in files for k, v in m.items() if k != slug and f in v.get('files', [])]


def _norm(files):
    return sorted({os.path.normpath(f) for f in files if f})


def wt_claim(state, task, files):
    """(ok, msg). Adds files to the task's ownership; refuses all of them if any is owned by another live task."""
    slug, files = _slug(task), _norm(files)
    def go(m):
        if slug not in m:
            return False, f'no live task {slug}; run: tz worktree add {slug}'
        c = _conflicts(m, slug, files)
        if c:
            return False, 'refused: ' + ', '.join(f'{f} owned by {k}' for f, k in c)
        m[slug]['files'] = sorted(set(m[slug]['files']) | set(files))
        return True, f'{slug} owns {len(m[slug]["files"])} file(s)'
    return _own(state, go)


def wt_add(state, task, files=(), base='HEAD', repo='.'):
    """(ok, msg). Claims files first (refused on overlap), then `git worktree add`; without git, ownership only."""
    import shutil, subprocess
    slug, files = _slug(task), _norm(files)
    repo = os.path.abspath(repo)
    path = os.path.join(os.path.dirname(repo), slug)
    def go(m):
        if slug in m:
            return False, f'task {slug} is already live at {m[slug].get("path") or "(no worktree)"}'
        c = _conflicts(m, slug, files)
        if c:
            return False, 'refused: ' + ', '.join(f'{f} owned by {k}' for f, k in c)
        note = ''
        if not shutil.which('git'):
            p, note = None, ' (git missing: ownership only, no worktree)'
        else:
            r = subprocess.run(['git', '-C', repo, 'worktree', 'add', path, '-b', f'tz/{slug}', base], capture_output=True, text=True)
            p = path if r.returncode == 0 else None
            if p is None:
                note = f' (git worktree failed: {(r.stderr or r.stdout).strip()[:200]}; ownership only)'
        m[slug] = dict(path=p, branch=f'tz/{slug}' if p else None, repo=repo, files=files)
        return True, f'{slug}: {p or "no worktree"}, owns {len(files)} file(s){note}'
    return _own(state, go)


def wt_remove(state, task, force=False):
    """(ok, msg). Removes the worktree (branch kept) and releases its files. A dirty worktree is kept unless force."""
    import shutil, subprocess
    slug = _slug(task)
    def go(m):
        v = m.get(slug)
        if not v:
            return False, f'no live task {slug}'
        if v.get('path') and shutil.which('git'):
            r = subprocess.run(['git', '-C', v['repo'], 'worktree', 'remove'] + (['--force'] if force else []) + [v['path']], capture_output=True, text=True)
            if r.returncode and os.path.isdir(v['path']):
                return False, f'kept {slug}: {(r.stderr or r.stdout).strip()[:200]} (commit, or --force)'
        del m[slug]
        return True, f'removed {slug}; released {len(v.get("files", []))} file(s); branch {v.get("branch") or "-"} kept'
    return _own(state, go)


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
        if '--otlp' in a:  # opt-in: write OTLP/JSON to a LOCAL file; --preview prints it and writes nothing
            import tzusage, tempfile
            tmp = tempfile.mktemp(); rec = export(src, tmp); os.unlink(tmp)
            pl = otlp(rec)
            if '--preview' in a:
                print(json.dumps(pl, indent=1)); print('preview only: counters, no prompts, no paths; nothing written or sent'); return 0
            open(a[a.index('--otlp') + 1], 'w').write(json.dumps(pl)); print('wrote OTLP/JSON locally; sending it anywhere is your step (curl to your collector)'); return 0
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
    if c == 'workflow':
        print(workflow(a[0] if a else None)); return 0
    if c == 'worktree' and a and a[0] in ('add', 'claim', 'remove', 'list'):
        v, r = a[0], a[1:]
        if v == 'list':
            m = _own(state, lambda m: dict(m))
            for k, x in m.items():
                print(f'  {k}  {x.get("path") or "(no worktree)"}  files: {", ".join(x["files"]) or "-"}')
            print(f'{len(m)} live task(s)'); return 0
        if not r:
            print(f'usage: tz worktree {v} TASK ...'); return 2
        opt = lambda k, d=None: r[r.index(k) + 1] if k in r and r.index(k) + 1 < len(r) else d
        if v == 'add':
            ok, msg = wt_add(state, r[0], (opt('--files') or '').split(','), opt('--base', 'HEAD'))
        elif v == 'claim':
            ok, msg = wt_claim(state, r[0], r[1:])
        else:
            ok, msg = wt_remove(state, r[0], '--force' in r)
        print(msg); return 0 if ok else 1
    if c == 'worktree':
        cmd = worktree_cmd(' '.join(a) or 'task')
        print(f'isolate this task so parallel agents never touch the same files:\n  {cmd}\nrun it yourself (TZ does not create worktrees); remove later: git worktree remove ../<dir>')
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
