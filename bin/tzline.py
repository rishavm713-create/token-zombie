#!/usr/bin/env python3
# Configurable status line: lines of widgets from ~/.claude/token-zombie/line.json, fed by the Claude Code status JSON.
# Widget behaviour, settings format and algorithms adapted from sirmalloc/ccstatusline src/utils, src/widgets
# (MIT, Copyright (c) 2025 Matthew Breedlove), ported to stdlib Python; see NOTICE.
# No network, no credentials: every value comes from the status JSON, the chat log, local git or the local machine.
import hashlib, json, os, re, shutil, subprocess, sys, time, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tzlib import cfg, chat_tokens, feature
import tzusage

WINDOW5, LOOKBACK, MIN_SPAN, TOLERANCE = 18000, 1800, 600, 60  # seconds, session forecast
RESERVED = 5  # columns the host keeps for itself
COLORS = ('black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white')
SEP = {'|': ' | ', '-': ' - ', ',': ', ', ' ': ' '}


def home(*p):
    """Path under the TZ state folder (resolved per call so HOME changes apply)."""
    return os.path.join(os.path.expanduser('~/.claude/token-zombie'), *p)


def config_path():
    """Layout file: env TZ_LINE_CONFIG, else line.json in the TZ folder."""
    return os.environ.get('TZ_LINE_CONFIG') or home('line.json')


def _load(path, default):
    """JSON file or default; never raises."""
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def _save(path, obj, indent=None):
    """Atomic JSON write; returns False when the disk refuses."""
    try:
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        tmp = f'{path}.tmp{os.getpid()}'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(obj, f, indent=indent)
        os.replace(tmp, path)
        return True
    except OSError:
        return False


# ---- text safety, width, colour -------------------------------------------------------------------------------
_SGR = re.compile(r'(?:\x1b\[|\x9b)[0-9;:]*m')
_OSC8 = re.compile(r'(?:\x1b\]|\x9d)8;[A-Za-z0-9=:_.-]*;[^\x00-\x20\x7f-\x9f]*(?:\x1b\\|\x9c|\x07)')
# every other sequence is swallowed whole: strings (OSC/DCS/SOS/PM/APC), CSI, intermediates, two-byte
_ESC = re.compile(r'(?:\x1b[\]PX^_]|[\x90\x98\x9d\x9e\x9f])[^\x07\x9c\x1b]*(?:\x07|\x9c|\x1b\\)?'
                  r'|(?:\x1b\[|\x9b)[ -?]*[@-~]?|\x1b[ -/]+[0-~]?|\x1b[^\x1b\x9b]?|[\x00-\x09\x0b-\x1f\x7f-\x9f]')


def sanitize(text):
    """Drop control sequences from untrusted text; keep colours and safe OSC 8 links (7-bit form); tab -> space."""
    out, i = [], 0
    while i < len(text):
        m = _SGR.match(text, i) or _OSC8.match(text, i)
        if m:
            s = m.group(0)
            s = '\x1b' + {'\x9b': '[', '\x9d': ']'}[s[0]] + s[1:] if s[0] in '\x9b\x9d' else s
            out.append(s[:-1] + '\x1b\\' if s.endswith('\x9c') else s)
        else:
            m = _ESC.match(text, i)
            if not m:
                out.append(text[i]); i += 1
                continue
            if m.group(0) == '\t':
                out.append(' ')
        i = m.end()
    return ''.join(out)


def plain(text):
    """Visible characters only."""
    return _OSC8.sub('', _SGR.sub('', text))


def _cw(c):
    """Terminal columns of one character."""
    if unicodedata.combining(c) or c in '‍️':
        return 0
    return 2 if unicodedata.east_asian_width(c) in 'WF' else 1


def width(text):
    """Visible column width of styled text."""
    return sum(map(_cw, plain(text)))


def truncate(text, limit, ellipsis=True):
    """Cut styled text to `limit` columns, closing any open colour or link."""
    if width(text) <= limit:
        return text
    tail = '...' if ellipsis and limit >= 3 else ''
    room, out, i = limit - len(tail), [], 0
    while i < len(text):
        m = _SGR.match(text, i) or _OSC8.match(text, i)
        if m:
            out.append(m.group(0)); i = m.end()
            continue
        room -= _cw(text[i])
        if room < 0:
            break
        out.append(text[i]); i += 1
    s = ''.join(out)
    link = '\x1b]8;;\x1b\\' if '\x1b]8;' in s else ''
    return s + tail + link + ('\x1b[0m' if '\x1b[' in s else '')


def _code(color, bg, level):
    """SGR parameters for a ccstatusline colour name (named, brightX, bgX, ansi256:N, hex:RRGGBB)."""
    if not isinstance(color, str):
        return ''
    c = color[2].lower() + color[3:] if color.startswith('bg') and len(color) > 2 else color
    base = 40 if bg else 30
    if c in COLORS:
        return str(base + COLORS.index(c))
    if c in ('gray', 'grey'):
        c = 'brightBlack'
    if c.startswith('bright') and c[6:].lower() in COLORS:
        return str(base + 60 + COLORS.index(c[6:].lower()))
    m = re.fullmatch(r'ansi256:(\d{1,3})', c)
    if m:
        return f'{base + 8};5;{min(255, int(m.group(1)))}'
    m = re.fullmatch(r'hex:([0-9A-Fa-f]{6})', c)
    if m:
        r, g, b = (int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))
        if level >= 3:
            return f'{base + 8};2;{r};{g};{b}'
        return f'{base + 8};5;{16 + 36 * round(r / 51) + 6 * round(g / 51) + round(b / 51)}'
    return ''


def paint(text, item, conf, default=''):
    """Apply an item's colour/bold/dim; colorLevel 0 or NO_COLOR gives plain text."""
    level = conf.get('colorLevel', 2)
    if not level or os.environ.get('NO_COLOR'):
        return plain(text)
    codes = [c for c in ('1' if item.get('bold') or conf.get('globalBold') else '', '2' if item.get('dim') is True else '',
                         _code(item.get('color') or default, False, level), _code(item.get('backgroundColor'), True, level)) if c]
    return f"\x1b[{';'.join(codes)}m{text}\x1b[0m" if codes else text


# ---- number formats -------------------------------------------------------------------------------------------
def tok(n):
    """1234 -> 1.2k."""
    return f'{n / 1e6:.1f}M' if n >= 1e6 else (f'{n / 1e3:.1f}k' if n >= 1000 else str(int(n)))


