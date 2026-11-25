#!/usr/bin/env python3
"""tz skill-lint: agent-skill spec check plus a description-budget report (name + description are listed in every chat).
validate_text adapted from anthropics/skills skills/skill-creator/scripts/quick_validate.py (Apache-2.0, Copyright 2026 Anthropic, PBC), see NOTICE.
Changes: stdlib frontmatter reader instead of PyYAML (a subset of YAML, not a full parser), reads text instead of a path,
Claude Code frontmatter keys are accepted unless strict, budget report and hook advice added. Read-only, no network."""
import ast, json, os, re, sys

ALLOWED = {'name', 'description', 'license', 'allowed-tools', 'metadata', 'compatibility'}
# keys Claude Code reads that the portable spec check rejects
CLAUDE_KEYS = {'argument-hint', 'arguments', 'disable-model-invocation', 'user-invocable', 'model', 'effort', 'context',
               'agent', 'hooks', 'paths', 'shell', 'when_to_use', 'version'}
MAX_LINES = 500  # skill-creator guidance for the SKILL.md body


class BadYAML(ValueError):
    pass


def _scalar(v):
    if v.startswith(('"', "'")):
        q = v[0]
        m = re.match(r'"(?:[^"\\]|\\.)*"' if q == '"' else r"'(?:[^']|'')*'", v, re.S)
        if not m or not re.match(r'\s*(#.*)?$', v[m.end():]):
            raise BadYAML('unterminated or trailing text after quoted value')
        s = m.group(0)[1:-1]
        if q == "'":
            return s.replace("''", "'")
        try:
            return ast.literal_eval('"' + s.replace('\n', ' ') + '"')
        except (SyntaxError, ValueError):
            return s
    v = re.split(r'(?:^|\s)#', v)[0].strip()
    if v[:1] in ('[', '{'):
        if v[-1] != {'[': ']', '{': '}'}[v[0]]:
            raise BadYAML('unclosed flow collection')
        return [] if v[0] == '[' else {}
    if re.search(r':(\s|$)', v):
        raise BadYAML('unquoted value contains ": " (quote it)')
    if v[:1] in ('@', '`', '%', '*', '&', '!'):
        raise BadYAML(f'unquoted value cannot start with {v[0]}')
    if v in ('', '~', 'null', 'Null', 'NULL'):
        return None
    if v.lower() in ('true', 'false'):
        return v.lower() == 'true'
    if re.match(r'[-+]?(\d+(\.\d*)?|\.\d+)$', v):
        return float(v)
    return v


def parse_frontmatter(text):
    """Top-level keys of a frontmatter block; nested blocks come back as {} or []."""
    items = []  # [key, first-line value, continuation lines]
    for ln in text.split('\n'):
        if not items and (not ln.strip() or ln.startswith('#')):
            continue
        if not ln.strip() or ln[0] in ' \t' or (ln.startswith('- ') and items and not items[-1][1]):
            if items:
                items[-1][2].append(ln.strip())
            continue
        if ln.startswith('#'):
            continue
        m = re.match(r'([^\s:#][^:]*?):(?:[ \t]+(.*))?$', ln)
        if not m:
            raise BadYAML(f'expected "key: value", got "{ln[:40]}"')
        items.append([m.group(1), (m.group(2) or '').strip(), []])
    out = {}
    for k, v, more in items:
        while more and not more[-1]:
            more.pop()
        if re.match(r'[|>][-+0-9]*$', v):
            out[k] = ('\n' if v[0] == '|' else ' ').join(more).strip()
        elif not v and more and (more[0].startswith('- ') or more[0] == '-'):
            out[k] = []
        elif not v and more and re.match(r'[^\s"\'][^:]*:(\s|$)', more[0]):
            out[k] = {}
        else:
            out[k] = _scalar(' '.join(x for x in [v] + more if x))
    return out


def _frontmatter(content):
    if not content.startswith('---'):
        return None, 'No YAML frontmatter found'
    m = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not m:
        return None, 'Invalid frontmatter format'
    try:
        fm = parse_frontmatter(m.group(1))
    except BadYAML as e:
        return None, f'Invalid YAML in frontmatter: {e}'
    if not fm:
        return None, 'Frontmatter must be a YAML dictionary'
    return fm, ''


def validate_text(content, strict=True):
    """(valid, first problem). strict=True is the upstream portable spec."""
    fm, err = _frontmatter(content)
    if err:
        return False, err
    allowed = ALLOWED if strict else ALLOWED | CLAUDE_KEYS
    extra = set(fm) - allowed
    if extra:
        return False, (f"Unexpected key(s) in SKILL.md frontmatter: {', '.join(sorted(extra))}. "
                       f"Allowed properties are: {', '.join(sorted(allowed))}")
    for k in ('name', 'description'):
        if k not in fm:
            return False, f"Missing '{k}' in frontmatter"
    name = fm['name']
    if not isinstance(name, str):
        return False, f'Name must be a string, got {type(name).__name__}'
    name = name.strip()
    if name:
        if not re.match(r'^[a-z0-9-]+$', name):
            return False, f"Name '{name}' should be kebab-case (lowercase letters, digits, and hyphens only)"
        if name.startswith('-') or name.endswith('-') or '--' in name:
            return False, f"Name '{name}' cannot start/end with hyphen or contain consecutive hyphens"
        if len(name) > 64:
            return False, f'Name is too long ({len(name)} characters). Maximum is 64 characters.'
    desc = fm['description']
    if not isinstance(desc, str):
        return False, f'Description must be a string, got {type(desc).__name__}'
    desc = desc.strip()
    if '<' in desc or '>' in desc:
        return False, 'Description cannot contain angle brackets (< or >)'
    if len(desc) > 1024:
        return False, f'Description is too long ({len(desc)} characters). Maximum is 1024 characters.'
    comp = fm.get('compatibility')
    if comp:
        if not isinstance(comp, str):
            return False, f'Compatibility must be a string, got {type(comp).__name__}'
        if len(comp) > 500:
            return False, f'Compatibility is too long ({len(comp)} characters). Maximum is 500 characters.'
    return True, 'Skill is valid!'


