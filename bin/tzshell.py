#!/usr/bin/env python3
# Shell command analyser behind tzops.safe(): quote-aware segmenter + per-command rule engine (stdlib only).
# Rule ids, reasons and the verdict fixtures it is tested against are adapted from kenryu42/cc-safety-net
# (MIT, Copyright (c) 2026 J Liew), see NOTICE. Independent rebuild in Python: no TypeScript was copied.
# analyze(cmd, cwd) -> (ok, reason, rule_id) | None.  None = text could not be parsed and shows no dangerous raw text.
# Feature safety_net (on) = bypass fixes: more wrappers, cd tracking, subshells, stdin redirects, braces.
# Features safety_extra / safety_strict / custom_rules (off) add the rules in tzrules.py.
import os, re, shlex

SHELLS = {'bash', 'sh', 'zsh', 'dash', 'ksh'}
ECHO = {'echo', 'printf'}  # only THEIR OWN arguments are exempt, never the rest of the line
KEYWORDS = {'{', '}', '!', 'then', 'do', 'else', 'elif', 'if', 'while', 'until'}
FETCH = {'curl', 'wget', 'cat', 'base64', 'nc', 'openssl', 'gpg', 'echo', 'printf', 'fetch'}
MAX_DEPTH = 8
TRACE = None  # tzrules.explain sets a list; run() records each unwrapped command into it
# prefix commands that run their operands: name -> options that take a value
WRAPPERS = {'busybox': set(), 'chronic': set(), 'coproc': set(), 'unbuffer': set(), 'caffeinate': {'-t', '-w'},
            'stdbuf': {'-i', '-o', '-e'}, 'ionice': {'-c', '-n', '-p'}}


def _on(name):
    """Feature switch; if tzlib cannot load, only the default-on hardening stays active."""
    try:
        from tzlib import feature
        return feature(name)
    except Exception:
        return name == 'safety_net'


class ParseError(Exception):
    pass


def B(rid, why):
    return (rid, why)


# ---------------------------------------------------------------- segmenter
def _close(s, i):
    """Index of the ')' matching the '$(' at s[i:i+2]; quote aware."""
    d, j, q = 1, i + 2, ''
    while j < len(s):
        ch = s[j]
        if q:
            if ch == '\\' and q == '"':
                j += 1
            elif ch == q:
                q = ''
        elif ch == '\\':
            j += 1
        elif ch in '\'"':
            q = ch
        elif ch == '(':
            d += 1
        elif ch == ')':
            d -= 1
            if d == 0:
                return j
        j += 1
    raise ParseError('unclosed $(')


def _ansi(body):
    """Decode a $'...' body so shlex can treat it as plain single-quoted text."""
    def rep(m):
        e = m.group(1)
        if e[0] == 'x':
            return chr(int(e[1:], 16))
        if e[0] in '01234567':
            return chr(int(e, 8))
        return {'n': '\n', 't': '\t', 'r': '\r', 'a': '\a', 'b': '\b', 'e': '\x1b'}.get(e, e)
    return re.sub(r"\\(x[0-9a-fA-F]{1,2}|[0-7]{1,3}|.)", rep, body, flags=re.S)


