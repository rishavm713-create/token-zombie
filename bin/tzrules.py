#!/usr/bin/env python3
# Opt-in rules on top of tzshell: extra destructive/secret rules, custom rulebooks, `explain` and `verify` (stdlib only).
# Rule ids, matcher semantics and the rulebook format are adapted from kenryu42/cc-safety-net src/core/rules/
# {custom,custom-match-options,custom-subcommand,secret,destructive}.ts, src/core/policy/rulebook.ts and
# src/gate/analyzer/{network,namespace}.ts (MIT, Copyright (c) 2026 J Liew), see NOTICE. Rebuilt in Python.
import glob, json, os, re, sys

import tzshell as S

B = S.B

# ---------------------------------------------------------------- secrets (feature safety_extra)
SOURCE_EXT = ('.py', '.js', '.jsx', '.ts', '.tsx', '.go', '.rs', '.rb', '.java', '.c', '.h', '.cpp', '.cs', '.php',
              '.swift', '.kt', '.md', '.txt', '.html', '.css', '.sh')  # WHY: credentials_helper.py is code, not a key
VARIANT_PREFIX = ('id_rsa', 'id_dsa', 'id_ed25519', 'id_ecdsa', 'credentials')
VARIANT_SUFFIX = ('.bak', '.backup', '.copy', '.disabled', '.key', '.old', '.orig', '.pem', '.save', '.tmp')
EXT = set('agilekeychain asc bek cscfg fve gnucash jks keychain kwallet mdf ovpn p12 pcap pfx pkcs12 psafe3 rdp sdf '
          'tblk tpm'.split())
EXT_PATTERN = re.compile(r'^(keypair|keyring|kdb)$')
# credential files of coding CLIs (upstream's config-only rules are default-off there, so they are left out)
CLI_PATHS = {
    'claude-code': '.claude/.credentials.json',
    'codex': '.codex/auth.json .codex/.credentials.json .codex/secrets .codex/.sandbox-secrets',
    'gemini': '.gemini/oauth_creds.json .gemini/mcp-oauth-tokens.json .gemini/a2a-oauth-tokens.json '
              '.gemini/gemini-credentials.json',
    'antigravity': '.gemini/config/hooks.json .gemini/config/mcp_config.json',
    'copilot-cli': '.copilot/config.json .copilot/mcp-oauth-config .copilot/mcp-secrets',
    'kimi-code': '.kimi-code/server.token .kimi-code/credentials .kimi/credentials .kimi/mcp-oauth',
    'opencode': '.local/share/opencode/auth.json .local/share/opencode/mcp-auth.json .local/share/opencode/opencode.db',
    'pi': '.pi/agent/auth.json',
    'amp': '.local/share/amp/secrets.json .amp/oauth',
    'cursor': '.cursor/auth.json .config/cursor/auth.json',
    'grok-build': '.grok/auth.json .grok/mcp_credentials.json',
    'droid': '.factory/auth.encrypted .factory/auth.v2.file .factory/auth.v2.key .factory/auth.v2.loginkeychain',
    'devin': '.local/share/devin/credentials.toml .local/share/devin/mcp/oauth',
}


def secret_extra(tok):
    """rule-id for the wider upstream secret list (variants, key extensions, CLI credentials), else None."""
    for t in {tok, tok.split('=', 1)[-1]}:
        t = t.lstrip('@')
        if not t or t.startswith('-') or re.search(r'\s', t) or '://' in t:
            continue
        low = t.lower()
        r = S._secret(low) if low != t else None  # case-insensitive file systems: .ENV is .env
        if r:
            return r
        h = os.path.expanduser('~')
        full = os.path.normpath(os.path.expanduser(t.replace('${HOME}', h).replace('$HOME', h)))
        for slug, rels in CLI_PATHS.items():
            for rel in rels.split():
                d = os.path.join(h, rel)
                if full == d or full.startswith(d + '/'):
                    return 'secret.cli.' + slug
        m = re.search(r'/\.(kube/config|docker/config\.json)(\.[a-z]+)$', full)
        if m and m.group(2) in VARIANT_SUFFIX:
            return 'secret.home.%s-config.%s' % (m.group(1).split('/')[0], m.group(2)[1:])
        base = os.path.basename(low.rstrip('/'))
        if base.endswith('.pub'):
            continue
        for p in VARIANT_PREFIX:
            rest = base[len(p):] if base.startswith(p) else ''
            slug = p.replace('_', '-')
            if rest in VARIANT_SUFFIX:
                return 'secret.variant.%s.%s' % (slug, rest[1:])
            if rest[:1] in ('-', '_') and not base.endswith(SOURCE_EXT):
                return 'secret.variant.%s.separator' % slug
        if re.match(r'^[^.*?]+_(rsa|dsa|ed25519|ecdsa)$', base) and ('/' in t or os.path.exists(t)):
            return 'secret.pattern.ssh-key-basename'  # WHY path/exists: `grep use_rsa` is a word, not a file
        stem, dot, ext = base.rpartition('.')
        if dot and stem and ext in EXT:
            return 'secret.ext.' + ext
        if dot and stem and EXT_PATTERN.match(ext):
            return 'secret.ext-pattern.' + {'keypair': 'key', 'keyring': 'keystore', 'kdb': 'kdbx'}[ext]
    return None


