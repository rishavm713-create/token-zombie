#!/usr/bin/env python3
# tz skills check DIR: lint agent skills for token cost and progressive disclosure. Read-only; runs nothing from the skill.
# Capability prompted by vercel-labs/agent-skills (no LICENSE file): original stdlib code, nothing copied.
#   tz skills check DIR [--json] [--strict]    DIR = one skill or a tree of skills; exit 1 on errors (--strict: on warnings too)
# Three cost tiers, all [est] chars/4: listed (name+description, every chat) | load (SKILL.md body, per invocation) |
# on demand (other .md files, only if opened).
import fnmatch, json, os, re, sys

LONG = 250        # chars; same threshold tzstartup uses to advise shortening
DESC_MAX = 1024   # published Agent Skills limit
NAME_MAX = 64     # published Agent Skills limit
BODY_LINES = 500  # published guidance for SKILL.md body
REF_BYTES = 8192  # TZ choice: above this, opening a reference costs ~2k tokens
SKIP_DIRS = {'.git', 'node_modules', '__pycache__'}
HUMAN = {'readme.md', 'license.md', 'changelog.md', 'contributing.md', 'notice.md'}  # for people; agents need no link to them
BULK = {'agents.md', 'claude.md'}  # compiled all-in-one docs
TRIGGER = re.compile(r'\b(use|used|using|trigger|invoke)\b[^.]{0,40}\b(when|for|if|on|before|after|to)\b|\bwhen (the|you|a|an|asked|user)', re.I)
LINK = re.compile(r'\]\(\s*<?([^)\s>]+)')
CODEPATH = re.compile(r'`((?:\./)?(?:references|reference|rules|scripts|assets)/[^`\s]+\.\w+)`')


def tok(chars):
    """Token estimate, chars/4 rounded up."""
    return (chars + 3) // 4


def read(path):
    """File text (capped), '' if unreadable."""
    try:
        with open(path, encoding='utf-8-sig', errors='ignore') as f:
            return f.read(400000).replace('\r\n', '\n')
    except OSError:
        return ''


def frontmatter(text):
    """(fields or None, body); folded/multi-line values are joined so their real length is counted."""
    m = re.match(r'---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)', text, re.S)
    if not m:
        return None, text
    out, key = {}, None
    for line in m.group(1).split('\n'):
        k = re.match(r'([A-Za-z][\w-]*):(?:\s+(.*))?$', line)
        if k:
            key = k.group(1)
            out[key] = (k.group(2) or '').strip()
        elif key and line[:1] in (' ', '\t'):
            out[key] = f'{out[key]} {line.strip()}'.strip()
    for k, v in out.items():
        v = re.sub(r'^[>|][+-]?\d*(\s+|$)', '', v)  # YAML block marker is not content
        out[k] = v[1:-1] if len(v) > 1 and v[0] == v[-1] and v[0] in '"\'' else v
    return out, text[m.end():]


def skill_dirs(root):
    """Every directory under root (inclusive) holding a SKILL.md."""
    found = []
    for d, ds, fs in os.walk(root):
        ds[:] = sorted(x for x in ds if x not in SKIP_DIRS)
        if 'SKILL.md' in fs:
            found.append(d)
    return found


def md_files(d):
    """{relative posix path: text} of the skill's other .md files; nested skills own theirs."""
    out = {}
    for root, ds, fs in os.walk(d):
        ds[:] = sorted(x for x in ds if x not in SKIP_DIRS and not os.path.isfile(os.path.join(root, x, 'SKILL.md')))
        for f in sorted(fs):
            rel = os.path.relpath(os.path.join(root, f), d).replace(os.sep, '/')
            if f.lower().endswith('.md') and rel != 'SKILL.md':
                out[rel] = read(os.path.join(root, f))
    return out


def mentions(text, rel, base=''):
    """True if text (a file in folder base) points at rel: by path, file name, glob or folder."""
    names = {rel, os.path.relpath(rel, base or '.').replace(os.sep, '/'), os.path.basename(rel)}
    if any(re.search(r'(?<![\w-])' + re.escape(n) + r'(?![\w-])', text) for n in names):
        return True
    globs = re.findall(r'[\w./-]*\*[\w./*-]*\.md', text)
    if any(fnmatch.fnmatch(rel, g[2:] if g.startswith('./') else g) for g in globs):
        return True
    folder = os.path.dirname(rel)
    # "rules/" or "rules/<name>.md" means: pick files from this folder
    return bool(folder) and bool(re.search(r'(?<![\w-])' + re.escape(folder) + r'/(?![\w.-])', text))


def depths(body, files):
    """{rel: link hops from SKILL.md} for every reachable file."""
    seen, frontier, hop = {}, [('', body)], 0
    while frontier:
        hop += 1
        nxt = []
        for base, text in frontier:
            for rel, t in files.items():
                # compiled docs are never a route to other files: they mention everything
                if rel not in seen and mentions(text, rel, base):
                    seen[rel] = hop
                    if os.path.basename(rel).lower() not in BULK | HUMAN:
                        nxt.append((os.path.dirname(rel), t))
        frontier = nxt
    return seen


def broken_links(d, body):
    """Local paths SKILL.md points at that do not exist."""
    prose = re.sub(r'^(```|~~~).*?^\1', '', body, flags=re.S | re.M)  # fenced examples are not real links
    bad = []
    for t in LINK.findall(prose) + CODEPATH.findall(prose):
        p = t.split('#')[0].split('?')[0]
        if not p or re.match(r'[a-z][\w+.-]*:|[/~$]', p, re.I) or re.search(r'[<>*{}$]', p):
            continue
        if not re.search(r'\.\w{1,5}$|/', p):  # "(see)" style false hits
            continue
        if not os.path.exists(os.path.join(d, p)) and p not in bad:
            bad.append(p)
    return bad