def scan(s):
    """-> (segments [(text, op_before)], subs [text executed via $() / backticks / shell heredocs])."""
    segs, subs, buf, op = [], [], [], ''
    pend = []  # heredoc delimiters waiting for the next newline
    i, n = 0, len(s)

    def cut(newop):
        nonlocal buf, op
        t = ''.join(buf).strip()
        if t:
            segs.append((t, op))
        buf, op = [], newop

    while i < n:
        ch = s[i]
        if ch == '\\':
            if s[i + 1:i + 2] == '\n':
                buf.append(' ')
            else:
                buf.append(s[i:i + 2])
            i += 2
        elif ch == "'":
            j = s.find("'", i + 1)
            if j < 0:
                raise ParseError('unterminated quote')
            buf.append(s[i:j + 1])
            i = j + 1
        elif ch == '$' and s[i + 1:i + 2] == "'":
            j, k = i + 2, i + 2
            while k < n and s[k] != "'":
                k += 2 if s[k] == '\\' else 1
            if k >= n:
                raise ParseError('unterminated $quote')
            buf.append("'" + _ansi(s[j:k]).replace("'", "'\\''") + "'")
            i = k + 1
        elif ch == '"':
            j = i + 1
            while j < n and s[j] != '"':
                if s[j] == '\\':
                    j += 1
                elif s[j] == '$' and s[j + 1:j + 2] == '(' and s[j + 2:j + 3] != '(':
                    e = _close(s, j)
                    subs.append(s[j + 2:e])
                    j = e
                elif s[j] == '`':
                    e = s.find('`', j + 1)
                    if e < 0:
                        raise ParseError('unclosed backtick')
                    subs.append(s[j + 1:e])
                    j = e
                j += 1
            if j >= n:
                raise ParseError('unterminated quote')
            buf.append(s[i:j + 1])
            i = j + 1
        elif ch == '$' and s[i + 1:i + 2] == '(':
            e = _close(s, i)
            if s[i + 2:i + 3] != '(':  # $(( )) is arithmetic, not a command
                subs.append(s[i + 2:e])
            buf.append(s[i:e + 1])
            i = e + 1
        elif ch == '`':
            e = s.find('`', i + 1)
            if e < 0:
                raise ParseError('unclosed backtick')
            subs.append(s[i + 1:e])
            buf.append(s[i:e + 1])
            i = e + 1
        elif ch == '<' and s.startswith('<<', i) and not s.startswith('<<<', i):
            m = re.match(r"<<-?\s*(?:'([^']+)'|\"([^\"]+)\"|(\\?\w+))", s[i:])
            if m:
                pend.append((m.group(1) or m.group(2) or m.group(3).lstrip('\\'), ''.join(buf)))
                i += m.end()
                buf.append(' ')
            else:
                buf.append('<<')
                i += 2
        elif ch == '\n':
            cut('\n')
            i += 1
            for word, head in pend:  # body is data, except when fed to a shell
                body = []
                while i < n:
                    j = s.find('\n', i)
                    line = s[i:] if j < 0 else s[i:j]
                    i = n if j < 0 else j + 1
                    if line.strip() == word:
                        break
                    body.append(line)
                if re.match(r'\s*(sudo\s+)?(\S*/)?(ba|z|da|k)?sh\b', head):
                    subs.append('\n'.join(body))
            pend = []
        elif ch == ';':
            cut(';'); i += 1
        elif ch in '()':
            cut(ch); i += 1
        elif ch == '|':
            k = 2 if s[i + 1:i + 2] in '|&' and s[i + 1:i + 2] else 1
            cut('|' if k == 1 or s[i + 1] == '&' else '||'); i += k
        elif ch == '&':
            if s[i + 1:i + 2] == '&':
                cut('&&'); i += 2
            elif (buf and buf[-1][-1:] in '<>') or s[i + 1:i + 2] == '>':
                buf.append(ch); i += 1  # 2>&1, >&2, &>file
            else:
                cut('&'); i += 1
        else:
            buf.append(ch); i += 1
    cut('')
    return segs, subs


# ---------------------------------------------------------------- option helpers
def _long(prefix, longs):
    """Resolve a long option name or its unique abbreviation (>= 3 chars, like git's parse-options)."""
    if prefix in longs:
        return prefix
    c = [x for x in longs if x.startswith(prefix)]
    return c[0] if len(prefix) >= 3 and len(c) == 1 else prefix


def _opts(args, longs):
    """-> (long names, short letters, positionals, saw '--'). Options after '--' are operands."""
    L, S, P, dd = set(), set(), [], False
    for a in args:
        if dd:
            P.append(a)
        elif a == '--':
            dd = True
        elif a.startswith('--'):
            L.add(_long(a[2:].split('=')[0], longs))
        elif a.startswith('-') and len(a) > 1:
            S.update(a[1:])
        else:
            P.append(a)
    return L, S, P, dd


def _w(s):
    return set(s.split())


