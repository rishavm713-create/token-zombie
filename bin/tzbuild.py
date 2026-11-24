#!/usr/bin/env python3
# tz 2.0 build helpers, all local and read-only unless noted:
#   tz reuse [REPO..]       licence audit (gh) of repos: reuse-with-credit | check | study-only
#   tz gaps [dir]           missing implementation pieces: TODO/stubs/unresolved local imports
#   tz missing [dir]        features promised in README/docs but not found in code
#   tz contract [dir]       frontend fetch() calls vs backend routes: mismatches
#   tz api [dir]            list HTTP routes found; --openapi prints a skeleton
#   tz dbschema [dir]       tables/columns from SQL and ORM models; flags foreign keys without index
#   tz coord post|list|claim|done ...   shared note board between sessions (file: ~/.claude/token-zombie/coord.json)
#   tz stack [idea|design|web|off]      turn on the skill packs an idea-to-product build needs (calls ~/.claude/skillpack)
import json, os, re, subprocess, sys, time

STATE = os.path.expanduser('~/.claude/token-zombie')
SKIP = {'.git', 'node_modules', '__pycache__', 'dist', 'build', '.venv', 'venv', '.next', 'handoffs'}
CODE = ('.py', '.js', '.jsx', '.ts', '.tsx', '.sh')
OK_LIC = {'mit', 'apache-2.0', 'bsd-2-clause', 'bsd-3-clause', 'isc', 'unlicense', '0bsd'}
CHATGPT = ('DietrichGebert/ponytail Yeachan-Heo/oh-my-claudecode affaan-m/everything-claude-code anthropics/claude-plugins-official '
           'cloudflare/security-audit-skill janestreet/agent_skills mattpocock/skills mksglu/context-mode morluto/rea '
           'nadimtuhin/claude-token-optimizer obra/superpowers pbakaus/impeccable pingdotgg/t3code rtk-ai/rtk ruvnet/ruflo '
           'thedotmack/claude-mem vercel-labs/agent-skills vercel-labs/skills').split()


def files(root, exts=CODE, limit=2000):
    out = []
    for d, ds, fs in os.walk(root):
        ds[:] = [x for x in ds if x not in SKIP]
        for f in fs:
            if f.endswith(exts):
                out.append(os.path.join(d, f))
        if len(out) >= limit:
            break
    return out[:limit]


def text(p):
    try:
        return open(p, errors='ignore').read()
    except OSError:
        return ''


def arg_dir(a):
    return os.path.abspath(next((x for x in a if not x.startswith('--')), '.'))


# ---- reuse -------------------------------------------------------------
def licence(repo):
    r = subprocess.run(['gh', 'repo', 'view', repo, '--json', 'licenseInfo', '-q', '.licenseInfo.key // "none"'], capture_output=True, text=True, timeout=30)
    return r.stdout.strip() if r.returncode == 0 else 'gone'


def verdict(lic):
    if lic in OK_LIC:
        return 'REUSE', 'code may be reused; keep the licence text and credit the author'
    if lic == 'gone':
        return 'GONE', 'repo not found'
    if lic == 'none':
        return 'STUDY', 'no licence = all rights reserved: read public docs and behaviour, write your own version, copy nothing'
    return 'CHECK', 'custom or copyleft licence: read it before using any code'


def reuse(a):
    repos = [x for x in a if not x.startswith('--')] or CHATGPT
    rows = []
    for r in repos:
        try:
            lic = licence(r)
        except (OSError, subprocess.TimeoutExpired):
            lic = 'gone'
        v, why = verdict(lic)
        rows.append((r, lic, v, why))
        print('%-8s %-42s %-12s %s' % (v, r, lic, why))
    try:
        os.makedirs(STATE, exist_ok=True)
        json.dump({r: dict(licence=l, verdict=v) for r, l, v, _ in rows}, open(os.path.join(STATE, 'reuse.json'), 'w'))
    except OSError:
        pass
    print('boundary: no decompiling or copying of proprietary code; behaviour from public docs, outputs and APIs only (clean-room).')
    return 0