def dur(sec):
    """Seconds -> '2d 3hr' / '2hr 15m' / '4m' / '<1m'."""
    m = int(max(0, sec) // 60)
    d, h, m = m // 1440, m % 1440 // 60, m % 60
    if d:
        return f'{d}d {h}hr'
    if h:
        return f'{h}hr {m}m' if m else f'{h}hr'
    return f'{m}m' if m else '<1m'


def _num(v):
    """Finite non-negative number or None."""
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v < float('inf') else None


def _epoch(v):
    """resets_at (epoch s/ms or ISO) -> epoch seconds or None."""
    n = _num(v)
    if n is not None:
        return n / 1000 if n > 1e12 else n
    return tzusage._ts(v) if v else None


# ---- context window -------------------------------------------------------------------------------------------
def _window_value(raw):
    """'1M', '200k', '1_000_000' -> tokens, else None."""
    m = re.fullmatch(r'\s*(\d+(?:[,_]\d+)*(?:\.\d+)?)\s*([kKmM])?\s*', raw or '')
    if not m:
        return None
    v = float(re.sub('[,_]', '', m.group(1))) * {'k': 1e3, 'm': 1e6}.get((m.group(2) or '').lower(), 1)
    return v if v > 0 else None


def _env_window():
    """Explicit window override; values under 1000 are nonsense and ignored."""
    v = _window_value(os.environ.get('CCSTATUSLINE_CONTEXT_WINDOW_SIZE'))
    return round(v) if v and round(v) >= 1000 else None


def max_window(model_id='', payload=None):
    """Context window: env override, host value, '[1m]'-style model suffix, fallback env, TZ ctx_window."""
    m = (re.search(r'[(\[]\s*(\d+(?:[,_]\d+)*(?:\.\d+)?)\s*([kKmM])\s*[)\]]', model_id or '')
         or re.search(r'\b(\d+(?:[,_]\d+)*(?:\.\d+)?)\s*([kKmM])(?:\s*(?:token\s*)?context)?\b', model_id or ''))
    fb = os.environ.get('CCSTATUSLINE_CONTEXT_SIZE_FALLBACK', '')
    return int(_env_window() or _num(payload) or (m and _window_value(m.group(1) + m.group(2)))
               or (int(fb) if fb.isdigit() and int(fb) else 0) or cfg('ctx_window'))


def usable_window(maximum):
    """Tokens usable before auto-compact [est]: 80% of the (possibly lowered) compact window; all of it if disabled."""
    if any(re.fullmatch(r'(1|true|yes|on)', os.environ.get(k, '').strip(), re.I) for k in ('DISABLE_AUTO_COMPACT', 'DISABLE_COMPACT')):
        return maximum
    w = _window_value(os.environ.get('CLAUDE_CODE_AUTO_COMPACT_WINDOW'))
    win = min(maximum, round(max(100000, min(1000000, w))) if w else maximum)
    try:
        pct = float(os.environ.get('CLAUDE_AUTOCOMPACT_PCT_OVERRIDE', '').replace('_', ''))
    except ValueError:
        pct = 0
    return max(1, int(win * (min(0.8, pct / 100) if 1 <= pct <= 100 else 0.8)))


# ---- chat log (incremental) -----------------------------------------------------------------------------------
def _blank():
    """Empty scan state."""
    return dict(off=0, ids={}, inp=0, out=0, cr=0, cw=0, ctx=0, post=None, comp=dict(count=0, auto=0, manual=0, unknown=0, reclaimed=0),
                user_ts=None, cache_ts=None, working=False, tin=0, tout=0, ms=0.0, pts=[], t0=None, t1=None, skills=[], name='')


def feed(s, e):
    """Fold one chat-log record into the scan state."""
    if not isinstance(e, dict):
        return
    ts = tzusage._ts(e.get('timestamp'))
    if ts:
        s['t0'], s['t1'] = s['t0'] or ts, ts
    if e.get('type') == 'custom-title':
        s['name'] = str(e.get('customTitle') or '')
    if e.get('isSidechain') is True:
        return
    if e.get('type') == 'system' and e.get('subtype') == 'compact_boundary':
        meta = e.get('compactMetadata') if isinstance(e.get('compactMetadata'), dict) else {}
        c = s['comp']
        c['count'] += 1
        c[meta.get('trigger') if meta.get('trigger') in ('auto', 'manual') else 'unknown'] += 1
        pre, post = _num(meta.get('preTokens')), _num(meta.get('postTokens'))
        if pre is not None and post is not None:
            c['reclaimed'] += max(0, pre - post)
        s['post'], s['ctx'] = post or 0, post or 0
        return
    m = e.get('message') if isinstance(e.get('message'), dict) else {}
    parts = m.get('content') if isinstance(m.get('content'), list) else []
    if e.get('type') == 'user':
        text = m.get('content') if isinstance(m.get('content'), str) else ''.join(str(p.get('text', '')) for p in parts if isinstance(p, dict))
        done_marks = ('[Request interrupted by user', '<command-name>', '<local-command-')
        s['working'] = not text.lstrip().startswith(done_marks)  # those end a turn with no reply
        s['user_ts'] = ts or s['user_ts']
        return
    for p in parts:
        if isinstance(p, dict) and p.get('type') == 'tool_use' and p.get('name') == 'Skill':
            sk = str((p.get('input') or {}).get('skill') or '')
            if sk:
                s['skills'] = [x for x in s['skills'] if x != sk][-19:] + [sk]
    u = m.get('usage')
    if not isinstance(u, dict) or e.get('isApiErrorMessage') or m.get('model') == '<synthetic>':
        return
    v = [_num(u.get(k)) or 0 for k in ('input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens')]
    key = m.get('id') or e.get('uuid') or str(ts)
    # one reply is logged on several lines with growing usage: replace its earlier count, never add twice
    old = s['ids'].pop(key, None)
    start = old[4] if old else s['user_ts']
    ms = max(0.0, (ts - start) * 1000) if ts and start else 0.0
    for n, k in enumerate(('inp', 'out', 'cr', 'cw')):
        s[k] += v[n] - (old[n] if old else 0)
    for n, k in ((0, 'tin'), (1, 'tout')):
        s[k] += (v[n] if ms else 0) - (old[n] if old and old[5] else 0)
    s['ms'] += ms - (old[5] if old else 0)
    s['ids'][key] = v + [start, ms]
    while len(s['ids']) > 50:
        del s['ids'][next(iter(s['ids']))]
    s['ctx'], s['working'] = v[0] + v[2] + v[3], False
    if ts:
        s['pts'] = (s['pts'] + [[ts, s['ctx']]])[-200:]
        if v[2] or v[3]:
            s['cache_ts'] = ts


def scan(path):
    """Chat-log totals, reading only bytes added since the last render (complete lines only)."""
    s = _blank()
    if not path or not os.path.isfile(path):
        return s
    state = home('line', hashlib.sha256(path.encode()).hexdigest()[:16] + '.json')
    old = _load(state, None)
    size = os.path.getsize(path)
    if isinstance(old, dict) and old.keys() >= s.keys() and old['off'] <= size:
        s = old
    with open(path, 'rb') as f:
        f.seek(s['off'])
        done = s['off']
        for raw in f:
            if not raw.endswith(b'\n'):
                break
            done += len(raw)
            try:
                feed(s, json.loads(raw))
            except Exception:
                pass
    if done != s['off']:
        s['off'] = done
        _save(state, s)
    return s


# ---- 5-hour window forecast and blocks ------------------------------------------------------------------------
def forecast(readings, now, reset, percent):
    """Where 5 h usage is heading at the last 30 min pace: dict current/projected/limit_in (seconds) or None."""
    seen = [r for r in readings if r[0] <= now + TOLERANCE]
    pct = max([percent] + [r[2] for r in seen])  # usage never falls inside a window
    left, start = reset - now, max(now - LOOKBACK, reset - WINDOW5)
    if left <= 0 or pct >= 100 or now - start < MIN_SPAN:
        return None
    pts = [(reset - WINDOW5, 0)] + [(t, r[2]) for r in seen for t in (r[0], min(r[1], now)) if t >= reset - WINDOW5]
    pts = sorted(pts + [(now, pct)])
    before = None
    for t, p in pts:
        if t > start and before:
            at = before[1] + (p - before[1]) * (start - before[0]) / (t - before[0])
            break
        before = (t, p)
    else:
        at = before[1] if before else 0
    rise = pct - at
    if rise <= 0:
        return None
    to_limit = (100 - pct) * (now - start) / rise
    return dict(current=pct, projected=min(100, pct + rise * left / (now - start)), limit_in=to_limit if to_limit < left else None)


def record_reading(reset, percent, now):
    """Keep first/last sighting of each 5 h percent (shared by all chats); returns this window's readings."""
    path = home('line', 'usage-5h.json')
    st = _load(path, {})
    if not isinstance(st, dict) or abs(st.get('reset', 0) - reset) > TOLERANCE:
        st = {'reset': reset, 'readings': []}
    r = st['readings']
    if r and r[-1][2] == percent:
        r[-1][1] = now
    elif not r or percent > r[-1][2]:
        r.append([now, now, percent])
    st['readings'] = r[-300:]
    _save(path, st)
    return st['readings']


def log_block(now):
    """Start of the active 5 h block from recent chat logs [est]; the scan is cached for 60 s."""
    path = home('line', 'block.json')
    c = _load(path, {})
    if isinstance(c, dict) and 0 <= now - c.get('ts', 0) < 60:
        return c.get('start')
    import glob
    ents = []
    root = os.path.expanduser((os.environ.get('CLAUDE_CONFIG_DIR') or '~/.claude').split(',')[0])
    for f in glob.glob(os.path.join(root, 'projects', '*', '*.jsonl')):
        try:
            if now - os.path.getmtime(f) > 2 * WINDOW5:
                continue
            with open(f, 'rb') as fh:
                for line in fh:
                    m = re.search(rb'"timestamp"\s*:\s*"([^"]+)"', line) if b'"usage"' in line else None
                    t = tzusage._ts(m.group(1).decode()) if m else None
                    if t:
                        ents.append((t, 0))
        except OSError:
            pass
    start = next((b['start'] for b in reversed(tzusage.blocks(ents, now=now)) if b['active']), None)
    _save(path, {'ts': now, 'start': start})
    return start


# ---- render context -------------------------------------------------------------------------------------------
class Ctx:
    """Everything one render may need; expensive sources load on first use."""
    def __init__(self, data, raw='', tz_segment='', now=None):
        self.data = data if isinstance(data, dict) else {}
        self.raw, self.tz, self.now = raw or json.dumps(self.data), tz_segment, now or time.time()
        self._scan, self._git, self.width = None, {}, term_width()

    def get(self, *keys):
        """Nested payload value or None."""
        v = self.data
        for k in keys:
            v = v.get(k) if isinstance(v, dict) else None
        return v

    @property
    def log(self):
        """Chat-log scan, once."""
        if self._scan is None:
            self._scan = scan(self.get('transcript_path'))
        return self._scan

    @property
    def cwd(self):
        """Session folder."""
        d = self.get('workspace', 'current_dir') or self.get('cwd')
        return d if isinstance(d, str) and os.path.isdir(d) else None

    def turn(self):
        """Last-turn usage from the payload (input, output, cache read, cache write) or None."""
        u = self.get('context_window', 'current_usage')
        if not isinstance(u, dict):
            return None
        return [_num(u.get(k)) or 0 for k in ('input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens')]

    def context(self):
        """(context tokens, window, used %)."""
        t = self.turn()
        n = _num(self.get('context_window', 'current_usage'))
        ctx = t[0] + t[2] + t[3] if t else (n if n is not None else self.log['ctx'])
        model = self.get('model')
        mid = f"{model.get('id', '')} {model.get('display_name', '')}" if isinstance(model, dict) else str(model or '')
        win = max_window(mid, self.get('context_window', 'context_window_size'))
        pct = _num(self.get('context_window', 'used_percentage'))
        if pct is None or _env_window():
            pct = ctx * 100.0 / win
        return ctx, win, min(100.0, pct)

    def limit(self, name):
        """(used %, reset epoch) of a provider window; (None, None) when the host does not send it."""
        v = self.get('rate_limits', name)
        if not isinstance(v, dict):
            return None, None
        return _num(v.get('used_percentage')), _epoch(v.get('resets_at'))


def term_width():
    """Terminal columns from env overrides, COLUMNS or the controlling tty; None if unknown."""
    for k in ('TZ_LINE_WIDTH', 'CCSTATUSLINE_WIDTH', 'COLUMNS'):
        if os.environ.get(k, '').isdigit() and int(os.environ[k]):
            return int(os.environ[k])
    try:
        fd = os.open('/dev/tty', os.O_RDONLY)
        try:
            return os.get_terminal_size(fd).columns or None
        finally:
            os.close(fd)
    except OSError:
        return None


# ---- git ------------------------------------------------------------------------------------------------------
_LFS = {'clean': 'git-lfs clean -- %f', 'smudge': 'git-lfs smudge -- %f', 'process': 'git-lfs filter-process'}


def _run(args, cwd, env=None):
    """stdout of a short command, or None."""
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, errors='replace', timeout=1, env=env, stdin=subprocess.DEVNULL)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def git(c, *args):
    """Memoised hardened git call: a repo's own config must not make the status line run programs."""
    if args in c._git:
        return c._git[args]
    if not c.cwd:
        return None
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0')
    base = ['git', '-c', 'core.fsmonitor=', '-c', 'safe.bareRepository=explicit']
    if '_filters' not in c._git:
        off, safe = [], True
        out = _run(base + ['config', '--null', '--show-scope', '--get-regexp', r'^filter\.'], c.cwd, env) or ''
        f = out.split('\0')
        for scope, kv in zip(f[::2], f[1::2]):
            key, _, val = kv.partition('\n')
            name, _, op = key[len('filter.'):].rpartition('.')
            if scope not in ('local', 'worktree') or not name or op not in _LFS or val in ('', _LFS[op]):
                continue
            if '=' in name:  # cannot be overridden with -c: skip git altogether
                safe = False
            off += [x for k in ('clean=', 'smudge=', 'process=', 'required=false') for x in ('-c', f'filter.{name}.{k}')]
        c._git['_filters'] = off if safe else None
    off = c._git['_filters']
    c._git[args] = None if off is None else _run(base + off + list(args), c.cwd, env)
    return c._git[args]