GL = {
    'reset': _w('hard soft mixed merge keep quiet patch no-refresh refresh recurse-submodules pathspec-from-file pathspec-file-nul'),
    'checkout': _w('force detach orphan merge conflict ours theirs track no-track quiet progress no-progress patch '
                   'ignore-other-worktrees overlay no-overlay pathspec-from-file recurse-submodules guess no-guess'),
    'switch': _w('force discard-changes detach create force-create orphan guess no-guess merge track no-track quiet conflict '
                 'ignore-other-worktrees progress no-progress recurse-submodules'),
    'restore': _w('staged worktree source patch quiet progress no-progress ours theirs merge conflict ignore-unmerged overlay '
                  'no-overlay pathspec-from-file pathspec-file-nul recurse-submodules'),
    'clean': _w('force dry-run quiet interactive exclude'),
    'push': _w('force force-with-lease force-if-includes delete mirror all branches tags prune dry-run verbose quiet '
               'set-upstream thin no-thin follow-tags atomic signed push-option receive-pack repo porcelain progress '
               'no-verify verify recurse-submodules'),
    'branch': _w('delete force move copy list all remotes verbose quiet set-upstream-to unset-upstream track no-track '
                 'show-current contains no-contains merged no-merged sort format edit-description create-reflog'),
    'tag': _w('delete force list annotate sign local-user verify message file contains no-contains merged no-merged points-at sort format'),
    'rm': _w('force cached dry-run recursive quiet ignore-unmatch sparse pathspec-from-file pathspec-file-nul'),
    'worktree': _w('force detach lock reason quiet verbose expire'),
    'rebase': _w('abort continue skip quit interactive onto autosquash autostash'),
    'merge': _w('abort continue quit squash no-ff ff-only no-commit'),
    'rmcmd': _w('force interactive one-file-system no-preserve-root preserve-root recursive dir verbose help version'),
}
GIT_ARG_OPTS = {'-C', '-c', '--git-dir', '--work-tree', '--namespace', '--config-env', '--super-prefix', '--attr-source'}
# ---------------------------------------------------------------- secrets
SECRET_BASE = {'.npmrc', '.pypirc', '.netrc', '.git-credentials', 'id_rsa', 'id_ed25519', 'id_ecdsa'}
SECRET_EXT = ('.pem', '.key', '.keystore', '.kdbx')
ENV_OK = ('.example', '.sample', '.template', '.dist')
SECRET_HOME = [('.ssh', 'ssh'), ('.aws', 'aws'), ('.gcp', 'gcp'), ('.config/gcloud', 'gcloud'), ('.kube/config', 'kube'),
               ('.docker/config.json', 'docker'), ('.config/gh/hosts.yml', 'gh'), ('.claude/.credentials.json', 'claude'),
               ('.codex/auth.json', 'codex'), ('.gemini/oauth_creds.json', 'gemini')]


def _real(x):
    """realpath with '/' separators, so the prefix checks below also hold on Windows (D:\\a -> D:/a)."""
    return os.path.realpath(x).replace(os.sep, '/')


def _home():
    return _real(os.path.expanduser('~'))


def _secret(tok):
    """rule-id when tok names a credentials file, else None. Templates like .env.example are allowed."""
    for t in {tok, tok.split('=', 1)[-1]}:
        t = t.lstrip('@')
        if not t or re.search(r'\s', t) or '://' in t:
            continue
        h = _home()
        t = t.replace('${HOME}', h).replace('$HOME', h)
        if t.startswith('~'):
            t = os.path.expanduser(t)
        base = os.path.basename(t.rstrip('/'))
        if base == '.env' or (base.startswith('.env.') and not base.endswith(ENV_OK)):
            return 'secret.basename.env'
        if base in SECRET_BASE:
            return 'secret.basename.' + base.lstrip('.')
        if base == 'credentials' and '/' in t:
            return 'secret.basename.credentials'
        if base.endswith(SECRET_EXT):
            return 'secret.ext.' + base.rsplit('.', 1)[1]
        p = os.path.normpath(t).replace(os.sep, '/')
        for rel, nm in SECRET_HOME:
            for root in (h, _real(os.path.expanduser('~'))):  # HOME may be a symlink
                d = root.rstrip('/') + '/' + rel
                if p == d or p.startswith(d + '/'):
                    return 'secret.home.' + nm
    return None


# ---------------------------------------------------------------- rm
def _temp_roots():
    r = {'/tmp', '/var/tmp', '/private/tmp', '/private/var/tmp'}
    if os.environ.get('TMPDIR'):
        r.add(_real(os.environ['TMPDIR']).rstrip('/'))
    return r | {_real(x).rstrip('/') for x in r}  # Windows: /tmp resolves to D:/tmp


def _under(p, roots):
    return any(p.startswith(r.rstrip('/') + '/') for r in roots)


def _braces(t, n=0):
    """Expand {a,b} so `{/,build}` is checked as each real operand."""
    m = re.search(r'(?<!\$)\{([^{}]*,[^{}]*)\}', t)
    if not m or n > 3:
        return [t]
    return [y for x in m.group(1).split(',')[:32] for y in _braces(t[:m.start()] + x + t[m.end():], n + 1)]