# ---------------------------------------------------------------- extra command rules (feature safety_extra)
CLIENTS = set('curl wget nc ncat netcat socat telnet http https httpie xh fetch aria2c ssh openssl'.split())
INTERP = re.compile(r'^(python[\d.]*|node(js)?|perl|ruby|php|deno|bun)$')
METADATA = re.compile(r'(?<![\w.-])(?:169\.254\.169\.254|169\.254\.170\.23|169\.254\.170\.2|100\.100\.100\.200|'
                      r'metadata\.google\.internal|metadata\.goog)(?![\w-]|\.[\w-])|(?<![\w:])fd00:ec2::(?:254|23)(?![\w:])',
                      re.I)
GIT_NET = {'fetch', 'pull', 'push', 'clone', 'ls-remote', 'remote', 'submodule', 'archive'}


def _git_sub(a):
    """(global options, subcommand, rest) of git arguments."""
    i = 0
    while i < len(a) and a[i].startswith('-'):
        i += 2 if a[i] in S.GIT_ARG_OPTS else 1
    return a[:i], a[i] if i < len(a) else '', a[i + 1:]


def _git_extra(a, env):
    head, sub, rest = _git_sub(a)
    if sub in GIT_NET and any(k in env for k in ('GIT_SSH_COMMAND', 'GIT_SSH', 'GIT_SSH_VARIANT')):
        return B('git.ssh-env', 'A Git SSH environment override runs a program that cannot be checked.')
    hidden = any(x.startswith('--config-env=alias.') or (x == '--config-env' and a[k + 1:k + 2] and
                 a[k + 1].startswith('alias.')) for k, x in enumerate(head))
    if hidden or any(k.startswith('GIT_CONFIG_KEY_') and v.startswith('alias.') for k, v in env.items()) \
            or 'alias.' in env.get('GIT_CONFIG_PARAMETERS', ''):
        return B('git.alias-config', 'A Git alias set through the environment cannot be resolved safely.')
    if sub == 'checkout' and any(x.startswith('--pathspec-from') for x in rest):
        return B('git.checkout-pathspec-from-file', "git checkout --pathspec-from-file discards listed files. Use 'git stash' first.")
    return None


def _unshare(a):
    """True when unshare options create a user namespace (options before the program only)."""
    long_val = set('--propagation --setgroups --root --wd --setuid --setgid --map-user --map-group --map-users '
                   '--map-groups --owner --whitelist-env --load-interp'.split())
    i = 0
    while i < len(a) and a[i].startswith('-') and a[i] != '--':
        x = a[i]
        if x.startswith('--'):
            if re.match(r'^--(user|map-root-user|map-current-user|map-auto|map-subids|map-(user|group)s?|owner|'
                        r'mount-binfmt|load-interp)(=|$)', x):
                return True
            i += 2 if x in long_val else 1
            continue
        for k, ch in enumerate(x[1:], 1):
            if ch in 'Urcl':
                return True
            if ch in 'RwSG':
                i += 1 if k == len(x) - 1 else 0
                break
        i += 1
    return False