def git_status(c):
    """Branch, sha, ahead/behind and file counts from porcelain v2, or None outside a repo."""
    out = git(c, 'status', '--porcelain=v2', '--branch', '--untracked-files=normal')
    if out is None:
        return None
    s = dict(branch='', sha='', ahead=0, behind=0, staged=0, unstaged=0, untracked=0, conflicts=0)
    for line in out.splitlines():
        p = line.split(' ')
        if line.startswith('# branch.head '):
            s['branch'] = p[2]
        elif line.startswith('# branch.oid ') and p[2] != '(initial)':
            s['sha'] = p[2][:7]
        elif line.startswith('# branch.ab '):
            s['ahead'], s['behind'] = int(p[2][1:]), int(p[3][1:])
        elif p[0] in '12' and len(p) > 1:
            s['staged'] += p[1][0] != '.'
            s['unstaged'] += p[1][1] != '.'
        elif p[0] == 'u':
            s['conflicts'] += 1
        elif p[0] == '?':
            s['untracked'] += 1
    if s['branch'] == '(detached)':
        s['branch'] = s['sha']
    return s


def git_changes(c):
    """(insertions, deletions) staged plus unstaged, or None outside a repo."""
    ins = dels = 0
    for extra in ((), ('--cached',)):
        out = git(c, 'diff', '--no-ext-diff', '--no-textconv', '--shortstat', *extra)
        if out is None:
            return None
        a, d = re.search(r'(\d+) insertion', out), re.search(r'(\d+) deletion', out)
        ins, dels = ins + int(a.group(1) if a else 0), dels + int(d.group(1) if d else 0)
    return ins, dels