def _rm_target(t, cwd, at=''):
    """Verdict for one recursive-rm operand, or None when it is inside cwd or a temp dir."""
    h = _home()
    m = re.match(r'^\$\{?TMPDIR\}?(/.*)$', t)
    if m and '..' not in m.group(1).split('/'):
        return None
    t = t.replace('${HOME}', h).replace('$HOME', h)
    if '$' in t or '`' in t:
        return B('rm.dynamic-target', 'rm -r on a path built from a variable or substitution; the target cannot be checked.')
    if t.startswith('~'):
        t = os.path.expanduser(t)
    parts = t.split('/')
    gi = next((k for k, x in enumerate(parts) if re.search(r'[*?\[]', x)), None)
    glob = gi is not None
    base = '/'.join(parts[:gi]) if glob else t
    base = base or ('/' if t.startswith('/') else '.')
    if at is None and not os.path.isabs(base):
        return B('rm.dynamic-target', 'rm -r after a cd whose destination cannot be checked.')
    p = _real(os.path.join(at or cwd, base))
    c = _real(cwd)
    if os.path.dirname(p) == p:  # / or a drive root such as D:/
        return B('rm.root-or-home' if glob else 'rm.root', 'rm -r on the filesystem root.')
    if p == h or h.startswith(p + '/'):
        return B('rm.root-or-home', 'rm -r on the home directory or a parent of it.')
    if '.git' in p.split('/'):
        return B('rm.git-metadata', 'rm -r on .git metadata destroys repository history.')
    if p == c:
        return None if glob else B('rm.cwd-self', 'rm -r on the current directory itself.')
    if p.startswith(c + '/') or _under(p, _temp_roots()) or (glob and p in _temp_roots()):
        return None
    return B('rm.outside-cwd', 'rm -r outside the current working directory. Use a path inside the project or /tmp.')


# ---------------------------------------------------------------- git
def _git(a, ctx):
    al, i = {}, 0
    while i < len(a) and a[i].startswith('-'):
        if a[i] in GIT_ARG_OPTS:
            if a[i] == '-c' and i + 1 < len(a):
                k, _, v = a[i + 1].partition('=')
                if k.startswith('alias.'):
                    al[k[6:]] = v
            i += 2
        else:
            i += 1
    if i >= len(a):
        return None
    sub, rest = a[i], a[i + 1:]
    if sub in al:
        v = al[sub]
        if v.startswith('!'):
            return _text(v[1:] + ' ' + ' '.join(shlex.quote(x) for x in rest), ctx)
        return _git(shlex.split(v) + rest, ctx)
    cwd = ctx['cwd']
    if sub in GL:
        L, S, P, dd = _opts(rest, GL[sub])
    else:
        L, S, P, dd = _opts(rest, set())
    if sub == 'reset':
        if 'hard' in L:
            return B('git.reset-hard', "git reset --hard destroys uncommitted changes. Use 'git stash' first.")
        if 'merge' in L:
            return B('git.reset-merge', "git reset --merge can lose uncommitted changes. Use 'git stash' first.")
    elif sub == 'checkout':
        if dd:
            return B('git.checkout-double-dash', "git checkout -- <path> discards local changes. Use 'git stash' first.")
        if 'force' in L or 'f' in S:
            return B('git.checkout-force', "git checkout --force discards local changes. Use 'git stash' first.")
        if S & {'b', 'B'} or 'orphan' in L or P == ['-']:
            return None
        if len(P) >= 2 or (P and (P[0] in ('.', '..') or os.path.exists(os.path.join(cwd, P[0])))):
            return B('git.checkout-ambiguous', "git checkout with a path-like operand can discard changes. Use 'git switch' for branches.")
    elif sub == 'switch':
        if 'discard-changes' in L:
            return B('git.switch-discard-changes', "git switch --discard-changes drops local changes. Use 'git stash' first.")
        if ('force' in L or 'f' in S) and 'force-create' not in L:
            return B('git.switch-force', "git switch --force drops local changes. Use 'git stash' first.")
    elif sub == 'restore':
        if 'worktree' in L or 'W' in S:
            return B('git.restore-worktree', "git restore --worktree discards working-tree changes. Use 'git stash' first.")
        if not ('staged' in L or 'S' in S):
            return B('git.restore-unstaged', "git restore discards unstaged changes. Use 'git stash' first.")
    elif sub == 'clean':
        if ('force' in L or 'f' in S) and not ('dry-run' in L or 'n' in S):
            return B('git.clean-force', 'git clean -f deletes untracked files for good. Run git clean -n first.')
    elif sub == 'push':
        refs = P[1:]
        if 'force' in L or 'f' in S or any(r.startswith('+') or ':+' in r for r in refs):
            return B('git.push-force', 'Force push rewrites remote history. Use --force-with-lease.')
        if 'delete' in L or 'd' in S or any(r.startswith(':') for r in refs):
            return B('git.push-delete', 'git push --delete removes a remote branch or tag.')
        if 'mirror' in L:
            return B('git.push-mirror', 'git push --mirror overwrites every remote ref.')
    elif sub == 'stash' and P[:1] == ['drop']:
        return B('git.stash-drop', 'git stash drop loses saved work.')
    elif sub == 'stash' and P[:1] == ['clear']:
        return B('git.stash-clear', 'git stash clear loses all saved work.')
    elif sub == 'branch':
        if ('delete' in L or S & {'d', 'D'}) and ('force' in L or S & {'f', 'D'}):
            return B('git.branch-force-delete', 'Force-deleting a branch can lose unmerged commits. Use git branch -d.')
    elif sub == 'tag' and ('delete' in L or 'd' in S):
        return B('git.tag-delete', 'Deleting a tag can lose a release pointer.')
    elif sub == 'reflog' and P[:1] and P[0] in ('delete', 'expire'):
        return B('git.reflog-delete', 'git reflog delete/expire removes recovery points.')
    elif sub == 'rebase' and 'abort' in L:
        return B('git.rebase-abort', 'git rebase --abort drops the in-progress rebase work.')
    elif sub == 'merge' and 'abort' in L:
        return B('git.merge-abort', 'git merge --abort drops in-progress merge changes.')
    elif sub == 'rm':
        if ('force' in L or 'f' in S) and not ('cached' in L or 'dry-run' in L or 'n' in S):
            return B('git.rm-force', 'git rm -f deletes files without the safety check. Use --cached or commit first.')
    elif sub == 'worktree' and P[:1] == ['remove'] and ('force' in L or 'f' in S):
        return B('git.worktree-remove-force', 'git worktree remove --force can lose uncommitted work.')
    return None


