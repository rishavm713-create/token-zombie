#!/usr/bin/env python3
# Content-aware crushing for big tool output: detect JSON / unified diff / repetitive log, shrink structurally.
# Always paired with tzout.spill (original kept; `tz recall ID`). Pure stdlib. Idea of a content router seen in Headroom (Apache-2.0); independent code.
import json, re, statistics
import tzrtk
# Ideas adapted (independent code): Headroom (Apache-2.0) SmartCrusher outlier retention; RTK (Apache-2.0) strip-ANSI / collapse-blank stages.
_ANSI = re.compile(r'\x1b\[[0-9;?]*[ -/]*[@-~]')

_NUM = re.compile(r'0x[0-9a-fA-F]+|\d+')
_ERR = re.compile(r'error|fail|exception|fatal|denied|timeout|traceback|panic', re.I)


def kind(text):
    s = text.lstrip()[:1]
    if s in '[{':
        try:
            json.loads(text); return 'json'
        except ValueError:
            pass
    if text.startswith('diff --git') or re.search(r'^@@ -\d+', text, re.M):
        return 'diff'
    return 'log' if text.count('\n') > 20 else 'text'


def _outliers(x):
    """Indexes of dict items whose numeric field is a >=3-sigma outlier (kept even when the middle is omitted)."""
    if len(x) < 8 or not all(isinstance(i, dict) for i in x):
        return set()
    keep = set()
    for k in {k for i in x for k in i}:
        v = [(n, i[k]) for n, i in enumerate(x) if isinstance(i.get(k), (int, float)) and not isinstance(i.get(k), bool)]
        if len(v) < 8:
            continue
        sd = statistics.pstdev(a for _, a in v)
        if sd:
            m = statistics.fmean(a for _, a in v)
            keep |= {n for n, a in v if abs(a - m) >= 3 * sd}
    return keep


def _json(text):
    d = json.loads(text)
    omitted = [0]

    def walk(x):
        if isinstance(x, list) and len(x) > 8:
            out_i = _outliers(x)
            keep = [i for i in range(len(x)) if i < 3 or i == len(x) - 1 or i in out_i or _ERR.search(json.dumps(x[i])[:2000])]
            omitted[0] += len(x) - len(keep)
            out = [walk(x[i]) for i in keep]
            keys = sorted({k for i in x if isinstance(i, dict) for k in i})[:12]
            out.insert(3, f'[TZ: {len(x) - len(keep)} of {len(x)} items omitted' + (f'; keys {keys}' if keys else '') + ']')
            return out
        if isinstance(x, list):
            return [walk(i) for i in x]
        if isinstance(x, dict):
            return {k: walk(v) for k, v in x.items()}
        return x
    r = walk(d)
    return json.dumps(r, separators=(',', ':'), ensure_ascii=False) if omitted[0] else text


def _diff(text):
    out, ctx = [], 0
    lines = text.split('\n')
    for i, l in enumerate(lines):
        ch = l[:1] in '+-' or l.startswith(('@@', 'diff ', 'index ', '--- ', '+++ '))
        near = any(lines[j][:1] in '+-' for j in range(max(0, i - 1), min(len(lines), i + 2)))
        if ch or near:
            out.append(l)
    new = '\n'.join(out)
    return tzrtk.cap_hunks(new) if _rtk_on() else new


def _rtk_on():
    """Feature gate for the per-command filters and the hunk cap."""
    try:
        from tzlib import feature
        return feature('rtk_filters')
    except Exception:
        return False


def _log(text):
    out, prev, n, last = [], None, 0, ''
    flush = lambda: out.extend([f'[TZ: {n} similar lines omitted (numbers/ids differ); last of run:]', last] if n > 1 else [last] if n else [])
    for l in text.split('\n'):
        k = _NUM.sub('#', l.strip())
        if k == prev and not _ERR.search(l):
            n += 1; last = l; continue
        flush()
        out.append(l); prev, n, last = k, 0, ''
    flush()
    return '\n'.join(out)


def clean(text):
    """Lossless-ish noise stage: ANSI codes, carriage-return progress redraws (keep last), runs of blank lines."""
    t = _ANSI.sub('', text)
    if '\r' in t:
        t = '\n'.join(l.rsplit('\r', 1)[-1] if '\r' in l and l.rsplit('\r', 1)[-1].strip() else l.replace('\r', '') for l in t.split('\n'))
    return re.sub(r'\n{3,}', '\n\n', t)


def _buildlog(text):
    """tzlogc output when feature log_compress is on and the text is a build/test log, else None."""
    try:
        from tzlib import feature
        if not feature('log_compress'):
            return None
        import tzlogc
        r = tzlogc.compress(text)
    except Exception:
        return None
    return r and r['text']


def crush(text, cmd=None):
    """(new_text, kind) or (None, kind) when it did not shrink by >=10%. Caller must spill the original first.
    cmd (the shell command, when known) picks a per-command filter; without it only strict first-line signatures do."""
    if _rtk_on():
        new, name = tzrtk.apply(text, cmd)
        if new is not None:
            return new, 'rtk:' + name
    k = kind(text)
    if k != 'json' and not text.startswith('diff --git'):  # test output can hold '@@' hunks and still be a log
        new = _buildlog(text)
        if new is not None:
            return new, 'buildlog'
    text = clean(text) if k in ('log', 'text') else text
    try:
        new = {'json': _json, 'diff': _diff, 'log': _log}.get(k, lambda t: t)(text)
    except Exception:
        return None, k
    return (new, k) if len(new) <= len(text) * 0.9 else (None, k)
