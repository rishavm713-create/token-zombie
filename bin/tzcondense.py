#!/usr/bin/env python3
"""History condenser: keep the first K and last L events, replace old bulky tool results with a placeholder.
Idea from OpenHands software-agent-sdk condenser (keep_first / max_size / forgotten events) and mini-swe-agent
head+tail output cut (MIT); independent code, no LLM call. Every cut keeps head and tail and says how much was elided."""
import json, sys

PLACEHOLDER = '[tz: %d chars of old tool output elided]'


def cut(text, head=2000, tail=2000):
    """mini-swe-agent style: keep head and tail of a long string, say how much is gone."""
    if len(text) <= head + tail:
        return text
    return '%s\n[tz: %d chars elided]\n%s' % (text[:head], len(text) - head - tail, text[-tail:])


def condense(events, keep_first=2, keep_last=20, max_len=1000):
    """events: list of {'role','text'}. Old middle events with text > max_len are masked; short ones and the
    kept ends are untouched; the user's own messages are never masked. Returns (new_events, chars_saved)."""
    n, saved, out = len(events), 0, []
    for i, e in enumerate(events):
        t = e.get('text', '')
        if keep_first <= i < n - keep_last and e.get('role') != 'user' and len(t) > max_len:
            p = PLACEHOLDER % len(t)
            saved += len(t) - len(p)
            e = dict(e, text=p)
        out.append(e)
    return out, saved


def main(argv):
    if not argv:
        print('usage: tz condense FILE.jsonl [--keep-first K] [--keep-last L]  (lines: {"role","text"}); prints stats'); return 2
    arg = lambda k, d: int(argv[argv.index(k) + 1]) if k in argv else d
    ev = [json.loads(l) for l in open(argv[0], encoding='utf-8') if l.strip()]
    new, saved = condense(ev, arg('--keep-first', 2), arg('--keep-last', 20))
    tot = sum(len(e.get('text', '')) for e in ev)
    print('%d events, %d chars -> %d chars (saves %d, ~%d tokens EST)' % (len(ev), tot, tot - saved, saved, saved // 4))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