# ---------------------------------------------------------------- wrappers and commands
def _skip_opts(a, argset=()):
    i = 0
    while i < len(a):
        if a[i] == '--':
            return a[i + 1:]
        if not a[i].startswith('-'):
            break
        i += 2 if a[i] in argset else 1
    return a[i:]


def _eval_text(s, ctx):
    """Re-analyse code handed to a shell/eval; block text whose source is unknown (variable, fetched output)."""
    m = re.match(r'\s*\$\((.*)\)\s*$', s, re.S)
    if m:
        w = shlex.split(m.group(1))[:1] if m.group(1).strip() else []
        if w and os.path.basename(w[0]) in FETCH:
            return B('analysis.dynamic-shell-source', 'Shell code taken from fetched or file output cannot be checked.')
        return None  # command substitution already analysed as its own segment
    if re.match(r'\s*(`|\$[A-Za-z_{@*#0-9])', s):
        return B('analysis.dynamic-shell-source', 'Shell code taken from a variable cannot be checked.')
    return _text(s, ctx)


def _text(s, ctx):
    """Analyse nested shell text in the caller's directory."""
    return analyze_text(s, ctx['cwd'], ctx['depth'] + 1, ctx.get('piped', False), ctx)


def _interp(code, ctx):
    """python -c / node -e / perl -e / ruby -e: re-analyse the code and every quoted literal as shell text."""
    v = None
    try:
        v = _text(code, dict(ctx, piped=False))
    except ParseError:
        pass
    if v:
        return v
    for m in re.finditer(r"'([^'\n]*)'|\"([^\"\n]*)\"", code):
        lit = m.group(1) or m.group(2) or ''
        if _secret(lit):
            return B(_secret(lit), 'Interpreter code reads a credentials file.')
        try:
            v = _text(lit, dict(ctx, piped=False))
        except ParseError:
            continue
        if v:
            return B('interpreter.dangerous-command', 'Interpreter code runs a destructive command (%s).' % v[0])
    return None