def check_meta(d, fm):
    """Findings about the always-listed part: name and description."""
    if fm is None:
        return [('error', 'no-frontmatter', 'SKILL.md has no --- block: nothing tells the model when to load it')]
    out, name, desc = [], fm.get('name', ''), fm.get('description', '')
    if not name:
        out.append(('warn', 'name-missing', 'no name field'))
    elif len(name) > NAME_MAX or not re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+)*', name):
        out.append(('warn', 'name-format', f'name "{name[:70]}": use lowercase, digits, hyphens, <= {NAME_MAX} chars'))
    elif name != os.path.basename(os.path.abspath(d)):
        out.append(('warn', 'name-dir', f'name "{name}" differs from folder "{os.path.basename(os.path.abspath(d))}"'))
    if not desc:
        return out + [('error', 'desc-missing', 'no description field')]
    if len(desc) > DESC_MAX:
        out.append(('error', 'desc-over-limit', f'description {len(desc)} chars > {DESC_MAX}'))
    elif len(desc) > LONG:
        out.append(('warn', 'desc-long', f'description {len(desc)} chars > {LONG}: ~{tok(len(desc) - LONG)} tok [est] extra in every chat'))
    if not TRIGGER.search(desc):
        out.append(('warn', 'desc-no-trigger', 'description does not say when to use it'))
    return out


def check_files(body, files):
    """Findings about progressive disclosure of the on-demand files."""
    out, hops = [], depths(body, files)
    for rel, text in files.items():
        base = os.path.basename(rel).lower()
        if base in HUMAN or base.startswith('_'):
            continue
        if base in BULK:
            if len(text) > max(len(body), REF_BYTES):
                out.append(('warn', 'bulk-doc', f'{rel} ~{tok(len(text))} tok [est]: all-in-one copy; keep it out of the load path'))
        elif rel not in hops:
            out.append(('warn', 'orphan', f'{rel}: nothing reachable from SKILL.md points at it'))
        else:
            if hops[rel] > 1:
                out.append(('note', 'nested', f'{rel}: {hops[rel]} hops from SKILL.md; link it directly'))
            if len(text.encode()) > REF_BYTES:
                out.append(('note', 'ref-big', f'{rel} ~{tok(len(text))} tok [est]: split it or add a contents list'))
    return out


def check(d):
    """Report for one skill directory."""
    text = read(os.path.join(d, 'SKILL.md'))
    fm, body = frontmatter(text)
    files = md_files(d)
    found = check_meta(d, fm)
    lines = body.rstrip('\n').count('\n') + 1 if body.strip() else 0
    if lines > BODY_LINES:
        found.append(('warn', 'body-long', f'SKILL.md body {lines} lines > {BODY_LINES}: move detail to references/'))
    found += [('error', 'broken-link', f'SKILL.md points at missing {p}') for p in broken_links(d, body)]
    found += check_files(body, files)
    f = fm or {}
    hidden = f.get('disable-model-invocation', '').lower() == 'true'  # not listed to the model
    listed = 0 if hidden else tok(len(f.get('name', '')) + len(f.get('description', '')))
    return {'path': d, 'name': f.get('name') or os.path.basename(os.path.abspath(d)),
            'listed_tok_est': listed, 'load_tok_est': tok(len(body)),
            'ondemand_tok_est': tok(sum(len(t) for r, t in files.items() if os.path.basename(r).lower() not in HUMAN)),
            'findings': [{'level': a, 'code': b, 'msg': c} for a, b, c in found]}


def render(reports):
    """Human text, costliest listed skill first."""
    out = []
    for r in sorted(reports, key=lambda r: (-r['listed_tok_est'], r['path'])):
        out.append(f"{r['name']}: listed ~{r['listed_tok_est']} | load ~{r['load_tok_est']} | on demand ~{r['ondemand_tok_est']} tok [est]")
        out += [f"  {f['level']}: {f['code']}: {f['msg']}" for f in r['findings']]
    n = {k: sum(f['level'] == k for r in reports for f in r['findings']) for k in ('error', 'warn', 'note')}
    out.append(f"{len(reports)} skill(s), ~{sum(r['listed_tok_est'] for r in reports)} tok [est] listed in every chat; "
               f"{n['error']} error(s), {n['warn']} warning(s), {n['note']} note(s)")
    return '\n'.join(out)


def main(argv):
    """CLI entry: [check] DIR [--json] [--strict]."""
    args = argv[1:] if argv[:1] == ['check'] else list(argv)
    dirs = [a for a in args if not a.startswith('--')]
    if len(dirs) != 1 or set(args) - set(dirs) - {'--json', '--strict'}:
        print('usage: tz skills check DIR [--json] [--strict]')
        return 2
    found = skill_dirs(os.path.abspath(os.path.expanduser(dirs[0])))
    if not found:
        print(f'no SKILL.md under {dirs[0]}')
        return 2
    reports = [check(d) for d in found]
    print(json.dumps(reports, indent=1) if '--json' in args else render(reports))
    bad = {'error', 'warn'} if '--strict' in args else {'error'}
    return int(any(f['level'] in bad for r in reports for f in r['findings']))


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
