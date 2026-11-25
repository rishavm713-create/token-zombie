#!/usr/bin/env python3
"""tz obs: session observations recorded from hook events by fixed rules (no model call, no network), recalled in three steps:
search (compact index) -> timeline (neighbours) -> get (full detail). Rows live in the tz ledger (tz.db).
strip_tags / normalize_title / exact_title_match / content_hash adapted from claude-mem src/utils/tag-stripping.ts,
src/services/dedup/normalize.ts, src/services/sqlite/observations/store.ts (Apache-2.0, Copyright 2026 Alex Newman), see NOTICE.
Changed: ported to stdlib Python; recording, recall and injection are own code following claude-mem behaviour."""
import fnmatch, hashlib, json, os, re, sys, time, unicodedata

import tzdb, tzfit, tzgate, tzmem
from tzlib import feature

TYPES = ('decision', 'bugfix', 'feature', 'refactor', 'discovery', 'change')
SCHEMA = '''
CREATE TABLE IF NOT EXISTS obs(id INTEGER PRIMARY KEY, project TEXT, sid TEXT, agent TEXT, type TEXT, title TEXT, narrative TEXT,
 facts TEXT, files TEXT, prompt_n INT, t INT, t_last INT, hash TEXT, key TEXT, n INT DEFAULT 1);
CREATE INDEX IF NOT EXISTS obs_t ON obs(project, t, id);
CREATE INDEX IF NOT EXISTS obs_key ON obs(project, key);
CREATE TABLE IF NOT EXISTS obs_sess(sid TEXT PRIMARY KEY, project TEXT, first TEXT, request TEXT, kind TEXT, prompt_n INT, private INT, shown TEXT);
'''
COLS = 'id, project, sid, agent, type, title, narrative, facts, files, prompt_n, t, t_last, n'
SCAN = 3000            # newest rows ranked per search
CTX_CAP, CTX_ROWS = 2000, 50
FILE_MIN_BYTES, FILE_SHOW, FILE_LOOKAHEAD = 1500, 5, 40
EDITS = ('Edit', 'Write', 'MultiEdit', 'NotebookEdit')


# ---------- privacy ----------
TAGS = ('private', 'claude-mem-context', 'system_instruction', 'system-instruction', 'persisted-output', 'system-reminder')
_TAG = re.compile(r'<(/?)([A-Za-z_][A-Za-z0-9_-]*)')
_CLOSE_END = re.compile(r'\s*>')
EXTRA_SECRETS = [r'-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(-----END [A-Z ]*PRIVATE KEY-----|$)',
                 r'sk-[A-Za-z0-9_\-]{16,}', r'github_pat_[A-Za-z0-9_]{20,}', r'eyJ[\w\-]{10,}\.[\w\-]{10,}\.[\w\-]+',
                 r'(?i)bearer\s+[\w.\-+/=]{8,}', r'(?<=://)[^/\s:@]+:[^/\s@]+(?=@)',
                 r'(?i)[\w\-]*(password|passwd|secret|token|api[_-]?key|access[_-]?key)[\w\-]*["\']?\s*[:=]\s*("[^"]*"|\'[^\']*\'|[^\s"\';&|]+)',
                 r'(?i)--?(password|token|secret|api-?key)\s+[^\s;&|]+']


def strip_tags(text):
    """Remove <private> (and injected-context) blocks, nested or not; an unclosed <private> drops the rest."""
    if '<' not in text:
        return text.strip()
    opens, cut = {}, []
    for m in _TAG.finditer(text):
        closing, name = m.group(1), m.group(2)
        if name not in TAGS:
            continue
        if closing:
            end = _CLOSE_END.match(text, m.end())
            q = opens.get(name)
            if end and q and m.start() >= q[0][1]:
                cut.append((q.pop(0)[0], end.end()))
        else:
            gt = text.find('>', m.end())
            opens.setdefault(name, []).append((m.start(), gt if gt >= 0 else len(text)))
    # WHY stricter than upstream: a forgotten </private> must not leak what the user meant to hide
    cut += [(s, len(text)) for s, _ in opens.get('private', [])]
    out, at = [], 0
    for s, e in sorted(cut):
        if s > at:
            out.append(text[at:s])
        at = max(at, e)
    return (''.join(out) + text[at:]).strip()


