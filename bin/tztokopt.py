#!/usr/bin/env python3
# Delta re-read: when a file read earlier in this chat has changed a little, answer the next full Read with the diff only.
# Independent TOKEN ZOMBIE design. Idea source: the public README of alexgreensh/token-optimizer (PolyForm Noncommercial);
# no code or wording reused. Opt-in (feature 'read_delta', default off) because it denies a Read. Each change is
# answered once: repeating the same Read always goes through.
import difflib, hashlib, json, os, re, sys
from tzlib import feature

MIN_CHARS = 2000      # smaller files: a full re-read is cheap
MAX_CHARS = 20000     # above tzout READ_MAX the earlier result may have been trimmed
MAX_LINES = 2000      # Read's default window; longer files were never seen whole
MAX_LINE = 2000       # Read cuts longer lines
MAX_DIFF = 1500
KEEP = 50             # snapshots per session
_SECRET = re.compile(r'(^|/)(\.env[^/]*|\.netrc|\.npmrc|\.pypirc|id_(rsa|dsa|ecdsa|ed25519)[^/]*|[^/]*(secret|credential|token|passw)[^/]*|[^/]*\.(pem|key|p12|pfx))$|/\.(ssh|aws|gnupg)/', re.I)


def _path(sid):
    d = os.path.join(os.path.expanduser('~'), '.claude', 'token-zombie')
    return os.path.join(d, 'delta-%s.json' % re.sub(r'[^A-Za-z0-9_-]', '_', str(sid))[:60])


def _load(sid):
    try:
        with open(_path(sid), encoding='utf-8') as f:
            v = json.load(f)
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(sid, st):
    p = _path(sid)
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = '%s.%d' % (p, os.getpid())
        with os.fdopen(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w', encoding='utf-8') as f:
            json.dump(st, f)
        os.replace(tmp, p)
        return True
    except OSError:
        return False


def _target(payload):
    """(session, absolute path) for a whole-file Read in the main chat, else None."""
    ti = payload.get('tool_input') or {}
    fp, sid = ti.get('file_path'), payload.get('session_id')
    if payload.get('tool_name') != 'Read' or not sid or not isinstance(fp, str) or not os.path.isabs(fp):
        return None
    if any(ti.get(k) not in (None, '') for k in ('offset', 'limit', 'pages')) or payload.get('agent_id'):
        return None  # partial reads; sub-agents have their own context and never saw the parent's copy
    if _SECRET.search(fp) or _SECRET.search(os.path.realpath(fp)):
        return None
    return str(sid), fp


def _text(fp):
    """File text if Read would have shown all of it, else None."""
    try:
        if not os.path.isfile(fp) or os.path.getsize(fp) > MAX_CHARS * 4:
            return None
        with open(fp, 'rb') as f:
            s = f.read().decode('utf-8')
    except (OSError, UnicodeDecodeError):
        return None
    lines = s.splitlines()
    if not MIN_CHARS <= len(s) <= MAX_CHARS or '\0' in s or len(lines) > MAX_LINES or any(len(x) > MAX_LINE for x in lines):
        return None
    return s


def remember(payload):
    """PostToolUse on a successful Read: snapshot what the chat now holds. Returns True if stored."""
    t = _target(payload)
    if not t:
        return False
    sid, fp = t
    st = _load(sid)
    had = st.pop(fp, None)
    s = _text(fp)
    if s is not None:
        st[fp] = s
        while len(st) > KEEP:
            st.pop(next(iter(st)))
    return _save(sid, st) if (s is not None or had is not None) else False


def make_diff(old, new, name='file'):
    """Unified diff (2 context lines) if it is small enough to be worth sending instead of the file, else None."""
    a, b = old.splitlines(), new.splitlines()
    d = '\n'.join(difflib.unified_diff(a, b, name + ' (read earlier)', name + ' (now)', n=2, lineterm=''))
    return d if d and len(d) <= min(MAX_DIFF, len(new) // 2) else None


def delta(payload):
    """PreToolUse on Read: deny reason carrying the diff, or None to let the Read run."""
    t = _target(payload)
    if not t:
        return None
    sid, fp = t
    st = _load(sid)
    old, new = st.get(fp), _text(fp)
    if old is None or new is None or old == new:
        return None
    d = make_diff(old, new, os.path.basename(fp))
    if d is None:
        return None
    st[fp] = new
    if not _save(sid, st):  # cannot record that this was served: never risk denying twice
        return None
    return ('[TOKEN ZOMBIE read delta] %s changed since you read it earlier in this chat. Only the changes are below; '
            'the rest is as you saw it. For the whole file (also needed if Edit reports the file was modified), '
            'run the same Read again.\n%s' % (fp, d))


def reset(sid):
    """Call after compaction or /clear: earlier reads are no longer in context."""
    try:
        os.remove(_path(sid))
        return True
    except OSError:
        return False


def advise(payload):
    """Gated hook entry: PreToolUse -> deny reason or None; PostToolUse -> records, returns None."""
    if not feature('read_delta'):
        return None
    if payload.get('hook_event_name') == 'PostToolUse':
        remember(payload)
        return None
    return delta(payload)


def main(argv):
    if len(argv) == 3 and argv[0] == 'diff':
        try:
            old, new = (open(p, encoding='utf-8').read() for p in argv[1:])
        except (OSError, UnicodeDecodeError) as e:
            print('tz delta: %s' % e, file=sys.stderr)
            return 2
        d = make_diff(old, new, os.path.basename(argv[2]))
        print(d if d else ('no change' if old == new else 'diff too large: read the whole file'))
        return 0
    if len(argv) == 2 and argv[0] == 'reset':
        print('cleared' if reset(argv[1]) else 'nothing stored')
        return 0
    print('usage: tz delta diff OLD NEW | tz delta reset SESSION_ID', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
