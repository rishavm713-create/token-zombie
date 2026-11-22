#!/usr/bin/env python3
# Token-zombie PreCompact: before the chat is summarised, save a small verified continuation note
# (git changed files, last test command + result from the log, next step from the task list).
# tz-start.py injects it after compaction (SessionStart source=compact). Runs only on compaction, never per tool call.
import json, os, re, subprocess, sys, time

TEST = re.compile(r'\b(pytest|unittest|(npm|yarn|pnpm|bun) (run )?test|go test|cargo test|jest|vitest|mocha|rspec|tox|ctest|'
                  r'make (test|check)|test_\w+\.(sh|py)|\w+_test\.(sh|py)|tests?/\S+\.(sh|py))\b')
OUT = os.path.expanduser('~/.claude/token-zombie')


def text(c):  # tool_result content: str or list of {type:text}
    if isinstance(c, list):
        c = '\n'.join(x.get('text', '') for x in c if isinstance(x, dict))
    return c if isinstance(c, str) else ''


ASK = None  # owner's newest typed message (first 200 chars)


def scan(path):
    """(last test cmd, ok?, last output line, next step) from the newest part of the chat log."""
    cmd = res = nxt = None
    ok = None
    want = None  # tool_use id of the newest test command
    try:
        with open(path, 'rb') as f:
            f.seek(max(0, os.path.getsize(path) - 1_500_000))
            lines = f.read().decode('utf-8', 'ignore').splitlines()
    except OSError:
        return cmd, ok, res, nxt
    results, plan = {}, []
    global ASK
    for line in lines:
        if '"type":"user"' in line.replace(' ', '') and '"tool_result"' not in line:
            try:
                c = json.loads(line).get('message', {}).get('content')
                t = c if isinstance(c, str) else ' '.join(x.get('text', '') for x in c if isinstance(x, dict) and x.get('type') == 'text')
                t = ' '.join(t.split())
                if t and not t.startswith('<'):  # skip hook/system-injected turns
                    ASK = t[:200]
            except Exception:
                pass
            continue
        if '"tool_use"' not in line and '"tool_result"' not in line:
            continue
        try:
            content = json.loads(line).get('message', {}).get('content')
        except Exception:
            continue
        for b in content if isinstance(content, list) else []:
            if not isinstance(b, dict):
                continue
            if b.get('type') == 'tool_result':
                results[b.get('tool_use_id')] = b
            elif b.get('type') == 'tool_use':
                i = b.get('input') or {}
                c = i.get('command') or ''
                if b.get('name') == 'Bash' and TEST.search(c):
                    cmd, want = c.strip().splitlines()[0][:160], b.get('id')  # first line only: notes stay small
                items = i.get('items') or i.get('todos')  # update_plan / TodoWrite: full list
                if isinstance(items, list):
                    plan = [dict(x) for x in items if isinstance(x, dict)]
                elif str(b.get('name', '')).endswith('wrap_up') and plan:  # wrap_up checks off the whole list
                    for x in plan:
                        x['status'] = 'completed'
                elif (i.get('done') or i.get('start')) and plan:  # update_plan {"done": [2], "start": 4}, 1-based
                    for n in i.get('done') or []:
                        if isinstance(n, int) and 0 < n <= len(plan):
                            plan[n - 1]['status'] = 'completed'
                    s = i.get('start')
                    if isinstance(s, int) and 0 < s <= len(plan):
                        for x in plan:
                            if x.get('status') == 'in_progress':
                                x['status'] = 'pending'
                        plan[s - 1]['status'] = 'in_progress'
                elif i.get('advance') and plan:  # update_plan advance: current done, next pending starts
                    cur = next((x for x in plan if x.get('status') == 'in_progress'), None)
                    if cur:
                        cur['status'] = 'completed'
                    nx = next((x for x in plan if x.get('status') == 'pending'), None)
                    if nx:
                        nx['status'] = 'in_progress'
    open_ = [x for x in plan if x.get('status') != 'completed']
    cur = next((x for x in open_ if x.get('status') == 'in_progress'), open_[0] if open_ else None)
    if cur:
        nxt = cur.get('content') or cur.get('activeForm')
    elif plan:
        nxt = 'all listed steps done'
    r = results.get(want)
    if r:
        out = [l for l in text(r.get('content')).splitlines() if l.strip()]
        res = out[-1][:160] if out else ''
        ok = not r.get('is_error')
    return cmd, ok, res, nxt


def git(cwd, *a):
    try:
        return subprocess.run(['git', '-C', cwd, *a], capture_output=True, text=True, timeout=2).stdout
    except Exception:
        return ''


try:
    d = json.load(sys.stdin)
    if d.get('agent_id') or '/subagents/' in (d.get('transcript_path') or ''):
        sys.exit(0)  # subagent compaction shares the parent session_id: never overwrite the parent's note
    cwd = d.get('cwd') or os.getcwd()
    changed = [l[3:] for l in git(cwd, 'status', '--porcelain', '-uall').splitlines() if l.strip()]
    cmd, ok, res, nxt = scan(d.get('transcript_path') or '')
    note = [f"# Continuation ({time.strftime('%Y-%m-%d %H:%M')}, {d.get('trigger', '?')} compact) in {cwd}",
            'Changed files (git, uncommitted): ' + (', '.join(changed[:15]) + (f' +{len(changed) - 15} more' if len(changed) > 15 else '')
                                                     if changed else 'none or not a git repo'),
            'Last test: ' + (f"`{cmd}` -> {'exit 0' if ok else 'FAILED'}: {res}" if cmd and ok is not None else
                             f'`{cmd}` (no result logged)' if cmd else 'none in recent log'),
            'Owner last asked: ' + (ASK or 'not found in log'),
            'Next step: ' + (nxt or 'not recorded; check the summary and the daily handoff'),
            'Verify before claiming done: rerun the test above.']
    os.makedirs(OUT, exist_ok=True)
    try:  # also refresh the task state so a compaction never loses the git snapshot
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import tzhandoff
        tzhandoff.checkpoint(cwd)
    except Exception:
        pass
    open(os.path.join(OUT, f"compact-{d.get('session_id', 'x')}.md"), 'w').write('\n'.join(note)[:1500] + '\n')
except Exception:
    sys.exit(0)
