#!/usr/bin/env python3
# Compounding learnings loop: capture one verified lesson, update instead of duplicate, recall it, check it against the tree,
# merge review findings, and (opt-in) nudge after a check goes from fail to pass. check_frontmatter, check_claims and merge are
# adapted from EveryInc/compound-engineering-plugin skills/ce-compound/scripts/validate-{frontmatter,doc-claims}.py and
# skills/ce-code-review/scripts/findings-mechanics.py (MIT, Copyright (c) 2025 Every), see NOTICE.
import collections, datetime, glob, hashlib, json, os, re, subprocess, sys

COMMANDS = ('capture', 'recall', 'check', 'review')
MAX_DOC = 1536
HEADS = ('Symptom', 'Cause', 'Fix', 'Detect')


def git(repo, *args, timeout=10):
    """(exit code, stdout) of one git call; (1, '') when git cannot run."""
    try:
        r = subprocess.run(['git', '-C', repo, *args], capture_output=True, text=True, errors='replace', timeout=timeout)
        return r.returncode, r.stdout
    except (OSError, subprocess.TimeoutExpired):
        return 1, ''


def top(cwd):
    """Repository root, or cwd outside git."""
    code, out = git(cwd, 'rev-parse', '--show-toplevel')
    return out.strip() if code == 0 and out.strip() else cwd


def read(path):
    """File text, '' when unreadable."""
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            return f.read()
    except OSError:
        return ''


def inside(path, base):
    """True when path resolves to somewhere strictly below base."""
    return os.path.realpath(path).startswith(os.path.realpath(base) + os.sep)


def solutions(repo):
    """<docs_root>/solutions; docs_root comes from .compound-engineering/config.yaml (default docs) and must stay in the repo."""
    m = re.search(r'^docs_root:[ \t]*([^#\n]*)', read(os.path.join(repo, '.compound-engineering', 'config.yaml')), re.M)
    val = m.group(1).strip().strip('"\'') if m else ''
    root = os.path.join(repo, val or 'docs')
    rel = os.path.relpath(os.path.realpath(root), os.path.realpath(repo))
    # WHY no fallback to docs: silently writing somewhere else than configured splits the store.
    if os.path.isabs(val) or not inside(root, repo) or rel.split(os.sep)[0] == '.git':
        raise ValueError(f'docs_root {val!r} must be a directory inside the repository (not the root or .git)')
    out = os.path.join(root, 'solutions')
    if not inside(out, repo):
        raise ValueError(f'{out} resolves outside the repository')
    return out


def docs(repo):
    """All learning files, nested categories included."""
    d = solutions(repo)
    return sorted(p for p in glob.glob(os.path.join(glob.escape(d), '**', '*.md'), recursive=True) if inside(p, repo))


def terms(text):
    """Lowercase word set used for overlap and recall."""
    stop = {'the', 'and', 'for', 'with', 'that', 'this', 'from', 'was', 'are', 'not', 'when', 'but'}
    return {w for w in re.findall(r'[a-z0-9_]{3,}', text.lower()) if w not in stop}


def section(text, head):
    """Body of one '## head' section."""
    m = re.search(rf'^## {head}[ \t]*\n(.*?)(?=^## |\Z)', text, re.M | re.S)
    return m.group(1).strip() if m else ''


def title_of(text, path):
    """Frontmatter title, else first heading, else file name."""
    m = re.search(r'^title:[ \t]*(.+)$', text, re.M) or re.search(r'^# (.+)$', text, re.M)
    return m.group(1).strip().strip('"\'') if m else os.path.basename(path)[:-3]


def recall(repo, query, n=3):
    """[(score, relative path, title)] learnings matching the query; title and tags count double."""
    q, hits = terms(query), []
    for p in docs(repo):
        t = read(p)
        head = title_of(t, p) + ' ' + ' '.join(re.findall(r'^(?:tags|module):.*$', t, re.M))
        s = 2 * len(q & terms(head)) + len(q & terms(t))
        if s:
            hits.append((s, os.path.relpath(p, repo), title_of(t, p)))
    return sorted(hits, key=lambda h: (-h[0], h[1]))[:n]