def remote(c, name):
    """(owner, repo) of a remote URL, or None."""
    m = re.search(r'[:/]([^/:]+)/([^/]+?)(?:\.git)?/?$', (git(c, 'remote', 'get-url', name) or '').strip())
    return m.groups() if m else None


# ---- widgets: type -> (label, value function, default colour) ------------------------------------------------
W = {}


def widget(kind, label='', color=''):
    """Register a widget; the function returns text, or None to hide."""
    def reg(fn):
        W[kind] = (label, fn, color)
        return fn
    return reg


def est(c, item, text):
    """Tag estimates unless the item shows raw values."""
    return text if item.get('rawValue') else f'{text} [est]'


def meta(item, key, default=''):
    """Item metadata string."""
    m = item.get('metadata')
    return m.get(key, default) if isinstance(m, dict) else default


def simple(kind, label, color, fn):
    """Register a one-line widget."""
    widget(kind, label, color)(fn)


def _model(c, i):
    """Model display name."""
    m = c.get('model')
    return (m.get('display_name') or m.get('id')) if isinstance(m, dict) else m


simple('model', 'Model: ', 'cyan', _model)
simple('version', 'Version: ', '', lambda c, i: c.get('version'))
simple('output-style', 'Style: ', '', lambda c, i: c.get('output_style', 'name'))
simple('vim-mode', '', 'green', lambda c, i: c.get('vim', 'mode'))
simple('fast-mode', 'Fast: ', '', lambda c, i: {True: 'on', False: 'off'}.get(c.get('fast_mode')))
simple('claude-session-id', 'Session ID: ', '', lambda c, i: c.get('session_id'))
simple('session-name', 'Session: ', '', lambda c, i: c.get('session_name') or c.log['name'] or None)
simple('current-working-dir', 'cwd: ', 'blue', lambda c, i: _short_dir(c, i))
simple('worktree-mode', '', '', lambda c, i: 'worktree' if c.get('worktree') else None)
for _k, _f in (('worktree-name', 'name'), ('worktree-branch', 'branch'), ('worktree-original-branch', 'original_branch')):
    simple(_k, 'WT: ', '', lambda c, i, f=_f: c.get('worktree', f))


def _short_dir(c, i):
    """Folder with ~ and optional last-N segments."""
    d = c.cwd
    if not d:
        return None
    h = os.path.expanduser('~')
    d = '~' + d[len(h):] if d == h or d.startswith(h + os.sep) else d
    n = meta(i, 'segments')
    parts = d.split('/')
    return '.../' + '/'.join(parts[-int(n):]) if n.isdigit() and 0 < int(n) < len(parts) else d


@widget('thinking-effort', 'Thinking: ', 'magenta')
def _effort(c, i):
    """Effort level from the payload, else user settings."""
    e = c.get('effort')
    e = e.get('level') if isinstance(e, dict) else e
    return e or _load(os.path.expanduser('~/.claude/settings.json'), {}).get('effortLevel')


# git
def _gs(fmt):
    """Widget over git status."""
    def f(c, i):
        s = git_status(c)
        return fmt(s) if s else None
    return f


