#!/usr/bin/env python3
# Output trim + recall. PostToolUse: a big Read/Grep/WebFetch/MCP result is cut before the model sees it
# (hookSpecificOutput.updatedToolOutput, same shape as the tool's own output; host keeps the original on a shape mismatch).
# The full text is kept locally: `tz recall <id> [--grep P] [--lines A-B]`. Bash: only stdout still > TZ_OUT_MAX after rtk.
# Independent implementation; idea seen in context-mode (ELv2), no code copied. Verified on claude 2.1.318 (Read, Glob).
import hashlib, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STATE = os.path.expanduser('~/.claude/token-zombie')
RECALL = os.path.join(STATE, 'recall')
READ_MAX = int(os.environ.get('TZ_OUT_READ_MAX', 20000))  # chars kept from a whole-file Read (~5k tok); host 2.1.318 itself cut a
# 6000-line file at ~34k chars, so a higher limit never fires
OTHER_MAX = int(os.environ.get('TZ_OUT_MAX', 12000))  # chars kept from Grep content / WebFetch / MCP text (~3k tok)
KEEP_FILES = 200
_last_rid = ['', 0]  # id of the most recent spill, for the vault index


def _conf():
    try:
        return json.load(open(os.path.join(STATE, 'config.json')))
    except Exception:
        return {}


def enabled():
    return os.environ.get('TZ_OUT', '1') != '0' and _conf().get('out_trim', True) is not False