def redact(text):
    """Replace credential-looking strings; tzgate's patterns plus unquoted and URL forms."""
    for pat in EXTRA_SECRETS + [p for p, _ in tzgate.SECRETS]:
        text = re.sub(pat, '<redacted>', text)
    return text


def clean(text, n=200):
    """Private blocks out, secrets out, one line, then cut (cutting first could leave half a secret unmatched)."""
    return ' '.join(redact(strip_tags(str(text or ''))).split())[:n]


# ---------- duplicate identity ----------
def _word(ch):
    return unicodedata.category(ch)[0] in 'LNM'


def normalize_title(s):
    """NFC lowercase, punctuation to space; '' when no letter or digit is left (never merge on that)."""
    s = unicodedata.normalize('NFC', s or '').lower()
    s = ' '.join(''.join(c if _word(c) or c.isspace() else ' ' for c in s).split())
    return s if any(unicodedata.category(c)[0] in 'LN' for c in s) else ''


def _identifiers(s):
    s = unicodedata.normalize('NFC', s or '').lower().strip()
    s = re.sub(r'^__([\s\S]*\s[\s\S]*)__$', r'\1', s)
    toks = ''.join(c if _word(c) or c in '._/\\:@#=<>+~-' else ' ' for c in s).split()
    out = []
    for t in toks:
        if not re.search(r'^\.+$|[/\\]\.+$', t):
            t = t.rstrip('.')
        colon = any(_word(m.group(1)) and _word(m.group(2)) for m in re.finditer(r'(?=([^:]):+([^:]))', t))
        symbol = re.search(r'[._@#=<>+~]', t) or colon or re.match(r'^[a-z]:$', t)
        if re.match(r'^\.+$', t) or re.search(r'[/\\]', t) or (symbol and any(unicodedata.category(c)[0] in 'LN' for c in t)):
            out.append(t)
    return out


def exact_title_match(a, b):
    """Same prose AND same code identifiers/paths (C++ is not C, src/a-b is not src/a b)."""
    n = normalize_title(a)
    return bool(n) and n == normalize_title(b) and _identifiers(a) == _identifiers(b)