simple('git-branch', '⎇ ', 'magenta', _gs(lambda s: s['branch'] or None))
simple('git-sha', '', '', _gs(lambda s: s['sha'] or None))
simple('git-ahead-behind', '', '', _gs(lambda s: f"↑{s['ahead']} ↓{s['behind']}" if s['ahead'] or s['behind'] else None))
simple('git-clean-status', '', '', _gs(lambda s: '✗' if s['staged'] + s['unstaged'] + s['untracked'] + s['conflicts'] else '✓'))
simple('git-status', '', 'yellow', _gs(lambda s: ''.join(m for m, k in (('!', 'conflicts'), ('+', 'staged'), ('*', 'unstaged'), ('?', 'untracked')) if s[k]) or None))
for _k, _n, _m in (('git-staged', 'staged', '+'), ('git-unstaged', 'unstaged', '*'), ('git-untracked', 'untracked', '?')):
    simple(_k, '', '', _gs(lambda s, n=_n, m=_m: m if s[n] else None))
    simple(_k + '-files', _m, '', _gs(lambda s, n=_n: str(s[n])))
simple('git-conflicts', '!', 'red', _gs(lambda s: str(s['conflicts']) if s['conflicts'] else None))


def _gc(fmt):
    """Widget over git diff counts."""
    def f(c, i):
        d = git_changes(c)
        return fmt(*d) if d else None
    return f


simple('git-changes', '', 'yellow', _gc(lambda a, d: f'(+{a},-{d})'))
simple('git-insertions', '', 'green', _gc(lambda a, d: f'+{a}'))
simple('git-deletions', '', 'red', _gc(lambda a, d: f'-{d}'))
simple('git-root-dir', '', '', lambda c, i: os.path.basename((git(c, 'rev-parse', '--show-toplevel') or '').strip()) or None)


@widget('git-worktree', '\U00010FFF'[:0])
def _gitwt(c, i):
    """Linked worktree name, 'main' in the main checkout."""
    d = (git(c, 'rev-parse', '--absolute-git-dir') or '').strip()
    return None if not d else (os.path.basename(d) if '/worktrees/' in d else 'main')


for _r in ('origin', 'upstream'):
    for _s, _f in (('owner', lambda p: p[0]), ('repo', lambda p: p[1]), ('owner-repo', '/'.join)):
        if (_r, _s) != ('upstream', 'x'):
            simple(f'git-{_r}-{_s}', '', '', lambda c, i, r=_r, f=_f: (lambda p: f(p) if p else None)(remote(c, r)))
simple('git-is-fork', '', '', lambda c, i: 'fork' if remote(c, 'upstream') and remote(c, 'origin') != remote(c, 'upstream') else None)


# tokens, context, cache
def _tokens(key):
    """Session token total from the chat log [actual]."""
    def f(c, i):
        s = c.log
        n = {'in': s['inp'], 'out': s['out'], 'cached': s['cr'] + s['cw'], 'total': s['inp'] + s['out'] + s['cr'] + s['cw']}[key]
        return tok(n) if s['t0'] else None
    return f


for _k, _l in (('input', 'In: '), ('output', 'Out: '), ('cached', 'Cached: '), ('total', 'Total: ')):
    simple('tokens-' + _k, _l, 'yellow', _tokens({'input': 'in', 'output': 'out'}.get(_k, _k)))
simple('context-length', 'Ctx: ', 'brightBlack', lambda c, i: tok(c.context()[0]) if c.context()[0] else None)
simple('context-window', 'Window: ', '', lambda c, i: tok(c.context()[1]))
simple('context-percentage', 'Ctx: ', 'blue', lambda c, i: _pct(c.context()[2], i) if c.context()[0] else None)


def _pct(p, item):
    """Percent, optionally shown as remaining (metadata inverse=true)."""
    return f"{100 - p if meta(item, 'inverse') == 'true' else p:.1f}%"


@widget('context-percentage-usable', 'Ctx(u): ', 'green')
def _usable(c, i):
    """Share of the pre-compaction window [est]."""
    ctx, win, _ = c.context()
    return est(c, i, _pct(min(100.0, ctx * 100.0 / usable_window(win)), i)) if ctx else None


@widget('context-bar', 'Context: ', 'blue')
def _bar(c, i):
    """Progress bar of context use."""
    ctx, win, pct = c.context()
    if not ctx:
        return None
    n = int(meta(i, 'width', '16')) if meta(i, 'width', '16').isdigit() else 16
    fill = int(round(pct * n / 100))
    return f"[{'█' * fill}{'░' * (n - fill)}] {tok(ctx)}/{tok(win)} ({pct:.0f}%)"


def _cache(c, i):
    """(input, read, write) for the whole chat, or the last turn with metadata scope=turn."""
    if meta(i, 'scope') == 'turn':
        t = c.turn()
        return (t[0], t[2], t[3]) if t else None
    s = c.log
    return (s['inp'], s['cr'], s['cw']) if s['t0'] else None


@widget('cache-hit-rate', 'Cache Hit: ', 'cyan')
def _hit(c, i):
    """reads / (reads + writes)."""
    v = _cache(c, i)
    r = tzusage.hit_rate(v[1], v[2]) if v else None
    return None if r is None else f'{r:.1f}%'


simple('cache-read', 'Cache Read: ', '', lambda c, i: (lambda v: tok(v[1]) if v else None)(_cache(c, i)))
simple('cache-write', 'Cache Write: ', '', lambda c, i: (lambda v: tok(v[2]) if v else None)(_cache(c, i)))


@widget('cache-timer', 'Cache: ', 'cyan')
def _timer(c, i):
    """Prompt-cache life left: host expires_at [actual], else last cache use plus measured TTL [est]."""
    end = _num(c.get('prompt_cache', 'expires_at'))
    if end is not None:
        left = end - c.now
        return 'COLD' if left <= 0 else f'{int(left) // 60}:{int(left) % 60:02d}'
    s = c.log
    if s['working']:
        return 'active'
    if not s['cache_ttl'] if 'cache_ttl' in s else not s['cache_ts']:
        return None
    ttl = meta(i, 'ttlSeconds')
    if ttl.isdigit():
        ttl = int(ttl)
    else:
        from tzcont import cache_ttl
        ttl = cache_ttl(c.get('transcript_path'))
    left = ttl - 5 - (c.now - s['cache_ts'])  # 5 s margin: call it cold slightly early
    return est(c, i, 'COLD' if left <= 0 else f'{int(left) // 60}:{int(left) % 60:02d}')


def _pc(c, key):
    """Number from the host's prompt_cache block."""
    return _num(c.get('prompt_cache', key))