def _awk(a, ctx):
    """system() inside an awk program: literal commands are analysed, built ones are blocked."""
    prog = ' '.join(x for x in a if 'system' in x)
    for m in re.finditer(r'\bsystem\s*\(\s*(?:"((?:[^"\\]|\\.)*)"\s*\))?', prog):
        if m.group(1) is None:
            return B('awk.system-dynamic', 'awk system() with a built command cannot be checked.')
        v = S._text(m.group(1), ctx)
        if v:
            return B('interpreter.dangerous-command', 'awk system() runs a destructive command (%s).' % v[0])
    return None


def extra(c, a, env, ctx):
    """New standard-mode upstream rules for one unwrapped command."""
    if c == 'git':
        return _git_extra(a, env)
    if c == 'find' and '-delete' in a and '-prune' not in a and any('.git' in x.split('/') for x in a):
        return B('find.delete-git-metadata', 'find -delete on .git metadata destroys repository history.')
    if (c in CLIENTS or INTERP.match(c)) and any(METADATA.search(x) and not x.startswith('--noproxy') and
                                                 (k == 0 or a[k - 1] != '--noproxy') for k, x in enumerate(a)):
        return B('network.cloud-metadata', 'Cloud metadata endpoints hand out instance credentials.')
    if c == 'unshare' and _unshare(a):
        return B('unshare.user-namespace', 'unshare creating a user namespace is a privilege-escalation step.')
    if c in ('awk', 'gawk', 'mawk', 'nawk'):
        return _awk(a, ctx)
    return None


# ---------------------------------------------------------------- strict rules (feature safety_strict)
LOOPBACK = re.compile(r'^(localhost|[a-z\d-]+(\.[a-z\d-]+)*\.localhost|127(\.\d{1,3}){3}|0\.0\.0\.0|\[::1\])$', re.I)
CURL_BODY = {'--data', '--data-ascii', '--data-binary', '--data-raw', '--data-urlencode', '--json', '--form',
             '--form-string', '--upload-file'}
WGET_BODY = ('--post-data', '--post-file', '--body-data', '--body-file')


def _loopback(url):
    host = re.sub(r'^[a-z]+://', '', url, flags=re.I).split('/')[0].split('?')[0].rsplit('@', 1)[-1]
    return bool(LOOPBACK.match(re.sub(r':\d*$', '', host)))


def _uploads(c, a):
    """True when curl/wget sends a body or file and some URL is not loopback."""
    if c == 'curl':
        get = '--get' in a or any(re.match(r'^-[a-zA-Z]*G', x) for x in a)
        body = any(x.split('=')[0] in CURL_BODY or re.match(r'^-[sSkLvfiI]*[FT]', x) or
                   (not get and re.match(r'^-[sSkLvfiI]*d', x)) for x in a)
        if get and not any(re.match(r'^(--form|--upload-file|-[sSkLvfiI]*[FT])', x) for x in a):
            return False
    else:
        body = any(x.split('=')[0] in WGET_BODY for x in a)
    urls = [x.split('=', 1)[-1] if x.startswith('--url=') else x for x in a
            if re.match(r'^(--url=)?(https?|ftp)://', x, re.I) or re.match(r'^(localhost|127\.|[\w-]+\.[a-z]{2,}(:\d+)?/)', x)]
    return body and not (urls and all(_loopback(u) for u in urls))


def strict(c, t, a):
    """Upstream strict-mode rules: remote uploads and executables built from substitutions."""
    if c in ('curl', 'wget') and _uploads(c, a):
        return B('network.upload-remote', 'Uploading data to a remote host can send local files or secrets off the machine.')
    if t[0].startswith(('$', '`')) and any(re.match(r'^-[A-Za-z]*(r[A-Za-z]*f|f[A-Za-z]*r)[A-Za-z]*$', x) for x in a):
        return B('shell.dynamic-executable', 'A recursive force flag on a command name built at run time cannot be checked.')
    return None