def inspect(path, strict=False):
    """One SKILL.md -> {path, name, error, desc (chars), tokens (listing, EST chars/4), lines (body)}."""
    r = {'path': path, 'name': os.path.basename(os.path.dirname(os.path.abspath(path))), 'error': '',
         'desc': 0, 'tokens': 0, 'lines': 0}
    try:
        with open(path, encoding='utf-8-sig') as f:  # universal newlines: CRLF files pass
            text = f.read()
    except (OSError, UnicodeError) as e:
        r['error'] = f'unreadable: {type(e).__name__}'
        return r
    ok_, msg = validate_text(text, strict)
    r['error'] = '' if ok_ else msg
    fm = _frontmatter(text)[0] or {}
    m = re.match(r'^---\n.*?\n---[^\n]*\n?', text, re.DOTALL)
    r['lines'] = len(text[m.end() if m else 0:].splitlines())
    if isinstance(fm.get('name'), str) and fm['name'].strip():
        r['name'] = fm['name'].strip()
    d = fm.get('description')
    r['desc'] = len(d.strip()) if isinstance(d, str) else 0
    if fm.get('disable-model-invocation') is not True:  # such a skill is not listed to the model
        r['tokens'] = (r['desc'] + len(r['name']) + 10) // 4
    return r


def find(root):
    if os.path.isfile(root):
        return [root]
    out, seen = [], set()
    for d, dirs, files in os.walk(root, followlinks=True):
        real = os.path.realpath(d)
        if real in seen:
            dirs[:] = []
            continue
        seen.add(real)
        dirs[:] = sorted(x for x in dirs if x not in ('.git', 'node_modules'))
        if 'SKILL.md' in files:
            out.append(os.path.join(d, 'SKILL.md'))
    return out


def advise(payload):
    """PostToolUse Write/Edit of a SKILL.md -> one advice string, else None. Feature gate: skill_lint."""
    from tzlib import feature
    if not feature('skill_lint'):
        return None
    return check_edit(payload)


def check_edit(payload):
    try:
        if payload.get('tool_name') not in ('Write', 'Edit', 'MultiEdit'):
            return None
        p = payload.get('tool_input', {}).get('file_path') or ''
        if os.path.basename(p) != 'SKILL.md' or not os.path.isfile(p):
            return None
        r = inspect(p)
    except (AttributeError, TypeError, ValueError):
        return None
    bad = [r['error']] if r['error'] else []
    if r['lines'] > MAX_LINES:
        bad.append(f"body is {r['lines']} lines (guide: under {MAX_LINES}; move detail to reference files)")
    return f"TOKEN ZOMBIE skill check ({r['name']}): " + '; '.join(bad) if bad else None


USAGE = 'usage: tz skill-lint [dir|SKILL.md ...] [--strict] [--budget TOKENS] [--max-desc CHARS] [--top N] [--json]'


def main(argv):
    opt = {'--budget': None, '--max-desc': None, '--top': 5}
    paths, strict, as_json, it = [], False, False, iter(argv)
    for a in it:
        if a in ('-h', '--help'):
            print(USAGE)
            return 0
        if a == '--strict':
            strict = True
        elif a == '--json':
            as_json = True
        elif a in opt:
            v = next(it, '')
            if not v.isdecimal():
                print(USAGE, file=sys.stderr)
                return 2
            opt[a] = int(v)
        elif a.startswith('-'):
            print(USAGE, file=sys.stderr)
            return 2
        else:
            paths.append(a)
    files = []
    for p in paths or [os.path.expanduser('~/.claude/skills')]:
        got = find(os.path.expanduser(p))
        if not got:
            print(f'tz skill-lint: no SKILL.md under {p}', file=sys.stderr)
            return 2
        files += got
    rows = [inspect(f, strict) for f in files]
    total = sum(r['tokens'] for r in rows)
    bad = [r for r in rows if r['error']]
    long_ = [r for r in rows if opt['--max-desc'] is not None and r['desc'] > opt['--max-desc']]
    over = opt['--budget'] is not None and total > opt['--budget']
    code = 1 if bad or long_ or over else 0
    if as_json:
        print(json.dumps({'skills': rows, 'listing_tokens_est': total, 'over_budget': over}))
        return code
    for r in bad:
        print(f"INVALID {r['path']}: {r['error']}")
    for r in long_:
        print(f"LONG {r['name']}: description {r['desc']} chars > {opt['--max-desc']}")
    for r in rows:
        if r['lines'] > MAX_LINES:
            print(f"WARN {r['name']}: body {r['lines']} lines > {MAX_LINES}")
    print(f'{len(rows)} skills, {len(bad)} invalid; skill list ~{total} tok per chat (EST chars/4)')
    for r in sorted(rows, key=lambda r: -r['tokens'])[:opt['--top']]:
        print(f"  ~{r['tokens']} tok  {r['name']} ({r['desc']} chars)")
    if over:
        print(f"OVER BUDGET: ~{total} > {opt['--budget']} tok")
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