def existing(repo, slug, title, symptom):
    """The learning that already covers this lesson: same slug, or half of the title+symptom words shared."""
    new, best = terms(title + ' ' + symptom), (0.0, None)
    for p in docs(repo):
        if os.path.basename(p) == slug + '.md':
            return p
        t = read(p)
        old = terms(title_of(t, p) + ' ' + (section(t, 'Symptom') or section(t, 'Symptoms') or section(t, 'Problem')))
        score = len(new & old) / len(new | old) if new | old else 0.0
        if score > best[0]:
            best = (score, p)
    return best[1] if best[0] >= 0.5 else None


def render(f, today):
    """New learning document; the title is JSON-quoted so YAML cannot truncate it."""
    fm = ['---', 'title: ' + json.dumps(f['title'], ensure_ascii=False), 'date: ' + today]
    if f.get('module'):
        fm.append('module: ' + json.dumps(f['module'], ensure_ascii=False))
    body = ''.join(f'\n## {h}\n{f[h.lower()]}\n' for h in HEADS if f.get(h.lower()))
    return '\n'.join(fm) + f"\n---\n\n# {f['title']}\n" + body


def merge_doc(old, f, today):
    """Replace only the sections supplied now; other text and frontmatter survive."""
    for h in HEADS:
        v = f.get(h.lower())
        if not v:
            continue
        pat = re.compile(rf'^## {h}[ \t]*\n.*?(?=^## |\Z)', re.M | re.S)
        block = f'## {h}\n{v}\n\n'
        old = pat.sub(lambda _: block, old, 1) if pat.search(old) else old.rstrip('\n') + '\n\n' + block
    old = re.sub(r'^last_updated:.*\n', '', old, flags=re.M)
    old = re.sub(r'\A---\n(.*?\n)---\n', lambda m: f'---\n{m.group(1)}last_updated: {today}\n---\n', old, 1, re.S)
    return old.rstrip('\n') + '\n'


def capture(repo, f, diff_lines=None, apply=False, today=None):
    """(status, path, text or reason). status: skipped | manual | create | update. Writes only when apply."""
    f = {k: str(v).strip() for k, v in f.items() if v}
    f['title'] = ' '.join(f.get('title', '').split())
    missing = [k for k in ('title', 'symptom', 'cause', 'fix') if not f.get(k)]
    if missing:
        return 'skipped', None, 'not durable: missing ' + ', '.join(missing) + ' (capture only a solved problem with a found root cause)'
    if diff_lines is not None and diff_lines < 3:
        return 'skipped', None, 'not durable: the fix is under 3 changed lines'
    today = today or datetime.date.today().isoformat()
    text = render(f, today)
    if len(text.encode()) > MAX_DOC:
        return 'skipped', None, f'too long ({len(text.encode())} B, limit {MAX_DOC} B): tighten it'
    slug = re.sub(r'[^a-z0-9]+', '-', f['title'].lower()).strip('-')[:60].strip('-')
    if not slug:
        return 'skipped', None, 'title needs at least one ASCII letter or digit'
    old = existing(repo, slug, f['title'], f['symptom'])
    path = old or os.path.join(solutions(repo), slug + '.md')
    if not inside(path, repo):
        return 'skipped', None, 'target resolves outside the repository'
    if old:
        prev = read(old)
        # WHY manual: appending our sections to a differently shaped doc would leave the wrong old text beside the new.
        if not section(prev, 'Cause'):
            return 'manual', old, 'an existing learning covers this: edit it by hand, do not add a second one'
        text = merge_doc(prev, f, today)
    if apply:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
    return ('update' if old else 'create'), path, text