# ---------------------------------------------------------------- custom rulebooks (feature custom_rules)
NAME = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]{0,63}$')
COMMAND = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]*$')
MAX_FILE, MAX_FILES, MAX_RULES, MAX_REASON = 262144, 50, 500, 256
GLOBAL_VALUE_OPTS = {  # options that consume the next token, so they do not break a command path
    'aws': set('--ca-bundle --cli-binary-format --cli-connect-timeout --cli-error-format --cli-read-timeout --color '
               '--endpoint-url --output --profile --query --region'.split()),
    'gcloud': set('--access-token-file --account --billing-project --configuration --flags-file --flatten --format '
                  '--impersonate-service-account --project --trace-token --verbosity'.split()),
    'az': {'-o', '--output', '--query', '--subscription'},
}
SUB_VALUE_OPTS = {'git': S.GIT_ARG_OPTS,
                  'docker': set('-c -H -l --config --context --host --log-level --tlscacert --tlscert --tlskey'.split())}


def rule_files(cwd):
    """User rulebooks plus the nearest project's .tz/rules/*.json (rules only add blocks, so projects cannot loosen)."""
    out = sorted(glob.glob(os.path.expanduser('~/.claude/token-zombie/rules/*.json')))
    d = os.path.abspath(cwd or '.')
    while True:
        p = os.path.join(d, '.tz', 'rules')
        if os.path.isdir(p):
            out += sorted(glob.glob(os.path.join(glob.escape(p), '*.json')))
            break
        if os.path.dirname(d) == d:
            break
        d = os.path.dirname(d)
    return out[:MAX_FILES]


def _strs(v, unique=True):
    return isinstance(v, list) and bool(v) and all(isinstance(x, str) and x for x in v) and (not unique or len(set(v)) == len(v))


def _rule_errors(r, ver, i, listed):
    """Problems with one rule of a rulebook."""
    if not isinstance(r, dict):
        return ['rules.%d: must be an object' % i]
    e = []
    if not (isinstance(r.get('name'), str) and NAME.match(r['name'])):
        e.append('name: must match rule name pattern')
    if not (isinstance(r.get('command'), str) and COMMAND.match(r['command'])):
        e.append('command: required string matching command pattern')
    elif r['command'] not in listed:
        e.append('command: not listed in allowed_commands')
    if not (isinstance(r.get('reason'), str) and 0 < len(r['reason']) <= MAX_REASON):
        e.append('reason: required non-empty string up to %d characters' % MAX_REASON)
    if ver == 1:
        sub = r.get('subcommand')
        if sub is not None and not (isinstance(sub, str) and COMMAND.match(sub)):
            e.append('subcommand: must match command pattern')
        if not _strs(r.get('block_args'), False):
            e.append('block_args: required non-empty array')
    else:
        m = r.get('match')
        if not isinstance(m, dict) or not _strs(m.get('command_path'), False):
            e.append('match.command_path: required non-empty array of strings')
        elif any(k in m and not _strs(m[k]) for k in ('any_args', 'exclude_args')):
            e.append('match.any_args/exclude_args: non-empty array of unique strings')
        if 'subcommand' in r or 'block_args' in r:
            e.append('subcommand/block_args: not supported in rulebook_version 2')
    return ['rules.%d.%s' % (i, x) for x in e]


def validate(book):
    """List of problems; empty means the rulebook is accepted."""
    if not isinstance(book, dict):
        return ['Rulebook must be an object']
    ver, rules, listed = book.get('rulebook_version'), book.get('rules'), book.get('allowed_commands')
    e = [] if ver in (1, 2) else ['rulebook_version must be 1 or 2']
    if not (isinstance(book.get('name'), str) and NAME.match(book['name'])):
        e.append('name: required string matching rule name pattern')
    if not (isinstance(book.get('version'), str) and book['version']):
        e.append('version: required non-empty string')
    if not (isinstance(listed, list) and all(isinstance(x, str) and COMMAND.match(x) for x in listed)):
        e.append('allowed_commands: required array of command names')
        listed = []
    if not isinstance(rules, list) or len(rules) > MAX_RULES:
        return e + ['rules: required array of at most %d rules' % MAX_RULES]
    for i, r in enumerate(rules):
        e += _rule_errors(r, ver, i, listed)
    names = [str(r.get('name', '')).lower() for r in rules if isinstance(r, dict)]
    if len(set(names)) != len(names):
        e.append('rules: duplicate rule name')
    opts = book.get('options_with_values')
    if opts is not None and not (ver == 2 and isinstance(opts, dict) and
                                 all(_strs(v) and all(x.startswith('-') for x in v) for v in opts.values())):
        e.append('options_with_values: version 2 object of command -> option list')
    if not isinstance(book.get('tests', []), list):
        e.append('tests: must be an array if provided')
    return e[:20]


