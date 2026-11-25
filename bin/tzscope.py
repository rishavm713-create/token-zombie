#!/usr/bin/env python3
"""Authorized-scope check: is a network host one this project declared it may touch?
Host matching adapted from elementalsouls/Claude-BugHunter engine/scope.py (MIT, Copyright (c) 2026 Sachin Sharma), see NOTICE.
Defensive only: it parses strings and never opens a connection. Deny wins, default deny.

Scope file .tz/scope.json: {"in_scope": ["example.com", "*.example.org", "10.0.0.0/8", "re:^ci[0-9]+\\.corp\\.net$"],
                            "out_of_scope": ["admin.example.com"]}
"""
import argparse, ipaddress, json, os, re, shlex, sys
from urllib.parse import urlsplit

FILE = os.path.join('.tz', 'scope.json')


def host_of(target):
    """Lower-case host of a URL or host[:port]; '' when absent or ambiguous."""
    t = target.strip()
    if '\\' in t or any(c.isspace() for c in t):
        return ''   # clients disagree on these ('http://a.com\\@b.com'), so fail closed
    try:
        return str(ipaddress.ip_address(t.strip('[]')))   # bare IP, incl. unbracketed IPv6
    except ValueError:
        pass
    try:
        return (urlsplit(t if '://' in t else '//' + t).hostname or '').rstrip('.')
    except ValueError:
        return ''


def _rule(raw):
    """One rule as (kind, value). Raises ValueError: a rule that cannot match must not be silently dropped."""
    r = raw.strip()
    if r[:3].lower() == 're:':
        try:
            return 're', re.compile(r[3:], re.I)
        except re.error as e:
            raise ValueError(f'bad regex rule {raw!r}: {e}')
    try:
        return 'net', ipaddress.ip_network(r, strict=False)
    except ValueError:
        pass
    body = r.split('://', 1)[-1]
    wild = body.startswith('*.')
    host = host_of(body[2:] if wild else body)   # scheme, userinfo, port and path are dropped: scope is per host
    if not host or '*' in host:
        raise ValueError(f'unusable scope rule {raw!r}')
    return ('wild' if wild else 'host'), host


def _match(rule, host):
    kind, v = rule
    if kind == 're':
        return v.search(host) is not None
    if kind == 'net':
        try:
            return ipaddress.ip_address(host) in v
        except ValueError:
            return False
    if kind == 'wild':
        return host.endswith('.' + v)
    return host == v or host.endswith('.' + v)


def compile_scope(data):
    if not isinstance(data, dict):
        raise ValueError('scope must be a JSON object')
    out = []
    for key in ('in_scope', 'out_of_scope'):
        v = data.get(key, [])
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            raise ValueError(f'{key} must be a list of strings')
        out.append([_rule(x) for x in v if x.strip()])
    return tuple(out)


def reject_reason(scope, target):
    """None when in scope, else why not."""
    allow, deny = scope
    host = host_of(target)
    if not host:
        return 'could not parse host'
    if any(_match(r, host) for r in deny):
        return f'{host} matches an out-of-scope rule'
    if not any(_match(r, host) for r in allow):
        return f'{host} matches no in-scope rule (default deny)'
    return None


def find_scope(start):
    d = os.path.abspath(start)
    while True:
        p = os.path.join(d, FILE)
        if os.path.isfile(p):
            return p
        up = os.path.dirname(d)
        if up == d:
            return None
        d = up


def load(path):
    with open(path, encoding='utf-8') as f:
        return compile_scope(json.load(f))


# curl/wget flags whose next word is a value, not a target
VALUE_FLAGS = set('-o -H -d -F -u -A -e -b -c -T -X -m -w -K -E -P -U --output --header --data --data-raw --data-binary --form --user --user-agent --referer --cookie --cookie-jar --upload-file --request --max-time --write-out --config --cert --key --cacert --connect-timeout --retry --output-document --directory-prefix'.split())
WGET_BOOL = {'-b', '-c', '-d', '-m', '-E', '-K'}
URL = re.compile(r'^(?:https?|wss?|ftps?)://', re.I)
HOSTLIKE = re.compile(r'^(?:[^/@\s]+@)?(?:(?:[a-z0-9_-]+\.)+[a-z]{2,}|(?:\d{1,3}\.){3}\d{1,3})(?::\d+)?(?:[/?#].*)?$', re.I)


def targets_in(command):
    """Best-effort targets of curl/wget calls. Not a shell parser: variables, scripts and other clients are not seen."""
    try:
        lex = shlex.shlex(command.replace('\\\n', ' ').replace('\n', ' ; '), posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        words = list(lex)
    except ValueError:
        return []
    found, tool, skip = [], None, False
    for w, prev in zip(words, [''] + words):
        if w and set(w) <= set('();<>|&'):
            if '<' in w or '>' in w:
                skip = True   # a redirect operand is a file; the same call continues
            else:
                tool, skip = None, False
        elif skip:
            skip = False
            if tool and URL.match(w) and prev not in ('-e', '--referer', '-x'):
                found.append(w)   # still checked: a valueless flag must not hide a URL
        elif tool is None:
            if os.path.basename(w) in ('curl', 'wget'):
                tool = os.path.basename(w)
        elif w in VALUE_FLAGS and not (tool == 'wget' and w in WGET_BOOL):
            skip = True
        elif w.startswith('--url='):
            found.append(w[6:])
        elif URL.match(w) or (not w.startswith('-') and HOSTLIKE.match(w)):
            found.append(w)
    return found


def _loopback(host):
    if host == 'localhost' or host.endswith('.localhost'):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def advise(payload):
    """PreToolUse payload -> advice string or None. Silent without a scope file; advice only, never blocks."""
    if payload.get('tool_name') != 'Bash':
        return None
    cmd = (payload.get('tool_input') or {}).get('command') or ''
    targets = targets_in(cmd)
    path = targets and find_scope(payload.get('cwd') or os.getcwd())
    if not path:
        return None
    try:
        scope = load(path)
    except (OSError, ValueError) as e:
        return f'TZ scope: {path} is unreadable ({e}); treat all network targets as out of scope until fixed.'
    bad = []
    for t in targets:
        if not _loopback(host_of(t)):
            why = reject_reason(scope, t)
            if why and why not in bad:
                bad.append(why)
    if bad:
        return f'TZ scope: outside authorized scope ({path}): {"; ".join(bad[:3])}. Ask the owner before contacting it.'
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(prog='tz scope', description='authorized-scope check (deny wins, default deny)')
    ap.add_argument('targets', nargs='+', help='hosts or URLs')
    ap.add_argument('--file', help='scope JSON (default: nearest .tz/scope.json)')
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return e.code
    path = a.file or find_scope(os.getcwd())
    if not path:
        print(f'scope: no {FILE} found', file=sys.stderr)
        return 2
    try:
        scope = load(path)
    except (OSError, ValueError) as e:
        print(f'scope: {path}: {e}', file=sys.stderr)
        return 2
    rc = 0
    for t in a.targets:
        why = reject_reason(scope, t)
        print(f'OUT-OF-SCOPE {t} ({why})' if why else f'IN-SCOPE {t}')
        rc = 1 if why else rc
    return rc


if __name__ == '__main__':
    sys.exit(main())
