#!/usr/bin/env python3
# Output trim + recall. PostToolUse: a big Read/Grep/WebFetch/MCP result is cut before the model sees it
# (hookSpecificOutput.updatedToolOutput, same shape as the tool's own output; host keeps the original on a shape mismatch).
# The full text is kept locally: `tz recall <id> [--grep P] [--lines A-B]`. Bash is never touched (rtk owns Bash).
# Independent implementation; idea seen in context-mode (ELv2), no code copied. Verified on claude 2.1.318 (Read, Glob).
import hashlib, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STATE = os.path.expanduser('~/.claude/token-zombie')
RECALL = os.path.join(STATE, 'recall')
READ_MAX = int(os.environ.get('TZ_OUT_READ_MAX', 20000))  # chars kept from a whole-file Read (~5k tok); host 2.1.318 itself cut a
# 6000-line file at ~34k chars, so a higher limit never fires
OTHER_MAX = int(os.environ.get('TZ_OUT_MAX', 12000))  # chars kept from Grep content / WebFetch / MCP text (~3k tok)
KEEP_FILES = 200


def _conf():
    try:
        return json.load(open(os.path.join(STATE, 'config.json')))
    except Exception:
        return {}


def enabled():
    return os.environ.get('TZ_OUT', '1') != '0' and _conf().get('out_trim', True) is not False


def spill(text):
    rid = hashlib.sha1(text.encode('utf-8', 'replace')).hexdigest()[:10]
    os.makedirs(RECALL, mode=0o700, exist_ok=True)  # trimmed output can hold secrets (.env reads): owner-only
    os.chmod(RECALL, 0o700)
    p = os.path.join(RECALL, rid + '.txt')
    if not os.path.exists(p):
        with os.fdopen(os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w', encoding='utf-8') as fh:
            fh.write(text)
        old = sorted(os.listdir(RECALL), key=lambda f: os.path.getmtime(os.path.join(RECALL, f)))
        for f in old[:-KEEP_FILES]:
            os.remove(os.path.join(RECALL, f))
    return rid


def cut(text, limit, head_only):
    """Return (kept text, hidden chars) or None if under limit. Cuts on line edges."""
    if len(text) <= limit:
        return None
    lines = text.split('\n')
    rid = spill(text)
    if head_only:  # Read: keep line numbers right, so only a head is kept
        keep, n = [], 0
        for ln in lines:
            if n + len(ln) + 1 > limit:
                break
            keep.append(ln); n += len(ln) + 1
        k = len(keep)
        mark = (f'[TOKEN ZOMBIE trimmed: lines {k + 1}-{len(lines)} ({len(text) - n} chars) not shown. '
                f'Need them? Read with offset={k + 1} limit=..., or run: tz recall {rid} --grep PATTERN]')
        return '\n'.join(keep + [mark]), len(text) - n - len(mark)
    head, tail, n = [], [], 0
    for ln in lines:
        if n + len(ln) + 1 > limit * 0.7:
            break
        head.append(ln); n += len(ln) + 1
    m = 0
    for ln in reversed(lines[len(head):]):
        if m + len(ln) + 1 > limit * 0.3:
            break
        tail.insert(0, ln); m += len(ln) + 1
    hid = len(lines) - len(head) - len(tail)
    mark = (f'[TOKEN ZOMBIE trimmed: {hid} middle lines ({len(text) - n - m} chars) not shown. '
            f'Full text: tz recall {rid} --grep PATTERN  (or --lines A-B)]')
    return '\n'.join(head + [mark] + tail), len(text) - n - m - len(mark)


def trim(d):
    """PostToolUse payload -> (hookSpecificOutput, saved chars) or (None, 0). Never raises."""
    try:
        if not enabled():
            return None, 0
        tool, ti, r = d.get('tool_name') or '', d.get('tool_input') or {}, d.get('tool_response')
        saved = 0
        if tool == 'Read':
            fp = str(ti.get('file_path') or '')
            if ti.get('offset') or ti.get('limit') or fp.startswith(RECALL) or not isinstance(r, dict):
                return None, 0
            f = r.get('file') if r.get('type') == 'text' else None
            if not isinstance(f, dict) or not isinstance(f.get('content'), str):
                return None, 0
            c = cut(f['content'], READ_MAX, True)
            if not c:
                return None, 0
            f['content'], saved = c
            _mark_trimmed(d.get('session_id', 'x'), fp)
        elif tool == 'Grep' and isinstance(r, dict) and isinstance(r.get('content'), str):
            c = cut(r['content'], OTHER_MAX, False)
            if not c:
                return None, 0
            r['content'], saved = c
        elif tool == 'WebFetch' and isinstance(r, dict) and isinstance(r.get('result'), str):
            c = cut(r['result'], OTHER_MAX, False)
            if not c:
                return None, 0
            r['result'], saved = c
        elif tool.startswith('mcp__'):
            blocks = r if isinstance(r, list) else (r.get('content') if isinstance(r, dict) else None)
            if isinstance(r, str):
                c = cut(r, OTHER_MAX, False)
                if not c:
                    return None, 0
                r, saved = c
            elif isinstance(blocks, list):
                for b in blocks:
                    if isinstance(b, dict) and b.get('type') == 'text' and isinstance(b.get('text'), str):
                        c = cut(b['text'], OTHER_MAX, False)
                        if c:
                            b['text'], s = c
                            saved += s
                if not saved:
                    return None, 0
            else:
                return None, 0
        else:
            return None, 0
        if saved <= 0:
            return None, 0
        try:
            from tzopt import ledger
            ledger('out-trim', saved, 'measured', d.get('session_id', 'x'))
        except Exception:
            pass
        return {'hookEventName': 'PostToolUse', 'updatedToolOutput': r}, saved
    except Exception:
        return None, 0


def _mark_trimmed(session, fp):
    """The read guard must not call a trimmed Read 'already in context'."""
    p = os.path.join(STATE, f'reads-{session}.json')
    try:
        c = json.load(open(p))
    except Exception:
        return
    for k, v in c.items():
        if k.startswith(fp + '|'):
            v['trim'] = 1
    json.dump(c, open(p + '.tmp', 'w')); os.replace(p + '.tmp', p)


def recall(argv):
    rid = argv[0] if argv else ''
    if not re.fullmatch(r'[0-9a-f]{10}', rid):
        print('usage: tz recall <id> [--grep PATTERN] [--lines A-B]'); return 2
    p = os.path.join(RECALL, rid + '.txt')
    if not os.path.exists(p):
        print(f'no recall {rid} (kept: last {KEEP_FILES})'); return 1
    lines = open(p, encoding='utf-8').read().split('\n')
    if '--grep' in argv:
        pat = re.compile(argv[argv.index('--grep') + 1], re.I)
        for i, ln in enumerate(lines, 1):
            if pat.search(ln):
                print(f'{i}: {ln[:300]}')
    elif '--lines' in argv:
        a, _, b = argv[argv.index('--lines') + 1].partition('-')
        for i in range(max(1, int(a)), min(len(lines), int(b or a)) + 1):
            print(f'{i}: {lines[i - 1]}')
    else:
        print('\n'.join(lines))
    return 0


def main(argv):
    """`tz recall <id> ...` (bin/tz passes the args after 'recall'); `tzout.py hook < payload` for tests/probes."""
    if argv[:1] == ['recall']:
        argv = argv[1:]
    if argv[:1] == ['hook']:
        out, _ = trim(json.load(sys.stdin))
        if out:
            print(json.dumps({'hookSpecificOutput': out}))
        return 0
    return recall(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