simple('cache-misses', 'Misses: ', '', lambda c, i: None if _pc(c, 'misses') is None else str(int(_pc(c, 'misses'))))
simple('cache-miss-tokens', 'Re-cached: ', '', lambda c, i: None if _pc(c, 'miss_recache_tokens') is None else tok(_pc(c, 'miss_recache_tokens')))
simple('cache-if-cold', 'If cold: ', '', lambda c, i: None if _pc(c, 'recache_tokens_if_cold') is None else tok(_pc(c, 'recache_tokens_if_cold')))


@widget('last-cache-miss', 'Last miss: ', 'yellow')
def _miss(c, i):
    """Age and cause of the last miss reported by the host."""
    at = _epoch(c.get('prompt_cache', 'last_miss_at'))
    if not at:
        return None
    causes = c.get('prompt_cache', 'last_miss_cause', 'causes')
    why = f" ({', '.join(map(str, causes))})" if isinstance(causes, list) and causes else ''
    return f'{dur(c.now - at)} ago{why}'


@widget('compaction-counter', '↻ ', 'yellow')
def _comp(c, i):
    """Compactions in this chat; metadata metric=auto|manual|unknown|reclaimed, hideZero=true."""
    v = c.log['comp']
    k = meta(i, 'metric', 'count')
    n = v.get(k, v['count'])
    if not n and meta(i, 'hideZero') == 'true':
        return None
    return tok(n) if k == 'reclaimed' else str(int(n))


def _speed(kind):
    """Tokens per second over measured request time [est: log timestamps]."""
    def f(c, i):
        s = c.log
        if not s['ms']:
            return None
        n = {'input': s['tin'], 'output': s['tout'], 'total': s['tin'] + s['tout']}[kind]
        return est(c, i, f"{tok(n / (s['ms'] / 1000))} t/s")
    return f


for _k, _l in (('input', 'In: '), ('output', 'Out: '), ('total', 'Total: ')):
    simple(f'{_k}-speed', _l, '', _speed(_k))


# session, cost, limits
@widget('session-clock', 'Session: ', 'yellow')
def _clock(c, i):
    """Host session duration, else first-to-last log time."""
    ms = _num(c.get('cost', 'total_duration_ms'))
    if ms is None:
        s = c.log
        return dur(s['t1'] - s['t0']) if s['t0'] else None
    return dur(ms / 1000)


@widget('session-cost', 'Cost: ', 'green')
def _cost(c, i):
    """Host-reported cost."""
    v = _num(c.get('cost', 'total_cost_usd'))
    return None if v is None else f'${v:.2f}'


@widget('session-cost-rate', 'Rate: ', 'green')
def _rate(c, i):
    """Cost per hour once at least a minute has passed."""
    v, ms = _num(c.get('cost', 'total_cost_usd')), _num(c.get('cost', 'total_duration_ms'))
    return None if v is None or ms is None or ms < 60000 else f'${v / (ms / 3600000):.2f}/hr'


@widget('lines-changed', 'Lines: ', '')
def _lines(c, i):
    """Lines the session added and removed, from the host."""
    a, d = _num(c.get('cost', 'total_lines_added')), _num(c.get('cost', 'total_lines_removed'))
    return None if a is None and d is None else f'+{int(a or 0)},-{int(d or 0)}'


def _usage_pct(name):
    """Provider-reported window percent."""
    return lambda c, i: (lambda p: None if p is None else _pct(p, i))(c.limit(name)[0])


for _k, _l, _n in (('session-usage', '5h: ', 'five_hour'), ('weekly-usage', '7d: ', 'seven_day'), ('weekly-opus-usage', '7d Opus: ', 'seven_day_opus'),
                   ('weekly-sonnet-usage', '7d Sonnet: ', 'seven_day_sonnet'), ('spend-limit-usage', 'Spend: ', 'spend_limit')):
    simple(_k, _l, '', _usage_pct(_n))


@widget('spend-limit-amount', 'Spend: ', '')
def _spend(c, i):
    """Dollars used of the host's spend limit."""
    u, m = _num(c.get('rate_limits', 'spend_limit', 'used_usd')), _num(c.get('rate_limits', 'spend_limit', 'limit_usd'))
    return None if u is None or m is None else f'${u:.2f}/${m:.2f}'


def _reset(name):
    """Time until a provider window resets."""
    return lambda c, i: (lambda r: dur(r - c.now) if r and r > c.now else None)(c.limit(name)[1])


simple('reset-timer', 'Reset: ', '', _reset('five_hour'))
simple('weekly-reset-timer', '7d reset: ', '', _reset('seven_day'))


@widget('block-timer', 'Block: ', 'yellow')
def _block(c, i):
    """Time into the 5 h block: from the provider reset, else estimated from chat logs."""
    r = c.limit('five_hour')[1]
    if r and r > c.now:
        return dur(max(0, WINDOW5 - (r - c.now)))
    start = log_block(c.now)
    return est(c, i, dur(c.now - start)) if start else None


def _forecast(c):
    """Current 5 h forecast, recording this reading."""
    p, r = c.limit('five_hour')
    if p is None or not r or r <= c.now:
        return None
    return forecast(record_reading(r, p, c.now), c.now, r, p)


@widget('block-forecast', '→', 'yellow')
def _bf(c, i):
    """Projected 5 h percent at reset [est]."""
    f = _forecast(c)
    return est(c, i, f"{f['projected']:.0f}%") if f else None


@widget('block-limit-timer', 'Limit in: ', 'red')
def _bl(c, i):
    """Time until the 5 h limit, only if it comes before the reset [est]."""
    f = _forecast(c)
    return est(c, i, dur(f['limit_in'])) if f and f['limit_in'] is not None else None


@widget('weekly-limit-timer', '7d full: ', 'red')
def _wl(c, i):
    """When the weekly window fills at the average pace so far [est]."""
    import datetime as dt
    v = c.limit('seven_day')[0]
    if v is None:
        return None
    lim = tzusage.limits({'seven_day': c.get('rate_limits', 'seven_day')}, now=dt.datetime.fromtimestamp(c.now))
    return est(c, i, lim[0]['full']) if lim and lim[0]['full'] else None


# TOKEN ZOMBIE's own numbers
@widget('tz', '', 'green')
def _tz(c, i):
    """Chat growth against the TZ limit (the classic TZ segment when the caller passes it)."""
    if c.tz:
        return c.tz
    base, last = chat_tokens(c.get('transcript_path'))
    return f"TZ {max(0, last - base) // 1000}k/{cfg('limit') // 1000}k" if last else None