def spill(text):
    rid = hashlib.sha1(text.encode('utf-8', 'replace')).hexdigest()[:10]
    os.makedirs(RECALL, mode=0o700, exist_ok=True)  # trimmed output can hold secrets (.env reads): owner-only
    os.chmod(RECALL, 0o700)
    p = os.path.join(RECALL, rid + '.txt')
    if not os.path.exists(p):
        with os.fdopen(os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w', encoding='utf-8') as fh:
            fh.write(text)
        old = sorted(os.listdir(RECALL), key=lambda f: os.path.getmtime(os.path.join(RECALL, f)))
        for f in old[:-KEEP_FILES]:
            os.remove(os.path.join(RECALL, f))
    return rid


def cut(text, limit, head_only):
    """Return (kept text, hidden chars) or None if under limit. Cuts on line edges."""
    if len(text) <= limit:
        return None
    rid = spill(text); _last_rid[0] = rid; _last_rid[1] = len(text)
    if not head_only:  # content-aware crush first: lossless via recall, keeps structure instead of cutting the middle
        try:
            import tzcrush
            new, kd = tzcrush.crush(text)
        except Exception:
            new = None
        if new is not None:
            mark = f'\n[TOKEN ZOMBIE crushed {kd}: {len(text) - len(new)} chars removed. Original: tz recall {rid} --grep PATTERN]'
            if len(new) + len(mark) <= limit:
                return new + mark, len(text) - len(new) - len(mark)
            text = new
    lines = text.split('\n')
    if head_only:  # Read: keep line numbers right, so only a head is kept
        keep, n = [], 0
        for ln in lines:
            if n + len(ln) + 1 > limit:
                break
            keep.append(ln); n += len(ln) + 1
        k = len(keep)
        mark = (f'[TOKEN ZOMBIE trimmed: lines {k + 1}-{len(lines)} ({len(text) - n} chars) not shown. '
                f'Need them? Read with offset={k + 1} limit=..., or run: tz recall {rid} --grep PATTERN]')
        return '\n'.join(keep + [mark]), len(text) - n - len(mark)
    head, tail, n = [], [], 0
    for ln in lines:
        if n + len(ln) + 1 > limit * 0.7:
            break
        head.append(ln); n += len(ln) + 1
    m = 0
    for ln in reversed(lines[len(head):]):
        if m + len(ln) + 1 > limit * 0.3:
            break
        tail.insert(0, ln); m += len(ln) + 1
    hid = len(lines) - len(head) - len(tail)
    mark = (f'[TOKEN ZOMBIE trimmed: {hid} middle lines ({len(text) - n - m} chars) not shown. '
            f'Full text: tz recall {rid} --grep PATTERN  (or --lines A-B)]')
    return '\n'.join(head + [mark] + tail), len(text) - n - m - len(mark)


def trim(d):
    """PostToolUse payload -> (hookSpecificOutput, saved chars) or (None, 0). Never raises."""
    try:
        if not enabled():
            return None, 0
        tool, ti, r = d.get('tool_name') or '', d.get('tool_input') or {}, d.get('tool_response')
        saved = 0
        if tool == 'Read':
            fp = str(ti.get('file_path') or '')
            if ti.get('offset') or ti.get('limit') or fp.startswith(RECALL) or not isinstance(r, dict):
                return None, 0
            f = r.get('file') if r.get('type') == 'text' else None
            if not isinstance(f, dict) or not isinstance(f.get('content'), str):
                return None, 0
            stub = _reread(d.get('session_id', 'x'), fp, f['content'])
            if stub:  # unchanged re-read: idea from lean-ctx (Apache-2.0), independent code
                saved = len(f['content']) - len(stub); f['content'] = stub
            else:
                c = cut(f['content'], READ_MAX, True)
                if not c:
                    return None, 0
                f['content'], saved = c
            if not stub:
                _mark_trimmed(d.get('session_id', 'x'), fp)
        elif tool == 'Grep' and isinstance(r, dict) and isinstance(r.get('content'), str):
            c = cut(r['content'], OTHER_MAX, False)
            if not c:
                return None, 0
            r['content'], saved = c
        elif tool == 'Bash' and isinstance(r, dict) and isinstance(r.get('stdout'), str):  # only what rtk left big
            for k in ('stdout', 'stderr'):  # long stderr (build logs) is cut the same way
                c = cut(r[k], OTHER_MAX, False) if isinstance(r.get(k), str) else None
                if c:
                    r[k] = c[0]; saved += c[1]
            if not saved:
                return None, 0
        elif tool == 'WebFetch' and isinstance(r, dict) and isinstance(r.get('result'), str):
            c = cut(r['result'], OTHER_MAX, False)
            if not c:
                return None, 0
            r['result'], saved = c
        elif tool.startswith('mcp__') or tool in ('Agent', 'Task'):  # subagent reports enter the chat whole: same cut
            blocks = r if isinstance(r, list) else (r.get('content') if isinstance(r, dict) else None)
            if isinstance(r, str):
                c = cut(r, OTHER_MAX, False)
                if not c:
                    return None, 0
                r, saved = c
            elif isinstance(blocks, list):
                for b in blocks:
                    if isinstance(b, dict) and b.get('type') == 'text' and isinstance(b.get('text'), str):
                        c = cut(b['text'], OTHER_MAX, False)
                        if c:
                            b['text'], s = c
                            saved += s
                if not saved:
                    return None, 0
            else:
                return None, 0
        else:
            return None, 0
        if saved <= 0:
            return None, 0
        shadow = _conf().get('out_trim') == 'shadow'
        _shadow_log('trim', tool, saved, 'shadow' if shadow else 'live')
        try:
            import tzdb
            tzdb.vault_add(_last_rid[0], d.get('session_id', 'x'), tool, ti.get('file_path') or ti.get('pattern') or ti.get('command') or ti.get('url') or '', _last_rid[1], max(0, _last_rid[1] - saved))
        except Exception:
            pass
        if shadow:  # canary: measure what would be cut, change nothing the model sees
            return None, 0
        return {'hookEventName': 'PostToolUse', 'updatedToolOutput': r}, saved
    except Exception:
        return None, 0


def _reread(session, fp, content):
    """Stub text if this session already got these exact bytes of fp in full (untrimmed) and no compaction since; else '' and remember."""
    if len(content) < 2000:
        return ''
    p = os.path.join(STATE, f'seen-{session}.json')
    h = hashlib.sha1(content.encode('utf-8', 'replace')).hexdigest()
    try:
        seen = json.load(open(p))
    except Exception:
        seen = {}
    if seen.get(fp) == h:
        return f'[TOKEN ZOMBIE: {fp} is unchanged since you read it earlier in this chat ({len(content)} chars); that result is still above. Re-read with offset/limit for a part, or Grep.]'
    if len(content) <= READ_MAX:  # only a full, untrimmed result counts as "already in context"
        seen[fp] = h
        json.dump(seen, open(p + '.tmp', 'w')); os.replace(p + '.tmp', p)
    return ''


def _mark_trimmed(session, fp):
    """The read guard must not call a trimmed Read 'already in context'."""
    p = os.path.join(STATE, f'reads-{session}.json')
    try:
        c = json.load(open(p))
    except Exception:
        return
    for k, v in c.items():
        if k.startswith(fp + '|'):
            v['trim'] = 1
    json.dump(c, open(p + '.tmp', 'w')); os.replace(p + '.tmp', p)


def _shadow_log(kind, tool, n, mode):
    try:
        os.makedirs(STATE, exist_ok=True)
        with open(os.path.join(STATE, 'shadow.jsonl'), 'a') as f:
            f.write(json.dumps(dict(t=int(time.time()), kind=kind, tool=tool, chars=int(n), mode=mode)) + '\n')
    except Exception:
        pass


def shadow_report(days=7):
    """`tz shadow`: what the trim rule did/would do, and how often the original was needed again (recall) = quality-risk proxy."""
    cut = time.time() - days * 86400; a = {}
    try:
        for ln in open(os.path.join(STATE, 'shadow.jsonl')):
            try:
                e = json.loads(ln)
            except Exception:
                continue
            if e.get('t', 0) >= cut:
                k = (e['kind'], e.get('mode', ''))
                v = a.setdefault(k, [0, 0]); v[0] += 1; v[1] += e.get('chars', 0)
    except OSError:
        pass
    tr = [(k, v) for k, v in a.items() if k[0] == 'trim']; rc = sum(v[0] for k, v in a.items() if k[0] == 'recall')
    if not tr and not rc:
        print(f'shadow ({days} d): no data. Set out_trim to "shadow" in {STATE}/config.json to measure a trim without applying it.'); return 0
    for (k, m), (n, c) in sorted(tr):
        print(f'trim [{m}] {n} cuts, {c:,} chars (~{c // 4:,} tok EST) {"would be saved" if m == "shadow" else "saved"}')
    n_tr = sum(v[0] for k, v in tr)
    print(f'originals re-read via tz recall: {rc}' + (f' = {100 * rc // max(1, n_tr)}% of cuts [MEASURED counts; high % = trim hides needed text, review before keeping it on]' if n_tr else ''))
    st, c, r = lifecycle()
    print(f'lifecycle stage: {st} ({c} cuts, {r} recalls). ACTIVE needs >=20 live cuts and recalls <=10% of cuts [advice only].')
    return 0


def lifecycle():
    """Shadow lifecycle stage of the output trim: RECORD (no data) > RECOMMEND (data, trim off) > SHADOW (measuring) > CANARY (live, recall rate high) > ACTIVE (live, recall rate low).
    Promotion is advice only; the owner changes out_trim in config.json."""
    mode = _conf().get('out_trim', 'off'); cuts = rc = 0
    try:
        for ln in open(os.path.join(STATE, 'shadow.jsonl')):
            try:
                e = json.loads(ln)
            except Exception:
                continue
            cuts += e.get('kind') == 'trim'; rc += e.get('kind') == 'recall'
    except OSError:
        pass
    if mode == 'shadow':
        st = 'SHADOW'
    elif mode in ('on', 'live', True):
        st = 'ACTIVE' if cuts >= 20 and rc * 10 <= cuts else 'CANARY'
    else:
        st = 'RECOMMEND' if cuts else 'RECORD'
    return st, cuts, rc


def memdir():
    # Windows: Claude Code turns ':' '\\' and every other non-alphanumeric into '-'
    slug = re.sub(r'[^A-Za-z0-9]', '-', os.getcwd()) if os.name == 'nt' else os.getcwd().replace('/', '-').replace('_', '-')
    return os.path.expanduser('~/.claude/projects/' + slug + '/memory')


def _src(rid):
    """id -> file: 10-hex spill file, h:<handoff>.md (./handoffs), m:<memory>.md (project memory dir). None if not found / unsafe."""
    if re.fullmatch(r'[0-9a-f]{10}', rid):
        return os.path.join(RECALL, rid + '.txt')
    m = re.fullmatch(r'([hm]):([\w.-]+\.md)', rid)
    if m:
        return os.path.join(os.path.join(os.getcwd(), 'handoffs') if m.group(1) == 'h' else memdir(), m.group(2))
    return None


def search(query, limit=8, handoffs='', memory=''):
    """`tz recall --search WORDS`: rank the spilled outputs with SQLite FTS5 (bm25), built in memory from the kept files [independent code]."""
    import sqlite3
    db = sqlite3.connect(':memory:')
    try:
        db.execute('create virtual table t using fts5(id unindexed, body)')
    except sqlite3.OperationalError:
        print('FTS5 not available in this Python: use --grep'); return 1
    for f in os.listdir(RECALL) if os.path.isdir(RECALL) else []:
        if re.fullmatch(r'[0-9a-f]{10}\.txt', f):
            db.execute('insert into t values (?,?)', (f[:10], open(os.path.join(RECALL, f), encoding='utf-8', errors='replace').read()))
    for f in (sorted(os.listdir(handoffs)) if handoffs and os.path.isdir(handoffs) else []):  # progressive retrieval: handoff notes as extra index (no new store)
        if f.endswith('.md'):
            db.execute('insert into t values (?,?)', ('h:' + f, open(os.path.join(handoffs, f), encoding='utf-8', errors='replace').read()))
    for f in (sorted(os.listdir(memory)) if memory and os.path.isdir(memory) else []):  # Claude-Mem style: memory notes, same index
        if f.endswith('.md') and f != 'MEMORY.md':
            db.execute('insert into t values (?,?)', ('m:' + f, open(os.path.join(memory, f), encoding='utf-8', errors='replace').read()))
    q = ' '.join('"' + w.replace('"', '') + '"' for w in query.split())
    if not q:
        print('usage: tz recall --search WORDS'); return 2
    rows = db.execute("select id, snippet(t,1,'[',']','...',12) from t where t match ? order by bm25(t) limit ?", (q, limit)).fetchall()
    for rid, sn in rows:
        print(f"{rid}: {' '.join(sn.split())[:200]}")
    if not rows:
        print('no match')
    return 0


def recall(argv):
    if argv[:1] == ['--search']:
        h, m = '--handoffs' in argv, '--memory' in argv
        return search(' '.join(w for w in argv[1:] if w not in ('--handoffs', '--memory')), handoffs=os.path.join(os.getcwd(), 'handoffs') if h else '',
                      memory=memdir() if m else '')
    rid = argv[0] if argv else ''
    p = _src(rid)
    if not p:
        print('usage: tz recall <id|h:file.md|m:file.md> [--grep PATTERN] [--lines A-B]  |  tz recall --search WORDS [--handoffs] [--memory]'); return 2
    if not os.path.exists(p):
        print(f'no recall {rid} (kept: last {KEEP_FILES})'); return 1
    _shadow_log('recall', rid[:12], 0, 'live')
    lines = open(p, encoding='utf-8').read().split('\n')
    if '--grep' in argv:
        pat = re.compile(argv[argv.index('--grep') + 1], re.I)
        for i, ln in enumerate(lines, 1):
            if pat.search(ln):
                print(f'{i}: {ln[:300]}')
    elif '--lines' in argv:
        a, _, b = argv[argv.index('--lines') + 1].partition('-')
        for i in range(max(1, int(a)), min(len(lines), int(b or a)) + 1):
            print(f'{i}: {lines[i - 1]}')
    else:
        print('\n'.join(lines))
    return 0


def main(argv):
    """`tz recall <id> ...` (bin/tz passes the args after 'recall'); `tzout.py hook < payload` for tests/probes."""
    if argv[:1] == ['shadow']:
        return shadow_report()
    if argv[:1] == ['recall']:
        argv = argv[1:]
    if argv[:1] == ['hook']:
        d = json.load(sys.stdin)
        out, saved = trim(d)
        if out:
            try:  # standalone hook path; tz-guard writes its own single entry
                from tzopt import ledger
                ledger('output-trim', saved, 'measured', d.get('session_id', 'x'), 'trim ' + (d.get('tool_name') or ''))
            except Exception:
                pass
            print(json.dumps({'hookSpecificOutput': out}))
        return 0
    return recall(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