def check_frontmatter(text):
    """Parser-safety issues: unclosed frontmatter, unquoted ' #' or ': ' in top-level scalars."""
    lines = text.split('\n')
    if lines[0].rstrip() != '---':
        return ["file does not start with '---' frontmatter delimiter line"]
    end = next((i for i in range(1, len(lines)) if lines[i].rstrip() == '---'), None)
    if end is None:
        return ["frontmatter not closed (no '---' line after the opening delimiter)"]
    out = []
    for no, line in enumerate(lines[1:end], 2):
        if ':' not in line or line.startswith((' ', '\t', '#', '- ')):
            continue
        key, _, val = line.partition(':')
        val = val.strip()
        if not val or val[0] in '"\'[{|>':
            continue
        if re.search(r'\s#', val):
            out.append(f"line {no}: '{key.strip()}' value contains ' #': quote it (YAML drops the rest)")
        if re.search(r':\s', val):
            out.append(f"line {no}: '{key.strip()}' value contains ': ': quote it (read as a nested mapping)")
    return out


def _mask(body):
    """Blank fenced and inline code so quoted syntax is not read as a link or leftover placeholder."""
    out, fence = [], None
    for line in body.split('\n'):
        m = re.match(r'\s*(`{3,}|~{3,})(.*)$', line)
        if fence is None and m:
            fence, line = m.group(1), ''
        elif fence is not None:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not m.group(2).strip():
                fence = None
            line = ''
        out.append(re.sub(r'`[^`\n]+`', '', line))
    return '\n'.join(out)


def _path_flag(repo, doc_dir, raw):
    """Flag text for one backticked token that cites a missing file or a line past its end, else None."""
    cited = raw.strip().rstrip('.,;')
    ref = re.search(r':(\d+)(?:-(\d+))?$', cited)
    tok = cited[:ref.start()] if ref else cited
    tok = tok[2:] if tok.startswith('./') else tok
    if os.path.isabs(tok) and inside(tok, repo):
        tok = os.path.relpath(os.path.realpath(tok), os.path.realpath(repo))
    if ('/' not in tok or re.search(r'[\s<>{}*$]|\.\.\.|…|path/to|://', tok)
            or tok.startswith(('http', '#', '/', '~', 'origin/', 'upstream/', 'refs/'))):
        return None
    if tok.startswith('../') or '/../' in tok:
        tok = os.path.relpath(os.path.realpath(os.path.join(doc_dir, tok)), os.path.realpath(repo))
        if tok.startswith('..'):
            return None
    full = os.path.join(repo, tok)
    if os.path.exists(full):
        if ref and os.path.isfile(full):
            end, total = int(ref.group(2) or ref.group(1)), len(read(full).splitlines())
            if end > total:
                return f'line `{cited}`: {tok} has {total} line(s), stale line number'
        return None
    if git(repo, 'cat-file', '-e', 'HEAD:' + tok)[0] == 0:
        return f'path `{tok}`: tracked at HEAD but missing from the working tree'
    # WHY path-shaped only: branch names and model ids also contain slashes.
    if re.search(r'\.[A-Za-z0-9]{1,8}$|/$', tok) or os.path.isdir(os.path.join(repo, tok.split('/')[0])):
        return f'path `{tok}`: not found in the repository'
    return None


def check_claims(repo, doc):
    """Flags for body citations that no longer match the tree (paths, lines, commits, links, leftover placeholders)."""
    body = re.sub(r'\A---\n.*?\n---[ \t]*\n', '', read(doc), count=1, flags=re.S)
    here, flags = os.path.dirname(os.path.abspath(doc)), []
    for raw in dict.fromkeys(re.findall(r'`([^`\n]+)`', body)):
        f = _path_flag(repo, here, raw)
        if f:
            flags.append(f)
    if git(repo, 'rev-parse', '--git-dir')[0] == 0:
        cue = r'\b(?:commit(?:ted|s)?|revert(?:ed|s)?|cherry-pick(?:ed)?|(?:fixed|landed|introduced|merged) (?:in|by))\s+`?([0-9a-f]{7,40})\b'
        for sha in dict.fromkeys(re.findall(cue, body, re.I)):
            if git(repo, 'cat-file', '-e', sha + '^{commit}')[0]:
                flags.append(f'sha {sha}: does not resolve to a commit here')
    prose = _mask(body)
    for target in dict.fromkeys(re.findall(r'\[[^\]]*\]\(([^)\s]+)\)', prose)):
        bare = target.split('#')[0]
        if bare and not re.match(r'[a-z][a-z0-9+.-]*:', target, re.I) and not os.path.exists(os.path.join(here, bare)):
            flags.append(f'link ({target}): relative target does not resolve')
    for m in re.finditer(r'\bLearnings?\s+#?\d|\{\{[^}\n]*\}\}', prose):
        flags.append(f'scaffold "{m.group(0)}": drafting reference left in the doc')
    return flags