def content_hash(sid, title, narrative):
    f = [sid or '', title or '', narrative or '']
    if any('\0' in x for x in f):
        return 'tuple-' + hashlib.sha256(json.dumps(f, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    return hashlib.sha256('\0'.join(f).encode()).hexdigest()[:16]


# ---------- store ----------
def _run(fn, write=False):
    """fn(connection) on the ledger; None on any DB problem (a hook is never blocked)."""
    def f(c):
        c.executescript(SCHEMA)
        if write:
            c.execute('BEGIN IMMEDIATE')  # parallel hooks: dedup lookup and insert must not interleave
        return fn(c)
    return tzdb._w(f)


def _rows(sql, args=()):
    names = COLS.split(', ')
    got = _run(lambda c: c.execute(f'SELECT {COLS} FROM obs {sql}', args).fetchall()) or []
    out = [dict(zip(names, r)) for r in got]
    for r in out:
        r['facts'], r['files'] = json.loads(r['facts'] or '[]'), json.loads(r['files'] or '[]')
    return out


def _union(a, b, cap):
    return list(dict.fromkeys(list(a) + list(b)))[:cap]


def add(project, sid, type_, title, narrative='', facts=(), files=(), agent='main', prompt_n=0, now=None):
    """Store one observation; a repeat in the same session bumps the old row. Returns its id, None if refused."""
    title = (title or '').strip()
    if not title or type_ not in TYPES:
        return None
    now = int(now or time.time())
    norm = normalize_title(title)
    # session is part of the key: rule-made titles ("Changed x.py") repeat across sessions and those are separate history
    key = hashlib.sha256('\0'.join((project, sid, agent, type_, norm)).encode()).hexdigest()[:32] if norm else ''
    h = content_hash(sid, title, narrative)

    def fn(c):
        q = 'SELECT id, title, narrative, facts, files FROM obs WHERE project=? AND '
        if key:
            cand = c.execute(q + 'key=? ORDER BY id', (project, key)).fetchall()
            old = next((r for r in cand if exact_title_match(r[1], title)), None)
        else:
            old = c.execute(q + 'hash=? AND sid=? AND type=?', (project, h, sid, type_)).fetchone()
        if old:
            text = '\n'.join(_union((old[2] or '').split('\n'), narrative.split('\n'), 20)).strip()[:600]
            c.execute('UPDATE obs SET n=n+1, t_last=?, narrative=?, facts=?, files=? WHERE id=?',
                      (now, text, json.dumps(_union(json.loads(old[3]), facts, 8)), json.dumps(_union(json.loads(old[4]), files, 20)), old[0]))
            return old[0]
        return c.execute('INSERT INTO obs(project,sid,agent,type,title,narrative,facts,files,prompt_n,t,t_last,hash,key) '
                         'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', (project, sid, agent, type_, title, narrative, json.dumps(list(facts)[:8]),
                         json.dumps(list(files)[:20]), prompt_n, now, now, h, key)).lastrowid
    return _run(fn, write=True)


def forget(ids):
    def fn(c):
        n = sum(c.execute('DELETE FROM obs WHERE id=?', (i,)).rowcount for i in ids)
        c.execute('DELETE FROM obs_sess WHERE sid NOT IN (SELECT sid FROM obs)')  # the stored request goes with its last row
        return n
    return _run(fn, write=True) or 0


# ---------- capture ----------
def locate(cwd):
    """(project, checkout top). Walks up to .git without running git; a linked worktree belongs to its main project."""
    cwd = os.path.abspath(cwd or os.getcwd())
    d = cwd
    while True:
        g = os.path.join(d, '.git')
        if os.path.exists(g):
            if os.path.isfile(g):
                m = re.match(r'gitdir:\s*(.+?)/\.git/worktrees/', open(g, errors='ignore').read())
                if m:
                    return m.group(1), d
            return d, d
        up = os.path.dirname(d)
        if up == d:
            return cwd, cwd
        d = up


def _rel(path, top):
    r = os.path.relpath(path, top) if os.path.isabs(path) else path
    if r.startswith('..'):
        home = os.path.expanduser('~')
        return '~' + path[len(home):] if path.startswith(home + os.sep) else path
    return r.replace(os.sep, '/')


def _csv(name):
    return [x.strip().lower() for x in os.environ.get(name, '').split(',') if x.strip()]


def skipped(data, project):
    """True when user settings exclude this event (tool, project glob, subagent, command regex)."""
    if (data.get('tool_name') or '').lower() in _csv('TZ_OBS_SKIP_TOOLS'):
        return True
    if any(fnmatch.fnmatch(project.lower(), g) for g in _csv('TZ_OBS_EXCLUDE')):
        return True
    if data.get('agent_id') and (os.environ.get('TZ_OBS_SKIP_SUBAGENTS') == '1'
                                 or str(data.get('agent_type') or '').lower() in _csv('TZ_OBS_SKIP_AGENT_TYPES')):
        return True
    pat, cmd = os.environ.get('TZ_OBS_SKIP_BASH'), (data.get('tool_input') or {}).get('command')
    try:
        return bool(pat and cmd and re.search(pat, cmd))
    except re.error:
        return True  # a broken exclusion pattern must not start recording what the user meant to hide


KINDS = (('bugfix', r'\b(fix|bug|broken|crash|error|fail\w*|regression)\b'), ('refactor', r'\b(refactor|clean ?up|simplif\w+|rename|restructure)\b'),
         ('feature', r'\b(add|implement|build|create|support|new feature|integrate)\b'))


def classify(text):
    low = text.lower()
    return next((k for k, p in KINDS if re.search(p, low)), 'change')


def _session(sid):
    r = _run(lambda c: c.execute('SELECT first, request, kind, prompt_n, private, shown FROM obs_sess WHERE sid=?', (sid,)).fetchone())
    return dict(zip(('first', 'request', 'kind', 'prompt_n', 'private', 'shown'), r or ('', '', 'change', 0, 0, '[]')))


def on_prompt(data):
    """Remember the redacted request and its kind; a fully private prompt switches recording off for that turn."""
    sid, raw = data.get('session_id') or 'x', str(data.get('prompt') or '')
    project = locate(data.get('cwd'))[0]
    req = clean(raw)
    s = _session(sid)
    private = int(not req and '<private' in raw)
    row = (sid, project, s['first'] or req, req, classify(req), s['prompt_n'] + 1, private, s['shown'])
    _run(lambda c: c.execute('INSERT OR REPLACE INTO obs_sess VALUES(?,?,?,?,?,?,?,?)', row), write=True)


SYMBOL = re.compile(r'^[ \t]*(?:export\s+)?(?:default\s+)?(?:async\s+)?(def|class|function|fn|func|interface)\s+([A-Za-z_]\w*)', re.M)
TEST_RE = re.compile(r'(^|&&|;)\s*((\w+=\S+|rtk|uv run|npx|bash|sh|python[\d.]*( -m)?)\s+)*'  # runner in command position, not "grep pytest"
                     r'((\S*/)?(pytest|unittest|jest|vitest|run_all\.sh|test_\w+\.py)|(npm|pnpm|yarn|bun|cargo|go|make)\s+(run\s+)?test)\b')
COMMIT_OUT = re.compile(r'^\[[^\]\n]*?\b([0-9a-f]{7,40})\] (.+)$', re.M)


def _secret_file(path):
    b = os.path.basename(path).lower()
    return b.startswith('.env') or b.endswith(('.pem', '.key', '.keystore', '.kdbx')) or b in ('.npmrc', '.pypirc', '.netrc', '.git-credentials', 'id_rsa', 'id_ed25519')


def _command(cmd):
    first = next((x for x in strip_tags(cmd).splitlines() if x.strip()), '')
    return clean(re.sub(r'^\s*cd\s+\S+\s*(&&|;)\s*', '', first), 100)


def _error_line(data):
    """The line that names the failure: last one mentioning an error, else the last line."""
    text = str(data.get('error') or data.get('tool_response') or '')
    lines = [x for x in strip_tags(text).splitlines() if x.strip()]
    hit = [x for x in lines if re.search(r'(?i)error|fail|exception|denied|not found', x)]
    return clean((hit or lines or [''])[-1])


def derive(data, top):
    """[(type or None, title, detail, facts, files)] from one tool event; None type = use the request's kind. Most calls give []."""
    tool, inp = data.get('tool_name') or '', data.get('tool_input') or {}
    failed = data.get('hook_event_name') == 'PostToolUseFailure'
    if tool in EDITS:
        path = inp.get('file_path') or inp.get('notebook_path')
        if failed or not path:
            return []
        rel = _rel(path, top)
        new = '\n'.join(str(e.get('new_string') or '') for e in inp.get('edits') or [] if isinstance(e, dict))
        new += str(inp.get('new_string') or inp.get('content') or inp.get('new_source') or '')
        facts = [] if _secret_file(path) else [clean(f'{k} {n}', 80) for k, n in SYMBOL.findall(strip_tags(new))]
        return [(None, f'Changed {rel}', '', _union(facts, [], 8), [rel])]
    if tool != 'Bash' or not inp.get('command'):
        return []
    cmd = _command(str(inp['command']))
    if not cmd:
        return []
    if failed:
        return [] if data.get('is_interrupt') else [('discovery', f'Failed: {cmd}', _error_line(data), [], [])]
    out, resp = [], data.get('tool_response')
    stdout = str(resp.get('stdout') or '') if isinstance(resp, dict) else str(resp or '')
    if re.search(r'\bgit\b.*\bcommit\b', str(inp['command'])):
        for sha, subject in COMMIT_OUT.findall(stdout):
            s = clean(subject, 120)
            kind = {'fix': 'bugfix', 'feat': 'feature', 'refactor': 'refactor'}.get(re.split(r'[(:!]', s)[0].lower(), 'change')
            out.append((kind, f'Commit: {s}', f'commit {sha[:7]}', [], []))
    if TEST_RE.search(cmd) and '|' not in cmd:  # a pipe reports the last command's exit, not the tests'
        out.append(('discovery', f'Test command succeeded: {cmd}', '', [], []))
    return out


def observe(data):
    """Record what one PostToolUse / PostToolUseFailure event shows. Returns the stored ids."""
    project, top = locate(data.get('cwd'))
    found = derive(data, top)
    if not found or skipped(data, project):  # most tool calls record nothing: no database access for them
        return []
    sid = data.get('session_id') or 'x'
    s = _session(sid)
    if s['private']:
        return []
    ids = []
    for type_, title, detail, facts, files in found:
        note = '\n'.join(x for x in (detail, f"Request: {s['request']}" if s['request'] else '') if x)
        i = add(project, sid, type_ or s['kind'], title, note, facts, files, 'subagent' if data.get('agent_id') else 'main', s['prompt_n'])
        if i:
            ids.append(i)
    return ids


# ---------- recall: index -> timeline -> detail ----------
def _detail(r):
    seen = f" (x{r['n']}, last {_when(r['t_last'])})" if r['n'] > 1 else ''
    out = [f"#{r['id']} {_when(r['t'])} {r['type']}: {r['title']}{seen}", f"session {r['sid'][:8]} {r['agent']} prompt {r['prompt_n']} | {r['project']}"]
    out += [r['narrative']] if r['narrative'] else []
    out += ['facts: ' + '; '.join(r['facts'])] if r['facts'] else []
    out += ['files: ' + ', '.join(r['files'])] if r['files'] else []
    return '\n'.join(out)


def _when(t):
    return time.strftime('%m-%d %H:%M', time.localtime(t))


def line(r):
    """One index row; the ~Nt figure is the estimated cost of opening it (chars/4)."""
    times = f" (x{r['n']})" if r['n'] > 1 else ''
    return f"#{r['id']} {_when(r['t'])} {r['type']:9} {r['title'][:90]}{times} ~{len(_detail(r)) // 4}t"


def search(q='', project=None, type_=None, since=0, k=10):
    """Matching rows, best first (newest first when q is empty); project None = every project."""
    where, args = ['t_last >= ?'], [since]
    if project:
        where.append('project=?'); args.append(project)
    if type_:
        where.append('type=?'); args.append(type_)
    rows = _rows(f"WHERE {' AND '.join(where)} ORDER BY t DESC, id DESC LIMIT {SCAN}", args)
    k = max(1, min(k, 100))
    if not q.strip():
        return rows[:k]
    docs = [(r, 0, 0, ' '.join([r['title'], r['narrative'] or '', r['type']] + r['facts'] + r['files'])) for r in rows]
    return [d[0] for _, d in tzmem._bm25(docs, q)[:k]]


def get(ids):
    ids = [int(i) for i in ids][:100]
    return _rows(f"WHERE id IN ({','.join('?' * len(ids))}) ORDER BY t, id", ids) if ids else []


def timeline(anchor, before=3, after=3):
    """Rows around one id in its project, oldest first; (t, id) order keeps ties from over- or under-counting."""
    a = get([anchor])
    if not a:
        return []
    a = a[0]
    p = (a['project'], a['t'], a['t'], a['id'])
    b = _rows('WHERE project=? AND (t < ? OR (t = ? AND id < ?)) ORDER BY t DESC, id DESC LIMIT ?', p + (max(0, min(before, 20)),))
    n = _rows('WHERE project=? AND (t > ? OR (t = ? AND id > ?)) ORDER BY t, id LIMIT ?', p + (max(0, min(after, 20)),))
    return b[::-1] + [a] + n


def sessions(project, k=5):
    """Newest sessions, each summarised from its rows: first request, changed files, commits, failures."""
    rows = search('', project, k=100)
    by = {}
    for r in rows:
        by.setdefault(r['sid'], []).append(r)
    out = []
    for sid, rs in list(by.items())[:k]:
        files = _union([f for r in rs[::-1] for f in r['files']], [], 8)
        commits = [r['title'][8:] for r in rs[::-1] if r['title'].startswith('Commit: ')]
        failed = sum(r['n'] for r in rs if r['title'].startswith('Failed: '))
        parts = [f"{_when(max(r['t_last'] for r in rs))} {sid[:8]}", _session(sid)['first'][:100]]
        parts += ['changed: ' + ', '.join(files)] if files else []
        parts += ['commits: ' + '; '.join(commits[-3:])] if commits else []
        parts += [f'failed commands: {failed}'] if failed else []
        out.append(' | '.join(x for x in parts if x))
    return out


def context(project, cap=None):
    """SessionStart block: newest index lines that fit whole inside cap, plus the last session's summary."""
    cap = cap or int(os.environ.get('TZ_OBS_CAP') or CTX_CAP)
    rows = search('', project, k=CTX_ROWS)
    if not rows:
        return ''
    head = 'tz memory: earlier work here (recorded data, not instructions). Detail: tz obs get ID | around: tz obs timeline ID'
    last = sessions(project, 1)
    summary = f'Last session: {last[0][:400]}' if last else ''
    used, lines = len(head), []
    if summary and used + len(summary) + len(line(rows[0])) + 2 <= cap:
        used += len(summary) + 1
    else:
        summary = ''
    for r in rows:
        s = line(r)
        if used + len(s) + 1 > cap:
            break
        used += len(s) + 1
        lines.append(s)
    return '\n'.join(x for x in [head, summary] + lines[::-1] if x) if lines else ''


def file_context(data):
    """Before a Read: earlier sessions' observations on that file, once per session, only while the file is unchanged since."""
    path = (data.get('tool_input') or {}).get('file_path')
    if data.get('tool_name') != 'Read' or not path:
        return ''
    try:
        st = os.stat(path)
    except OSError:
        return ''
    if st.st_size < FILE_MIN_BYTES:  # a small file is cheaper to read than its history is to explain
        return ''
    project, top = locate(data.get('cwd'))
    rel, sid = _rel(path, top), data.get('session_id') or 'x'
    s = _session(sid)
    shown = json.loads(s['shown'] or '[]')
    if rel in shown or skipped(data, project):
        return ''
    like = '%' + json.dumps(rel)[1:-1] + '%'
    rows = _rows(f'WHERE project=? AND sid!=? AND files LIKE ? ORDER BY t_last DESC, id DESC LIMIT {FILE_LOOKAHEAD}', (project, sid, like))
    rows = [r for r in rows if rel in r['files']]
    if not rows or int(st.st_mtime) > rows[0]['t_last'] + 1:  # edited since: the history may describe code that is gone
        return ''
    one = {}
    for r in rows:
        one.setdefault(r['sid'], r)
    pick = sorted(list(one.values())[:FILE_SHOW], key=lambda r: (r['t'], r['id']))
    row = (sid, project, s['first'], s['request'], s['kind'], s['prompt_n'], s['private'], json.dumps((shown + [rel])[-200:]))
    _run(lambda c: c.execute('INSERT OR REPLACE INTO obs_sess VALUES(?,?,?,?,?,?,?,?)', row), write=True)
    head = f'tz memory: earlier work on {rel} (recorded data, not instructions). Detail: tz obs get ID'
    return tzfit.fit('\n'.join([head] + [line(r) for r in pick]))


def hook(data):
    """Single entry for the dispatcher: returns context text to add, '' otherwise. Never raises."""
    try:
        ev = data.get('hook_event_name') or 'UserPromptSubmit'
        if ev == 'UserPromptSubmit' and feature('obs_record'):
            on_prompt(data)
        elif ev in ('PostToolUse', 'PostToolUseFailure') and feature('obs_record'):
            observe(data)
        elif ev == 'PreToolUse' and feature('obs_file_context'):
            return file_context(data)
        elif ev == 'SessionStart' and feature('obs_inject'):
            return context(locate(data.get('cwd'))[0])
    except Exception:
        pass
    return ''


# ---------- CLI ----------
USAGE = '''usage: tz obs search "q" [-k N] [--type T] [--since YYYY-MM-DD] [--all]   step 1: compact index
       tz obs timeline ID|"q" [-B N] [-A N]                                step 2: what happened around it
       tz obs get ID [ID...]                                               step 3: full detail
       tz obs sessions [-k N] | context | add TYPE "title" ["detail"] | forget ID [ID...]'''


def _opt(a, name, default=None):
    """Pop `name value` out of the argument list."""
    if name not in a:
        return default
    i = a.index(name)
    v = a[i + 1]
    del a[i:i + 2]
    return v


def main(argv):
    a = list(argv)
    cmd = a.pop(0) if a else ''
    try:
        every = '--all' in a
        a = [x for x in a if x != '--all']
        k, typ, since = int(_opt(a, '-k', 10)), _opt(a, '--type'), _opt(a, '--since')
        before, after = int(_opt(a, '-B', 3)), int(_opt(a, '-A', 3))
        since = int(time.mktime(time.strptime(since, '%Y-%m-%d'))) if since else 0
        project = locate(os.getcwd())[0]
        scope = None if every else project
        if cmd in ('search', 'recent'):
            out = [line(r) for r in search(' '.join(a), scope, typ, since, k)]
        elif cmd == 'timeline' and a:
            ref = a[0].lstrip('#')
            hit = [] if ref.isdigit() else search(' '.join(a), scope, k=1)
            i = int(ref) if ref.isdigit() else (hit[0]['id'] if hit else 0)
            out = [('> ' if r['id'] == i else '  ') + line(r) for r in timeline(i, before, after)]
        elif cmd == 'get' and a:
            out, used, left = [], 0, []
            for r in get([x.lstrip('#') for x in a]):
                d = _detail(r)
                if out and used + len(d) > tzfit.CAP:
                    left.append(str(r['id']))
                    continue
                out.append(d + '\n'); used += len(d)
            out += [f"not shown (output cap): tz obs get {' '.join(left)}"] if left else []
        elif cmd == 'sessions':
            out = sessions(project, k)
        elif cmd == 'context':
            out = [x for x in [context(project)] if x]
        elif cmd == 'add' and len(a) >= 2:
            i = add(project, 'manual', a[0], clean(a[1], 160), clean(a[2], 600) if len(a) > 2 else '')
            if not i:
                print(f"not stored: type must be one of {', '.join(TYPES)} and the title non-blank"); return 2
            out = [f'stored #{i}']
        elif cmd == 'forget' and a:
            out = [f'deleted {forget([int(x.lstrip("#")) for x in a])} observation(s)']
        else:
            print(USAGE); return 2
    except (ValueError, IndexError):
        print(USAGE); return 2
    if not out:
        print('no observations match (recording needs the obs_record feature on)'); return 1
    print('\n'.join(out))
    if cmd in ('search', 'recent'):
        print('~Nt = tokens to open a row [est]. detail: tz obs get ID | around: tz obs timeline ID')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