def run(t, ctx):
    """Verdict (rule_id, reason) for one tokenised simple command, or None. Unwraps sudo/env/xargs/bash -c/..."""
    if ctx['depth'] > MAX_DEPTH:
        return B('analysis.depth', 'Command nesting is too deep to analyse.')
    hard, env = _on('safety_net'), {}
    while True:
        while t and (re.match(r'^[A-Za-z_]\w*=', t[0]) or t[0] in KEYWORDS):
            k, eq, val = t[0].partition('=')
            if eq:
                env[k] = val
            t = t[1:]
        if not t:
            return None
        c, a = os.path.basename(t[0]), t[1:]
        if c in ('sudo', 'doas'):
            t = _skip_opts(a, {'-u', '-g', '-h', '-p', '-C', '-r', '-t', '-T', '-U', '-D'})
        elif c == 'env':
            i = 0
            while i < len(a) and (a[i].startswith('-') or '=' in a[i]):
                k, eq, val = a[i].partition('=')
                if eq and not k.startswith('-'):
                    env[k] = val
                i += 2 if a[i] in ('-u', '-C', '-S', '--unset', '--chdir') else 1
            t = a[i:]
        elif c == 'command':
            if any(x in ('-v', '-V') for x in a[:2]):
                return None
            t = _skip_opts(a)
        elif c == 'exec':
            t = _skip_opts(a, {'-a'})
        elif c == 'nice':
            t = _skip_opts(a, {'-n'})
        elif c == 'timeout':
            a = _skip_opts(a, {'-s', '-k', '--signal', '--kill-after'})
            t = a[1:]
        elif c in ('time', 'nohup', 'setsid', 'builtin'):
            t = _skip_opts(a) if c == 'time' else a
        elif hard and c in WRAPPERS:
            t = _skip_opts(a, WRAPPERS[c])
        elif hard and c in ('chrt', 'taskset'):  # one priority / mask operand before the command
            r = _skip_opts(a, {'-c'} if c == 'taskset' else set())
            t = r if c == 'taskset' and '-c' in a else r[1:]
        elif hard and c == 'flock':
            r = _skip_opts(a, {'-w', '-E', '--timeout', '--conflict-exit-code'})[1:]
            if r[:1] == ['-c'] and len(r) > 1:
                return _eval_text(r[1], ctx)
            t = r
        else:
            break
    if TRACE is not None:
        TRACE.append({'depth': ctx['depth'], 'dir': ctx.get('at', ctx['cwd']), 'tokens': list(t)})
    v = _builtin(c, a, t, ctx, hard)
    if v or not (_on('safety_extra') or _on('safety_strict') or _on('custom_rules')):
        return v
    import tzrules
    return tzrules.check(t, env, ctx)


def _parallel(a, ctx):
    """GNU parallel: literal ::: inputs are checked one by one; piped input to rm -r or a shell is blocked."""
    i = 0
    while i < len(a) and a[i].startswith('-') and a[i] != '--':
        i += 2 if a[i] in ('-j', '-P', '-I', '-S', '-a', '--jobs', '--colsep', '--arg-file', '--sshlogin') else 1
    rest = a[i + 1:] if a[i:i + 1] == ['--'] else a[i:]
    cut = next((k for k, x in enumerate(rest) if x.startswith(':::')), len(rest))
    inner, fed = rest[:cut], [x for x in rest[cut:] if not x.startswith(':::')]
    if not inner:
        if ctx.get('piped'):
            return B('parallel.command-stream-dynamic', 'parallel runs commands read from input; they cannot be checked.')
        for x in fed:
            v = _text(x, ctx)
            if v:
                return v
        return None
    base = os.path.basename(inner[0])
    if ctx.get('piped') or cut == len(rest):
        L, S, P, dd = _opts(inner[1:], GL['rmcmd'])
        if base == 'rm' and ('recursive' in L or S & set('rR')):
            return B('parallel.rm-recursive-force-dynamic', 'parallel rm -r deletes whatever its input names.')
        if base in SHELLS:
            return B('parallel.shell-dynamic', 'parallel feeding a shell runs unchecked input.')
    words = [x for x in inner if x != '{}'] + fed
    return run(words, dict(ctx, depth=ctx['depth'] + 1))