# ---- gaps / missing ----------------------------------------------------
def gaps(a):
    root = arg_dir(a)
    todo = re.compile(r'\b(TODO|FIXME|XXX)\b|NotImplementedError|raise NotImplemented')
    n = 0
    mods = {os.path.splitext(os.path.basename(f))[0] for f in files(root)}
    for f in files(root):
        t = text(f)
        rel = os.path.relpath(f, root)
        for i, ln in enumerate(t.splitlines(), 1):
            if todo.search(ln):
                print('stub   %s:%d  %s' % (rel, i, ln.strip()[:80])); n += 1
        if f.endswith('.py'):
            for m in re.finditer(r'^\s*(?:from|import)\s+(tz\w+)', t, re.M):
                if m.group(1) not in mods:
                    print('import %s: %s has no file here' % (rel, m.group(1))); n += 1
        elif f.endswith(('.js', '.jsx', '.ts', '.tsx')):
            for m in re.finditer(r'''from\s+['"](\.{1,2}/[^'"]+)['"]''', t):
                p = os.path.normpath(os.path.join(os.path.dirname(f), m.group(1)))
                if not any(os.path.exists(p + e) for e in ('', '.js', '.jsx', '.ts', '.tsx', '/index.ts', '/index.js')):
                    print('import %s: %s not found' % (rel, m.group(1))); n += 1
    print('%d gap(s) [MEASURED by pattern: not a proof of completeness]' % n)
    return 1 if n else 0


def missing(a):
    root = arg_dir(a)
    docs = [os.path.join(root, x) for x in ('README.md', 'docs/FEATURES.md') if os.path.exists(os.path.join(root, x))]
    code = '\n'.join(text(f) for f in files(root))
    n = 0
    for d in docs:
        for ln in text(d).splitlines():
            m = re.search(r'`(?:tz )?([a-z][a-z0-9-]{2,})`', ln)
            if m and re.search(r'planned|todo|coming|not built|missing|roadmap', ln, re.I):
                print('promised-not-done %s: %s' % (os.path.basename(d), ln.strip()[:90])); n += 1
            elif m and m.group(1) not in code and ln.lstrip().startswith(('-', '*', '|')) and len(m.group(1)) > 4:
                print('named-not-in-code %s: %s' % (os.path.basename(d), m.group(1))); n += 1
    print('%d candidate(s) [pattern match: review by hand]' % n)
    return 0


# ---- contract / api / db ----------------------------------------------
ROUTE = [re.compile(p) for p in (
    r'@\w+\.(get|post|put|delete|patch|route)\(\s*[\'"]([^\'"]+)',
    r'\b(?:app|router)\.(get|post|put|delete|patch)\(\s*[\'"`]([^\'"`]+)')]
CALL = re.compile(r'''(?:fetch|axios\.(?:get|post|put|delete|patch))\(\s*[`'"]([^`'"]+)''')


def routes(root):
    out = []
    for f in files(root, ('.py', '.js', '.ts')):
        for ln in text(f).splitlines():
            for rx in ROUTE:
                m = rx.search(ln)
                if m:
                    out.append((m.group(1).upper(), m.group(2), os.path.relpath(f, root)))
    return out


def norm(p):
    p = re.sub(r'https?://[^/]+', '', p.split('?')[0])
    return re.sub(r'(\$\{[^}]*\}|<[^>]*>|:\w+|\{[^}]*\})', '*', p).rstrip('/') or '/'


def api(a):
    root = arg_dir(a)
    rs = routes(root)
    if '--openapi' in a:
        paths = {}
        for m, p, _ in rs:
            paths.setdefault(re.sub(r'<[^>]*>|:(\w+)', lambda x: '{%s}' % (x.group(1) or 'id'), p), {})[m.lower()] = {'responses': {'200': {'description': 'OK'}}}
        print(json.dumps({'openapi': '3.0.0', 'info': {'title': os.path.basename(root), 'version': '0.1'}, 'paths': paths}, indent=1)); return 0
    for m, p, f in rs:
        print('%-6s %-30s %s' % (m, p, f))
    print('%d route(s)' % len(rs)); return 0


def contract(a):
    root = arg_dir(a)
    have = {norm(p) for _, p, _ in routes(root)}
    bad = 0
    for f in files(root, ('.js', '.jsx', '.ts', '.tsx')):
        for m in CALL.finditer(text(f)):
            p = norm(m.group(1))
            if p.startswith('/') and p not in have and not any(re.fullmatch(h.replace('*', '[^/]+'), p) for h in have):
                print('no backend route for %s  (%s)' % (m.group(1), os.path.relpath(f, root))); bad += 1
    print('%d mismatch(es); %d backend route(s) known' % (bad, len(have)))
    return 1 if bad else 0