@widget('tz-level', 'Level: ', '')
def _level(c, i):
    """TZ usage level from context and provider percent."""
    ctx, _, pct = c.context()
    rl = c.get('rate_limits')
    return tzusage.level(pct, tzusage.limits(rl if isinstance(rl, dict) else None)) if ctx or rl else None


@widget('burn-rate', 'Burn: ', 'yellow')
def _burn(c, i):
    """Context growth per minute over the last 10 minutes [est]."""
    rate, _ = tzusage.burn({'pts': c.log['pts'], 'last': c.log['ctx']}, window=c.context()[1])
    return est(c, i, f'{tok(rate)}/min') if rate else None


# machine and user content
simple('terminal-width', 'Term: ', '', lambda c, i: str(c.width) if c.width else None)
simple('custom-text', '', '', lambda c, i: i.get('customText') or None)
simple('custom-symbol', '', '', lambda c, i: i.get('customSymbol') or None)
simple('skills', 'Skills: ', 'magenta', lambda c, i: ', '.join(c.log['skills'][::-1][:int(meta(i, 'limit', '3')) if meta(i, 'limit', '3').isdigit() else 3]) or None)


@widget('free-memory', 'Mem: ', '')
def _mem(c, i):
    """Used / total memory (Linux /proc, macOS vm_stat)."""
    try:
        if os.path.exists('/proc/meminfo'):
            m = dict(re.findall(r'(\w+):\s+(\d+)', open('/proc/meminfo').read()))
            total, used = int(m['MemTotal']) * 1024, (int(m['MemTotal']) - int(m['MemAvailable'])) * 1024
        elif sys.platform == 'darwin':
            total = int(_run(['sysctl', '-n', 'hw.memsize'], None))
            out = _run(['vm_stat'], None)
            page = int(re.search(r'page size of (\d+)', out).group(1))
            used = page * sum(int(re.search(k + r':\s+(\d+)', out).group(1)) for k in ('Pages active', 'Pages wired down'))
        else:
            return None
    except Exception:
        return None
    return f'{used / 2**30:.1f}G/{total / 2**30:.1f}G'


@widget('link')
def _link(c, i):
    """Clickable OSC 8 link (metadata url, text); plain text when the URL is unsafe."""
    url, text = meta(i, 'url'), plain(sanitize(meta(i, 'text') or meta(i, 'url')))
    if not re.fullmatch(r'https?://[^\x00-\x20\x7f-\x9f]+', url):
        return text or None
    return f'\x1b]8;;{url}\x1b\\{text}\x1b]8;;\x1b\\'


@widget('custom-command')
def _command(c, i):
    """First output line of the user's command (status JSON on stdin). Off unless feature line_custom_command is on."""
    cmd = i.get('commandPath')
    if not cmd or not feature('line_custom_command'):
        return None
    try:
        t = _num(i.get('timeout')) or 1000
        r = subprocess.run(cmd, shell=True, input=c.raw, capture_output=True, text=True, errors='replace', timeout=min(t, 3000) / 1000)
    except (OSError, subprocess.SubprocessError):
        return '[timeout/error]'
    line = next((x for x in r.stdout.splitlines() if x.strip()), '').strip() if r.returncode == 0 else f'[exit {r.returncode}]'
    return (line if i.get('preserveColors') else plain(sanitize(line))) or None


# ---- renderer -------------------------------------------------------------------------------------------------
DEFAULT = {'version': 3, 'colorLevel': 2, 'lines': [
    [{'type': t} for t in ('model', 'separator', 'context-bar', 'separator', 'context-percentage-usable', 'separator', 'cache-hit-rate',
                           'separator', 'cache-timer', 'separator', 'git-branch', 'git-changes')],
    [{'type': t} for t in ('tz', 'separator', 'session-usage', 'block-forecast', 'separator', 'reset-timer', 'separator', 'weekly-usage',
                           'separator', 'session-cost', 'separator', 'compaction-counter')]]}


def configured():
    """True when the user has a layout file (opt-in: without it the classic TZ status line stays)."""
    return os.path.isfile(config_path())


def settings():
    """Layout from the config file, else the built-in default; bad shapes fall back."""
    s = _load(config_path(), None)
    if not isinstance(s, dict) or not isinstance(s.get('lines'), list):
        return DEFAULT
    return s


def _value(c, item, conf):
    """One widget rendered and coloured, or None (unknown type, no data, or an error)."""
    if item.get('type') not in W:
        return None
    label, fn, color = W[item['type']]
    try:
        v = fn(c, item)
    except Exception:  # one broken widget must never blank the status line
        return None
    if v is None or v == '':
        return None
    v = sanitize(str(v)).replace('\n', ' ')
    text = v if item.get('rawValue') else label + v
    if _num(item.get('maxWidth')):
        text = truncate(text, int(item['maxWidth']), ellipsis=False)
    keep = item['type'] == 'custom-command' and item.get('preserveColors') or '\x1b[' in v
    return text if keep else paint(text, item, conf, color)


def render_line(c, items, conf):
    """Join one line: drop orphan separators, apply padding/merge, expand flex separators, truncate."""
    pad = sanitize(str(conf.get('defaultPadding') or ''))
    side = conf.get('defaultPaddingSide', 'both')
    default = conf.get('defaultSeparator')
    parts, pending, prev = [[]], None, None
    for item in (x for x in items if isinstance(x, dict)):
        kind = item.get('type')
        if kind == 'separator':
            pending = pending or item
        elif kind == 'flex-separator':
            parts.append([])
            pending, prev = None, None
        else:
            v = _value(c, item, conf)
            if v is None:
                continue
            merged = prev.get('merge') if prev else None
            if prev is not None and not merged:
                sep = pending or ({'character': default, 'literal': True} if default else None)
                if sep:
                    ch = sanitize(str(sep.get('character', '|')))
                    parts[-1].append(paint(ch if sep.get('literal') else SEP.get(ch, ch), sep, conf, 'brightBlack'))
                else:
                    parts[-1].append(' ')
            lead = '' if side == 'right' or merged == 'no-padding' else pad
            trail = '' if side == 'left' or item.get('merge') == 'no-padding' else pad
            parts[-1].append(lead + v + trail)
            pending, prev = None, item
    joined = [''.join(p) for p in parts]
    if not any(joined):
        return ''
    room = max(0, c.width - RESERVED) if c.width else None
    if len(joined) == 1:
        line = joined[0]
    elif room is None:
        line = ' | '.join(x for x in joined if x)
    else:
        n = len(joined) - 1
        gap, extra = divmod(max(0, room - sum(map(width, joined))), n)
        line = ''.join(p + (' ' * (gap + (k < extra)) if k < n else '') for k, p in enumerate(joined))
    return truncate(line, room) if room is not None else line


