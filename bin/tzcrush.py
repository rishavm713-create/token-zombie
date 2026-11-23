#!/usr/bin/env python3
# Content-aware crushing for big tool output: detect JSON / unified diff / repetitive log, shrink structurally.
# Always paired with tzout.spill (original kept; `tz recall ID`). Pure stdlib. Idea of a content router seen in Headroom (Apache-2.0); independent code.
import json, re

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


def _json(text):
    d = json.loads(text)
    omitted = [0]

    def walk(x):
        if isinstance(x, list) and len(x) > 8:
            keep = [i for i in range(len(x)) if i < 3 or i == len(x) - 1 or _ERR.search(json.dumps(x[i])[:2000])]
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
    return '\n'.join(out)


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


def crush(text):
    """(new_text, kind) or (None, kind) when it did not shrink by >=10%. Caller must spill the original first."""
    k = kind(text)
    try:
        new = {'json': _json, 'diff': _diff, 'log': _log}.get(k, lambda t: t)(text)
    except Exception:
        return None, k
    return (new, k) if len(new) <= len(text) * 0.9 else (None, k)