def _builtin(c, a, t, ctx, hard):
    """Default rules for one unwrapped command."""
    if c in ECHO:
        return None
    for x in a:  # credentials are never read through any command (templates like .env.example are fine)
        r = _secret(x)
        if not r and hard and c == 'git' and ':' in x and '://' not in x:
            r = _secret(x.split(':', 1)[1])  # git show HEAD:.env
        if r:
            return B(r, 'Touches a credentials file (%s). Ask the owner first.' % x)
    if re.search(r'\b(DROP\s+(TABLE|DATABASE)|TRUNCATE\s+TABLE)\b', ' '.join(t), re.I):
        return B('sql.drop', 'drops data')
    if c == 'git':
        return _git(a, ctx)
    if c == 'rm':
        L, S, P, dd = _opts(a, GL['rmcmd'])
        if not ('recursive' in L or S & set('rR')):
            return None
        if ctx.get('xargs'):
            return B('xargs.rm-recursive-force-dynamic', 'xargs rm -r deletes whatever its input names.')
        if ctx.get('fexec'):
            return B('find.exec-rm', 'find -exec rm -r removes files in bulk.')
        for x in [y for p in P for y in (_braces(p) if hard else [p])]:
            v = _rm_target(x, ctx['cwd'], ctx.get('at', ''))
            if v:
                return v
        return None
    if c in SHELLS:
        ci, j = None, 0
        while j < len(a):
            x = a[j]
            if re.match(r'^-[A-Za-z]*c[A-Za-z]*$', x):
                ci = j
                break
            if hard and x in ('-o', '+o', '-O', '+O', '--rcfile', '--init-file'):
                j += 2  # these take a value, so `bash -o pipefail -c ..` still reaches -c
                continue
            if x == '--' or not x.startswith('-'):
                break
            j += 1
        if ci is None:
            if hard and ctx.get('stdin') is not None and j >= len(a):
                return _eval_text(ctx['stdin'], dict(ctx, stdin=None))
            if ctx.get('xargs'):
                return B('xargs.shell-dynamic', 'xargs feeding a shell runs unchecked input.')
            if ctx.get('piped'):
                return B('analysis.dynamic-shell-source', 'Piping text into a shell runs it unchecked.')
            return None
        if ci + 1 >= len(a):
            return B('xargs.shell-dynamic', 'xargs feeding a shell runs unchecked input.') if ctx.get('xargs') else None
        return _eval_text(a[ci + 1], ctx)
    if c == 'eval':
        return _eval_text(' '.join(a), ctx)
    if hard and c == 'su':
        code = next((a[k + 1] for k, x in enumerate(a[:-1]) if x in ('-c', '--command')), None)
        return _eval_text(code, ctx) if code is not None else None
    if hard and c == 'parallel':
        return _parallel(a, ctx)
    if c == 'xargs':
        i = 0
        while i < len(a) and a[i].startswith('-') and a[i] != '--':
            i += 2 if a[i] in ('-I', '-n', '-P', '-L', '-s', '-d', '-E', '-a', '-J') else 1
        inner = a[i + 1:] if a[i:i + 1] == ['--'] else a[i:]
        return run(inner, dict(ctx, xargs=True, depth=ctx['depth'] + 1)) if inner else None
    if c == 'find':
        return _find(a, ctx)
    if re.match(r'^(python[\d.]*|node(js)?|perl|ruby)$', c):
        for j, x in enumerate(a[:-1]):
            if x in ('-c', '-e', '-E', '-p') or re.match(r'^-[a-zA-Z]*[ce]$', x):
                return _interp(a[j + 1], ctx)
        return None
    if c == 'dd' and any(re.match(r'^of=/dev/(sd|nvme|disk|rdisk|hd|mmcblk|vd|loop)', x) for x in a):
        return B('dd.device-write', 'dd writing to a raw device destroys its contents.')
    if c.startswith('mkfs') and any(x.startswith('/dev/') for x in a):
        return B('mkfs.device', 'mkfs on a device erases it.')
    if c == 'shred':
        return B('shred.target', 'shred destroys file contents.')
    if c == 'chmod' and (('-R' in a) or '--recursive' in a) and any(re.match(r'^0?(777|000)$', x) for x in a):
        return B('chmod.recursive', 'recursive chmod 777/000 breaks permissions.')
    if c == 'rsync' and any(x.startswith('--delete') for x in a) and not any(x in ('--dry-run', '-n') for x in a):
        return B('rsync.delete', 'rsync --delete removes destination files.')
    j = ' '.join(a)
    if (c == 'diskutil' and re.search(r'erase|partition|apfs\s+delete', j)) or (c == 'wipefs' and re.search(r'(^|\s)-[ao]|--all', j)) \
            or c == 'sgdisk' or (c == 'parted' and re.search(r'mklabel|\brm\b|mkpart', j)):
        return B('disk.erase', 'erases or repartitions a disk')
    return None


def _find(a, ctx):
    paths = []
    for x in a:
        if x.startswith('-') or x in ('(', '!'):
            break
        paths.append(x)
    h = _home()
    safe_p = bool(paths) and all(_under(_real(os.path.join(ctx['cwd'], p)), _temp_roots()) for p in paths)
    if '-delete' in a and not safe_p:
        return B('find.delete', 'find -delete removes files in bulk.')
    for k, x in enumerate(a):
        if x in ('-exec', '-execdir', '-ok', '-okdir'):
            e = next((j for j in range(k + 1, len(a)) if a[j] in (';', '+')), len(a))
            if not safe_p:
                v = run(a[k + 1:e], dict(ctx, fexec=True, depth=ctx['depth'] + 1))
                if v:
                    return v
    return None