SEV = ('P0', 'P1', 'P2', 'P3')
AUTOFIX = ('gated_auto', 'manual', 'advisory')  # later = more cautious
OWNERS = ('downstream-resolver', 'human', 'release')
NEED = {'title': str, 'severity': str, 'file': str, 'line': (int, str), 'confidence': int, 'autofix_class': str,
        'owner': str, 'requires_verification': bool, 'pre_existing': bool}


def _text(v):
    return isinstance(v, str) and bool(v.strip())


def _valid(f):
    """Schema check for one finding; bools are not integers here."""
    if not isinstance(f, dict) or not all(isinstance(f.get(k), t) for k, t in NEED.items()):
        return False
    if type(f['confidence']) is not int or ('first_evidence' in f and not _text(f['first_evidence'])):
        return False
    line_ok = (type(f['line']) is int and f['line'] > 0) or _text(f['line'])
    return (line_ok and f['severity'] in SEV and f['confidence'] in (0, 25, 50, 75, 100)
            and f['autofix_class'] in AUTOFIX and f['owner'] in OWNERS)


def _combine(group):
    """Merge exact duplicates conservatively; only a verified cross-model peer raises confidence."""
    group.sort(key=lambda g: (SEV.index(g[0]['severity']), -g[0]['confidence']))
    m, names, indep = dict(group[0][0]), [], []
    m['pre_existing'] = all(g[0]['pre_existing'] for g in group)
    for f, reviewer, mine in group:
        sup = f.get('reviewers')
        names += [n for n in (sup if isinstance(sup, list) else [reviewer]) if isinstance(n, str) and n not in names]
        indep += mine
        m['autofix_class'] = max(m['autofix_class'], f['autofix_class'], key=AUTOFIX.index)
        m['owner'] = max(m['owner'], f['owner'], key=OWNERS.index)
        m['requires_verification'] = m['requires_verification'] or f['requires_verification']
        for k in ('first_evidence', 'suggested_fix', 'settled_conflict'):
            if not m.get(k) and f.get(k):
                m[k] = f[k]
    conf, proof = max(g[0]['confidence'] for g in group), _text(m.get('first_evidence'))
    if conf >= 75 and not proof:
        conf = 50
    if proof and len(set(indep)) >= 2 and any(n.startswith('adversarial-') for n in indep):
        conf = {50: 75, 75: 100}.get(conf, conf)
    m.update(confidence=conf, reviewers=names, independent_reviewers=[n for n in names if n in indep])
    return m


def _independent(source, f):
    """Reviewer names that count as independent readings for one finding."""
    name = source['reviewer']
    if name == 'synthesis':
        have, ind = f.get('reviewers'), f.get('independent_reviewers')
        have = [n for n in have if isinstance(n, str)] if isinstance(have, list) else []
        return [n for n in ind if n in have] if isinstance(ind, list) else []
    if name == 'fast-pass' or (name.startswith('adversarial-') and source.get('independence_verified') is not True):
        return []
    return [name]