def render(data, raw='', tz_segment='', conf=None, now=None, host=False):
    """All configured lines as one string; host=True keeps spacing and overrides the app's dim style."""
    conf = conf or settings()
    c = Ctx(data, raw, tz_segment, now)
    out = [render_line(c, items, conf) for items in conf['lines'] if isinstance(items, list)]
    out = [x for x in out if x]
    if host:  # non-breaking spaces stop the host trimming; reset first so colours are not dimmed
        out = ['\x1b[0m' + re.sub(r' ', ' ', x) for x in out]
    return '\n'.join(out)


# ---- CLI ------------------------------------------------------------------------------------------------------
def sample(now):
    """Preview payload."""
    return {'model': {'id': 'claude-sonnet-sample', 'display_name': 'Sonnet (sample)'}, 'cwd': os.getcwd(), 'version': '0.0.0',
            'cost': {'total_cost_usd': 1.23, 'total_duration_ms': 3_600_000, 'total_lines_added': 12, 'total_lines_removed': 3},
            'context_window': {'context_window_size': 200000, 'current_usage': {'input_tokens': 2000, 'output_tokens': 500,
                               'cache_read_input_tokens': 40000, 'cache_creation_input_tokens': 5000}},
            'prompt_cache': {'expires_at': now + 240},
            'rate_limits': {'five_hour': {'used_percentage': 42, 'resets_at': now + 7200}, 'seven_day': {'used_percentage': 15, 'resets_at': now + 300000}}}


def import_config(src):
    """Convert a ccstatusline settings.json to a TZ layout; returns (layout, unsupported widget types)."""
    s = _load(os.path.expanduser(src), None)
    if not isinstance(s, dict) or not isinstance(s.get('lines'), list):
        raise ValueError(f'not a ccstatusline settings file: {src}')
    keep = {k: s[k] for k in ('lines', 'colorLevel', 'defaultSeparator', 'defaultPadding', 'defaultPaddingSide', 'globalBold') if k in s}
    keep['version'] = 3
    known = set(W) | {'separator', 'flex-separator'}
    kinds = {str(x.get('type')) for ln in s['lines'] if isinstance(ln, list) for x in ln if isinstance(x, dict)}
    return keep, sorted(kinds - known)


def main(argv):
    """tz line [render|preview|widgets|show|init|add|remove|import]."""
    import argparse
    ap = argparse.ArgumentParser(prog='tz line', description='Configurable status line. Values tagged [est] are estimates.')
    ap.add_argument('cmd', nargs='?', default='render', choices=['render', 'preview', 'widgets', 'show', 'init', 'add', 'remove', 'import'])
    ap.add_argument('arg', nargs='?', help='add: widget type; remove: position in the line; import: settings.json path')
    ap.add_argument('--line', type=int, default=1)
    ap.add_argument('--color')
    ap.add_argument('--text', help='custom-text / custom-symbol / custom-command value')
    ap.add_argument('--force', action='store_true', help='overwrite an existing layout (a .bak copy is kept)')
    a = ap.parse_args(argv)
    path = config_path()
    if a.cmd == 'render':
        raw = '' if sys.stdin.isatty() else sys.stdin.read()
        try:
            data = json.loads(raw) if raw.strip() else {}
        except ValueError:
            data = {}
        print(render(data, raw, host=bool(raw)))
        return 0
    if a.cmd == 'preview':
        now = time.time()
        print(render(sample(now), now=now))
        print('(sample data; [est] marks estimates)')
        return 0
    if a.cmd == 'widgets':
        print('\n'.join(sorted(W) + ['separator', 'flex-separator']))
        return 0
    if a.cmd == 'show':
        print(f"{path} ({'file' if configured() else 'built-in default'})")
        for n, ln in enumerate(settings()['lines'], 1):
            print(f'line {n}: ' + ' '.join(f"{k}:{x.get('type')}" for k, x in enumerate(ln, 1)))
        print(f"custom-command: {'on' if feature('line_custom_command') else 'off (feature line_custom_command)'}")
        return 0
    if a.cmd in ('init', 'import'):
        if configured() and not a.force:
            print(f'tz line: {path} exists; use --force to replace it', file=sys.stderr)
            return 1
        try:
            new, unknown = (DEFAULT, []) if a.cmd == 'init' else import_config(a.arg or '~/.config/ccstatusline/settings.json')
        except ValueError as e:
            print(f'tz line: {e}', file=sys.stderr)
            return 1
        if configured():
            shutil.copy2(path, path + '.bak')
        if not _save(path, new, indent=2):
            print(f'tz line: cannot write {path}', file=sys.stderr)
            return 1
        print(f'wrote {path}')
        if unknown:
            print('not supported (hidden): ' + ', '.join(unknown))
        if any(x.get('type') == 'custom-command' for ln in new['lines'] for x in ln if isinstance(x, dict)):
            print('layout has custom commands; they stay off until feature line_custom_command is enabled. Review them first.')
        return 0
    conf = json.loads(json.dumps(settings()))
    lines = conf['lines']
    if a.line < 1 or a.line > len(lines) + 1:
        print(f'tz line: --line must be 1..{len(lines) + 1}', file=sys.stderr)
        return 2
    while len(lines) < a.line:
        lines.append([])
    row = lines[a.line - 1]
    if a.cmd == 'add':
        if a.arg not in W and a.arg not in ('separator', 'flex-separator'):
            print(f'tz line: unknown widget {a.arg!r} (see: tz line widgets)', file=sys.stderr)
            return 2
        item = {'type': a.arg}
        if a.color:
            item['color'] = a.color
        if a.text:
            item[{'custom-symbol': 'customSymbol', 'custom-command': 'commandPath'}.get(a.arg, 'customText')] = a.text
        row.append(item)
    else:
        if not (a.arg or '').isdigit() or not 1 <= int(a.arg) <= len(row):
            print(f'tz line: remove needs a position 1..{len(row)}', file=sys.stderr)
            return 2
        row.pop(int(a.arg) - 1)
    if not _save(path, conf, indent=2):
        print(f'tz line: cannot write {path}', file=sys.stderr)
        return 1
    print(f'saved {path}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