# ---------------------------------------------------------------- entry points
_REDIR = re.compile(r'^\d*(>>?|<<?<?|&>>?|>&|<&)')
_DISK = re.compile(r'^(/dev/(sd|nvme|disk|rdisk|hd)\w*)')


def _strip_redirects(toks, ins=None):
    """Drop redirections; a redirect onto a raw disk device is itself a verdict. `ins` collects (op, source) pairs."""
    out, i = [], 0
    while i < len(toks):
        m = _REDIR.match(toks[i])
        if not m:
            out.append(toks[i]); i += 1
            continue
        tgt = toks[i][m.end():] or (toks[i + 1] if i + 1 < len(toks) else '')
        if m.group(1).startswith('>') and _DISK.match(tgt):
            return None, B('redirect.block-device', 'redirect onto a raw disk device')
        if ins is not None and m.group(1) in ('<', '<<<'):
            ins.append((m.group(1), tgt))
        i += 1 if toks[i][m.end():] else 2
    return out, None


def _chdir(toks, at, stack):
    """Directory after a cd/pushd/popd segment; None = cannot be known. Other commands leave it unchanged."""
    while toks and (toks[0] in KEYWORDS or toks[0] in ('builtin', 'command')):
        toks = toks[1:]
    if not toks or toks[0] not in ('cd', 'pushd', 'popd'):
        return at
    if toks[0] == 'popd':
        return stack.pop() if stack else None
    if toks[0] == 'pushd':
        stack.append(at)
    args = [x for x in toks[1:] if x == '-' or not x.startswith('-')]
    d = args[0] if args else '~'
    d = os.path.expanduser(d.replace('${HOME}', '~').replace('$HOME', '~'))
    if d == '-' or re.search(r'[$`*?]', d) or (at is None and not os.path.isabs(d)):
        return None
    return os.path.normpath(os.path.join(at or '/', d))


def _stdin_check(ins):
    """`cat < .env` reads the secret even though the path is not an argument."""
    for op, src in ins:
        if op == '<':
            r = _secret(src)
            if not r and _on('safety_extra'):
                import tzrules
                r = tzrules.secret_extra(src)
            if r:
                return B(r, 'Reads a credentials file (%s) through a redirect. Ask the owner first.' % src)
    return None


def analyze_text(s, cwd, depth=0, piped=False, parent=None):
    """First verdict (rule_id, reason) for shell text, or None. Raises ParseError when it cannot be parsed."""
    if depth > MAX_DEPTH:
        return B('analysis.depth', 'Command nesting is too deep to analyse.')
    segs, subs = scan(s)
    hard = _on('safety_net')
    at = (parent or {}).get('at', cwd)
    for sub in subs:
        v = analyze_text(sub, cwd, depth + 1, parent={'at': at})
        if v:
            return v
    dirs, groups = [], []  # pushd stack; directories saved at each open subshell
    for text, op in segs:
        closed = 0
        while hard and text.startswith('(') and not text.startswith('(('):
            groups.append(at)
            text = text[1:].lstrip()
        while closed < len(groups) and text.endswith(')') and text.count(')') > text.count('('):
            text = text[:-1].rstrip()
            closed += 1
        try:
            toks = shlex.split(text, posix=True)
        except ValueError as e:
            raise ParseError(str(e))
        ins = []
        toks, v = _strip_redirects(toks, ins)
        v = v or (_stdin_check(ins) if hard else None)
        if v:
            return v
        here = next((src for o, src in ins if o == '<<<'), None)
        v = run(toks, {'cwd': cwd, 'at': at, 'depth': depth, 'stdin': here,
                       'piped': op == '|' or (piped and op == '')})
        if v:
            return v
        if hard:
            at = _chdir(toks, at, dirs)
        for _ in range(closed):
            at = groups.pop()
    return None


RAW = re.compile(r'\brm\s+(-\S+\s+)*-\w*[rR]|\brm\s+--recursive|\bgit\s+(reset\s+--hard|clean\s+-\w*f|push\b.*(-f\b|--force\b))')


def analyze(cmd, cwd=None):
    """(ok, reason, rule_id), or None when unparseable and the raw text shows nothing dangerous."""
    cwd = cwd or os.getcwd()
    try:
        v = analyze_text(cmd, cwd)
    except ParseError:
        if RAW.search(cmd):
            return (False, 'Could not parse the command and its raw text looks destructive (fail closed).',
                    'raw-text.dangerous-command')
        return None
    return (False, v[1], v[0]) if v else (True, '', '')