def merge(payload):
    """Validate, dedup (file+line+title), gate by confidence, sort and number a list of reviewer returns."""
    if not isinstance(payload, list):
        raise ValueError('expected an array of reviewer returns')
    out = {'status': 'complete', 'findings': [], 'suppressed_findings': [], 'pre_existing_findings': [], 'residual_risks': [],
           'testing_gaps': [], 'malformed_returns': 0, 'malformed_findings': 0, 'first_evidence_backfilled': 0}
    groups, shape = {}, {'reviewer': str, 'findings': list, 'residual_risks': list, 'testing_gaps': list}
    for src in payload:
        if not isinstance(src, dict) or not all(isinstance(src.get(k), t) for k, t in shape.items()):
            out['malformed_returns'] += 1
            continue
        out['residual_risks'] += src['residual_risks']
        out['testing_gaps'] += src['testing_gaps']
        for f in src['findings']:
            filled = 0
            if isinstance(f, dict):
                f = dict(f)
                ev, fe = f.get('evidence'), f.get('first_evidence', '')
                if (f.get('confidence') in (75, 100) and isinstance(fe, str) and not fe.strip()
                        and isinstance(ev, list) and ev and _text(ev[0])):
                    f['first_evidence'], filled = ev[0], 1
            if not _valid(f):
                out['malformed_findings'] += 1
                continue
            out['first_evidence_backfilled'] += filled
            if src['reviewer'] == 'fast-pass':
                f['confidence'] = min(f['confidence'], 50)
            key = (f['file'].strip().lower(), str(f['line']).strip(), ' '.join(f['title'].lower().split()))
            groups.setdefault(key, []).append((f, src['reviewer'], _independent(src, f)))
    low = collections.Counter()
    for f in map(_combine, groups.values()):
        if f['pre_existing']:
            out['pre_existing_findings'].append(f)
        elif f['confidence'] < 75 and f['severity'] != 'P0' and not f.get('settled_conflict'):
            low[str(f['confidence'])] += 1
            out['suppressed_findings'].append(f)
        else:
            out['findings'].append(f)
    for k in ('findings', 'suppressed_findings'):
        out[k].sort(key=lambda f: (SEV.index(f['severity']), -f['confidence'], f['file'].lower(), str(f['line']), f['title'].lower()))
    for n, f in enumerate(out['findings'], 1):
        f['#'] = n
    out['suppressed_by_confidence'] = dict(sorted(low.items()))
    return out


CHECK_CMD = re.compile(r'(?:^|&&)\s*(?:\w+=\S*\s+)*(?:(?:python3?|uv run|poetry run|npx|bash|sh)\s+(?:-m\s+)?)?'
                       r'(?:pytest|unittest|jest|vitest|tsc|eslint|ruff|mypy|pyright|go (?:test|vet)|cargo (?:test|clippy)|'
                       r'(?:npm|pnpm|yarn|bun)(?: run)? (?:test|lint|build|typecheck)|make (?:test|check)|tz gate|'
                       r'\S*(?:test_\w+\.(?:py|sh)|run_all\.sh))(?![\w-])')


def _changes(repo, base):
    """Counter of hashed changed lines since commit `base`, untracked files included."""
    c = collections.Counter()
    code, diff = git(repo, 'diff', '-U0', '--no-ext-diff', '--no-color', base, '--', timeout=2)
    if code:
        return None
    lines = [l for l in diff.split('\n') if l[:1] in ('+', '-') and not l.startswith(('+++ ', '--- '))]
    for rel in git(repo, 'ls-files', '-o', '--exclude-standard', timeout=2)[1].split('\n')[:50]:
        p = os.path.join(repo, rel)
        if rel and os.path.isfile(p) and not os.path.islink(p) and os.path.getsize(p) < 100000:
            lines += ['+' + l for l in read(p).split('\n') if l]
    for l in lines[:5000]:
        c[hashlib.sha1(l.encode('utf-8', 'replace')).hexdigest()[:10]] += 1
    return c