def load(path):
    """(rules, errors, book); an invalid book contributes no rules."""
    try:
        if os.path.getsize(path) > MAX_FILE:
            return [], ['file is larger than %d bytes' % MAX_FILE], None
        with open(path, encoding='utf-8') as f:
            book = json.load(f)
    except (OSError, ValueError, RecursionError) as x:
        return [], ['cannot read: %s' % x], None
    errs = validate(book)
    if errs:
        return [], errs, book
    opts = book.get('options_with_values') or {}
    return [dict(r, _ver=book['rulebook_version'], _opts=opts.get(r['command'], [])) for r in book['rules']], [], book


def _has_path(args, path, valued):
    i, skip = 0, False
    for x in args:
        if i >= len(path):
            return True
        if skip:
            skip = False
        elif x.startswith('-'):
            skip = '=' not in x and x in valued
        elif x != path[i]:
            return False
        else:
            i += 1
    return i >= len(path)


def _has_sub(t, i, want, valued):
    """First non-option word equals `want`; an unknown option may or may not own the next word."""
    while i < len(t):
        x = t[i]
        if x == '--':
            return t[i + 1:i + 2] == [want]
        if x in valued:
            i += 2
            continue
        if not x.startswith('-'):
            return x == want
        if '=' not in x and i + 1 < len(t) and not t[i + 1].startswith('-') and _has_sub(t, i + 2, want, valued):
            return True
        i += 1
    return False


def match(t, rules):
    """First custom rule matching tokens -> (rule_id, reason)."""
    if not t:
        return None
    c, args = os.path.basename(t[0]).lower(), t[1:]
    short = {'-' + ch for x in args if re.match(r'^-[^-]', x) for ch in x[1:] if ch.isalpha()}
    for r in rules:
        if c != r['command'].lower():
            continue
        m = r.get('match')
        if m:
            if set(m.get('exclude_args') or []) & set(args) or (m.get('any_args') and not set(m['any_args']) & set(args)):
                continue
            hit = _has_path(args, m['command_path'], GLOBAL_VALUE_OPTS.get(c, set()) | set(r.get('_opts', [])))
        else:
            sub = r.get('subcommand')
            hit = (not sub or _has_sub(t, 1, sub, SUB_VALUE_OPTS.get(c, set()))) and \
                bool(set(r.get('block_args') or []) & (set(t) | short))
        if hit:
            return B('custom.' + r['name'], '[%s] %s' % (r['name'], r['reason']))
    return None


def verify(paths):
    """Validate rulebooks and run their own test fixtures -> (ok, lines)."""
    good, out = True, []
    for p in paths:
        rules, errs, book = load(p)
        for n, case in enumerate(([] if errs else book.get('tests') or [])):
            if not (isinstance(case, dict) and isinstance(case.get('command'), str) and case.get('expect') in ('blocked', 'allowed')):
                errs.append('tests.%d: needs command and expect blocked|allowed' % n)
                continue
            try:
                import shlex
                segs = S.scan(case['command'])[0]
                hit = next((v for v in (match(_strip(shlex.split(s)), rules) for s, _ in segs) if v), None)
            except (ValueError, S.ParseError):
                errs.append('tests.%d: command cannot be parsed' % n)
                continue
            if bool(hit) != (case['expect'] == 'blocked') or (hit and case.get('rule') and hit[0] != 'custom.' + case['rule']):
                errs.append('tests.%d: expected %s, got %s' % (n, case['expect'], hit[0] if hit else 'allowed'))
        good = good and not errs
        out.append('%s: %s' % (p, 'ok (%d rules)' % len(rules) if not errs else 'INVALID'))
        out += ['  ' + x for x in errs]
    return good, out


def _strip(t):
    """Drop leading VAR=x assignments (fixture commands are simple commands)."""
    while t and re.match(r'^[A-Za-z_]\w*=', t[0]):
        t = t[1:]
    return t