def dbschema(a):
    root = arg_dir(a)
    tabs = {}
    for f in files(root, ('.sql', '.py', '.ts', '.js', '.prisma')):
        t = text(f)
        for m in re.finditer(r'CREATE TABLE(?: IF NOT EXISTS)?\s+[`"\[]?(\w+)[`"\]]?\s*\((.*?)\);', t, re.S | re.I):
            cols = [c.strip().split()[0].strip('`"[]') for c in m.group(2).split(',\n') if c.strip() and not re.match(r'\s*(PRIMARY|FOREIGN|UNIQUE|CONSTRAINT|INDEX|KEY)', c, re.I)]
            tabs[m.group(1)] = dict(cols=cols, fks=re.findall(r'(\w+)\s+\w+[^,]*REFERENCES|FOREIGN KEY\s*\((\w+)', m.group(2), re.I), file=os.path.relpath(f, root))
        for m in re.finditer(r'^class (\w+)\((?:db\.Model|Base|models\.Model)\)', t, re.M):
            tabs.setdefault(m.group(1), dict(cols=re.findall(r'^\s{4}(\w+)\s*=\s*(?:db\.)?(?:Column|models\.)', t, re.M), fks=[], file=os.path.relpath(f, root)))
        for m in re.finditer(r'^model (\w+) \{(.*?)^\}', t, re.M | re.S):
            tabs.setdefault(m.group(1), dict(cols=re.findall(r'^\s+(\w+)\s+\w+', m.group(2), re.M), fks=[], file=os.path.relpath(f, root)))
    allsql = '\n'.join(text(f) for f in files(root, ('.sql',)))
    for n, d in sorted(tabs.items()):
        print('%s (%s): %s' % (n, d['file'], ', '.join(d['cols'][:12]) or '?'))
        for fk in d['fks']:
            c = next((x for x in fk if x), '')
            if c and not re.search(r'CREATE INDEX[^;]*\b%s\b' % c, allsql, re.I):
                print('  warn: foreign key %s has no index' % c)
    print('%d table(s) found' % len(tabs)); return 0


# ---- coord / stack -----------------------------------------------------
def coord(a):
    p = os.path.join(STATE, 'coord.json')
    try:
        b = json.load(open(p))
    except Exception:
        b = []
    op = a[0] if a else 'list'
    if op == 'post':
        b.append(dict(id=len(b) + 1, who=os.environ.get('CLAUDE_SESSION_ID', 'me')[:12], note=' '.join(a[1:]), status='open', t=int(time.time())))
    elif op in ('claim', 'done') and len(a) > 1 and a[1].isdigit():
        for x in b:
            if x['id'] == int(a[1]):
                if op == 'claim' and x['status'] != 'open':
                    print('refused: #%s is %s' % (a[1], x['status'])); return 3
                x['status'] = 'claimed' if op == 'claim' else 'done'
    elif op != 'list':
        print('usage: tz coord post TEXT | list | claim ID | done ID', file=sys.stderr); return 2
    os.makedirs(STATE, exist_ok=True)
    json.dump(b, open(p, 'w'))
    for x in b[-20:]:
        print('#%-3d %-8s %-12s %s' % (x['id'], x['status'], x['who'], x['note']))
    return 0


PACKS = {'idea': ['business', 'design', 'web', 'coding'], 'design': ['design'], 'web': ['web', 'seo']}


def stack(a):
    op = a[0] if a else 'idea'
    sp = os.path.expanduser('~/.claude/skillpack')
    if op == 'off':
        todo = [('off', p) for p in sorted({x for v in PACKS.values() for x in v})]
    elif op in PACKS:
        todo = [('on', p) for p in PACKS[op]]
    else:
        print('usage: tz stack idea|design|web|off', file=sys.stderr); return 2
    if not os.path.exists(sp):
        print('skillpack not found at %s (plan only): %s' % (sp, ', '.join('%s %s' % t for t in todo))); return 1
    for s, p in todo:
        r = subprocess.run([sp, s, p], capture_output=True, text=True)
        print('%s %s: %s' % (s, p, (r.stdout or r.stderr).strip().splitlines()[-1:] or 'ok'))
    print('idea -> product order: business (offer) > design (UI) > coding (build) > web (site, SEO). Turn off when done: tz stack off')
    return 0


CMDS = dict(reuse=reuse, gaps=gaps, missing=missing, contract=contract, api=api, dbschema=dbschema, coord=coord, stack=stack)


def main(argv):
    if argv and argv[0] in CMDS:
        return CMDS[argv[0]](argv[1:])
    print('usage: tz ' + '|'.join(CMDS), file=sys.stderr); return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