def observe(data):
    """Hook helper (PostToolUse / PostToolUseFailure): one advice line when a failed check passes after a code change."""
    from tzlib import feature
    cmd = str((data.get('tool_input') or {}).get('command') or '').strip()
    if data.get('tool_name') != 'Bash' or not feature('learn_loop') or not CHECK_CMD.search(cmd):
        return None
    r = data.get('tool_response') if isinstance(data.get('tool_response'), dict) else {}
    failed = data.get('hook_event_name') == 'PostToolUseFailure' or bool(r.get('is_error'))
    if r.get('interrupted') or data.get('is_interrupt'):
        return None
    # WHY: with a pipe or ';' the exit status belongs to the last command, so a "pass" proves nothing.
    if not failed and (re.search(r'[|;\n]', cmd) or (data.get('tool_input') or {}).get('run_in_background')):
        return None
    repo = top(data.get('cwd') or os.getcwd())
    sid = re.sub(r'[^A-Za-z0-9_-]', '_', str(data.get('session_id', 'x')))[:60]
    state = os.path.join(os.path.expanduser('~'), '.claude', 'token-zombie', f'learn-{sid}.json')
    try:
        st = json.loads(read(state) or '{}')
    except ValueError:
        st = {}
    key = hashlib.sha1((repo + '\0' + ' '.join(cmd.split())).encode()).hexdigest()[:16]
    msg = None
    if failed:
        if key in st:  # keep the first failure so the fix is measured across every retry
            return None
        base = git(repo, 'rev-parse', 'HEAD', timeout=2)[1].strip()
        seen = _changes(repo, base) if base else None
        if seen is None:
            return None
        st[key] = {'base': base, 'seen': seen}
    else:
        was = st.pop(key, None)
        now = _changes(repo, was['base']) if was else None
        if now is None:
            return None
        before = collections.Counter(was['seen'])
        n = sum(((now - before) + (before - now)).values())
        if n >= 3:  # under 3 lines (typo, flaky rerun) is not worth a record
            msg = (f'TOKEN ZOMBIE learn: a failing check now passes ({n} changed lines [actual]). Only if the cause is not '
                   'visible from code/tests/docs and could recur: prefer a test or lint rule, else '
                   '`tz learn capture --title T --symptom S --cause C --fix F --apply`.')
    os.makedirs(os.path.dirname(state), exist_ok=True)
    with open(state, 'w') as f:
        json.dump(st, f)
    return msg


def _opt(argv, name):
    i = argv.index(name) if name in argv else -1
    return argv[i + 1] if 0 <= i < len(argv) - 1 else None


def _cli_capture(repo, argv):
    fields = {k: _opt(argv, '--' + k) for k in ('title', 'module', 'symptom', 'cause', 'fix', 'detect')}
    n = _opt(argv, '--diff-lines')
    status, path, text = capture(repo, fields, int(n) if n else None, '--apply' in argv)
    if status == 'skipped':
        print('Documentation skipped: ' + text)
    elif status == 'manual':
        print(f'{text}: {path}')
    elif '--apply' in argv:
        print(f'{status}d {path}')
    else:
        print(f'Dry run ({status} {path}). Add --apply to write:\n{text}')
    return 0


def _cli_check(repo, paths):
    """Report only: stale learnings are flagged for a human or agent to fix; nothing is edited or deleted."""
    paths, bad = paths or docs(repo), 0
    for p in paths:
        if not os.path.isfile(p):
            print(f'{p}: file not found'); return 2
        flags = check_frontmatter(read(p)) + check_claims(repo, p)
        bad += bool(flags)
        for f in flags:
            print(f'FLAG {os.path.relpath(p, repo)}: {f}')
    print(f'tz learn check [actual]: {len(paths)} doc(s), {bad} need review')
    return 1 if bad else 0


def main(argv):
    """tz learn capture|recall|check|review."""
    if not argv or argv[0] not in COMMANDS:
        print('usage: tz learn capture --title T --symptom S --cause C --fix F [--detect D] [--module M] [--diff-lines N] [--apply]\n'
              '       tz learn recall WORDS... | check [DOC...] | review [RETURNS.json]', file=sys.stderr)
        return 2
    cmd, rest = argv[0], argv[1:]
    try:
        if cmd == 'review':
            raw = read(rest[0]) if rest else sys.stdin.read()
            print(json.dumps(merge(json.loads(raw)), sort_keys=True)); return 0
        repo = top(os.getcwd())
        if cmd == 'capture':
            return _cli_capture(repo, rest)
        if cmd == 'check':
            return _cli_check(repo, [os.path.abspath(p) for p in rest])
        hits = recall(repo, ' '.join(rest))
        print('\n'.join(f'{p}: {t}' for _, p, t in hits) or 'tz learn recall: no matching learning')
        return 0
    except (ValueError, OSError) as e:
        print(f'tz learn {cmd}: {e}', file=sys.stderr); return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