# ---------------------------------------------------------------- hook for tzshell and the dispatcher
def check(t, env, ctx):
    """Opt-in verdict for one unwrapped command that the built-in rules allowed."""
    c, a, v = os.path.basename(t[0]), t[1:], None
    if S._on('safety_extra'):
        if c not in S.ECHO:
            for x in a:
                r = secret_extra(x)
                if r:
                    return B(r, 'Touches a credentials file (%s). Ask the owner first.' % x)
        v = extra(c, a, env, ctx)
    if not v and S._on('safety_strict'):
        v = strict(c, t, a)
    if not v and S._on('custom_rules'):
        v = match(t, [r for p in rule_files(ctx['cwd']) for r in load(p)[0]])
    return v


def check_path(path, cwd=None):
    """(ok, reason, rule_id) for a Read/Grep tool path; the dispatcher calls this behind feature secret_read_block."""
    if not path:
        return True, '', ''
    p = os.path.expanduser(path)
    cands = [p]
    if os.path.exists(os.path.join(cwd or '.', p)):  # a symlink with an innocent name still opens the secret
        cands.append(os.path.realpath(os.path.join(cwd or '.', p)))
    for x in cands:
        x = x.replace(' ', '_')  # WHY: the matchers skip text with spaces (command words); a tool path is one file
        r = S._secret(x) or (secret_extra(x) if S._on('safety_extra') else None)
        if r:
            return False, 'Reads a credentials file (%s). Ask the owner first.' % path, r
    return True, '', ''


# ---------------------------------------------------------------- explain
def explain(cmd, cwd=None):
    """Dry-run trace of the guard's decision; analyses text only, never runs it."""
    cwd = cwd or os.getcwd()
    trace, old, S.TRACE = [], S.TRACE, []
    try:
        r = S.analyze(cmd, cwd)
        trace = S.TRACE
    finally:
        S.TRACE = old
    layer = 'parser'
    if r is None:  # unparseable and harmless-looking: the same regex fallback the hook uses
        import tzops
        ok, why = tzops.safe(cmd, cwd)
        r, layer = (ok, why, '' if ok else 'regex-fallback'), 'regex'
    on = [n for n in ('safety_net', 'safety_extra', 'safety_strict', 'custom_rules') if S._on(n)]
    return {'command': cmd, 'cwd': cwd, 'verdict': 'allowed' if r[0] else 'blocked', 'rule': r[2], 'reason': r[1],
            'layer': layer, 'features': on, 'steps': trace,
            'rulebooks': rule_files(cwd) if 'custom_rules' in on else []}


def main(argv=None):
    """tz rules explain [--json] [--cwd DIR] <command> | verify [file...] | list"""
    argv = list(sys.argv[1:] if argv is None else argv)
    verb = argv.pop(0) if argv else ''
    if verb == 'explain':
        js, cwd = False, None
        while argv[:1] in (['--json'], ['--cwd']):
            if argv.pop(0) == '--json':
                js = True
            else:
                cwd = argv.pop(0) if argv else None
        argv = argv[1:] if argv[:1] == ['--'] else argv
        if not argv:
            print('usage: explain [--json] [--cwd DIR] "<command>"')
            return 2
        x = explain(argv[0] if len(argv) == 1 else ' '.join(argv), cwd)
        if js:
            print(json.dumps(x, indent=2))
        else:
            for n, s in enumerate(x['steps'], 1):
                print('step %d (depth %d, in %s): %s' % (n, s['depth'], s['dir'] or 'unknown dir', json.dumps(s['tokens'])))
            print('verdict: %s%s [layer: %s]' % (x['verdict'], ' by ' + x['rule'] if x['rule'] else '', x['layer']))
            if x['reason']:
                print('reason: ' + x['reason'])
            print('features on: ' + (', '.join(x['features']) or 'none'))
        return 0
    if verb in ('verify', 'list'):
        paths = argv or rule_files(os.getcwd())
        if not paths:
            print('no rulebooks (~/.claude/token-zombie/rules/*.json or <project>/.tz/rules/*.json)')
            return 0
        good, lines = verify(paths)
        print('\n'.join(lines))
        if verb == 'list':
            for p in paths:
                for r in load(p)[0]:
                    print('custom.%s  %s: %s' % (r['name'], r['command'], r['reason']))
        if not S._on('custom_rules'):
            print('note: custom rules are off (TZ_FEAT_CUSTOM_RULES=1 or config features.custom_rules)')
        return 0 if good else 1
    print(main.__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main())
