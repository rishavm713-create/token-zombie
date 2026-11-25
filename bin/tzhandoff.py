#!/usr/bin/env python3
# Token-zombie task continuity: `handoff` writes a verified state file, `resume` checks it against reality.
# Files in <project>/handoffs/: YYYY-MM-DD-tz.md (DAILY note, <=30 lines, read by tz-start.py),
# tasks/<slug>.json (active task state, evidence = paths), MASTER.md (stable project facts). resume never writes to the work tree.
import hashlib, json, os, subprocess, sys, time

MEM_TAIL = 10


def git(cwd, *a):
    try:
        r = subprocess.run(['git', '-C', cwd, *a], capture_output=True, text=True, timeout=5)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def fhash(p):
    try:
        with open(p, 'rb') as f:
            return hashlib.sha1(f.read(1_000_000)).hexdigest()[:10] + f':{os.path.getsize(p)}'
    except OSError:
        return 'gone'


def snapshot(cwd):
    """git state: branch, head, {changed file: content hash}. repo=False outside git."""
    top = git(cwd, 'rev-parse', '--show-toplevel')
    if top is None:
        return {'repo': False, 'branch': '', 'head': '', 'changed': {}}
    top = top.strip()
    st = git(cwd, 'status', '--porcelain', '-uall') or ''
    changed = {}
    for l in st.splitlines():
        if l.strip():
            p = l[3:].split(' -> ')[-1].strip('"')
            if p.startswith('handoffs/'):  # our own notes must not count as drift
                continue
            changed[p] = fhash(os.path.join(top, p))
    return {'repo': True, 'branch': (git(cwd, 'rev-parse', '--abbrev-ref', 'HEAD') or '').strip(),
            'head': (git(cwd, 'rev-parse', '--short', 'HEAD') or '').strip(), 'changed': changed}


def run_test(cwd, cmd, timeout=120):
    """(ok, last output line). Runs the user's own test command; timeout counts as failure."""
    try:
        r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        out = [l for l in (r.stdout + r.stderr).splitlines() if l.strip()]
        return r.returncode == 0, (out[-1][:160] if out else '')
    except subprocess.TimeoutExpired:
        return False, f'timeout after {timeout}s'
    except Exception as e:
        return False, str(e)[:160]


def hdir(cwd):
    return os.path.join(cwd, 'handoffs')


def remember(cwd, fact):
    """Append one dated fact to MEMORY.md unless the same text is already there. True if added."""
    fact = ' '.join(fact.split())[:300]
    if not fact:
        return False
    os.makedirs(hdir(cwd), exist_ok=True)
    p = os.path.join(hdir(cwd), 'MASTER.md')
    old = open(p, encoding='utf-8', errors='ignore').read() if os.path.exists(p) else '# Project master memory (tz): stable facts only\n'
    if any(l[13:] == fact for l in old.splitlines() if l.startswith('- ')):
        return False
    open(p, 'w', encoding='utf-8').write(old.rstrip('\n') + f"\n- {time.strftime('%Y-%m-%d')} {fact}\n")
    return True


def task_path(cwd, task=''):
    slug = ''.join(c if c.isalnum() else '-' for c in task.lower()).strip('-')[:40] or 'active'
    return os.path.join(hdir(cwd), 'tasks', slug + '.json')


def newest_task(cwd):
    import glob
    fs = glob.glob(os.path.join(hdir(cwd), 'tasks', '*.json'))
    fs = [f for f in fs if not os.path.basename(f).startswith('T-')]  # T-*.json = tznext tasks
    return max(fs, key=os.path.getmtime) if fs else None


# tail_lines: copied from planning-with-files scripts/inject-plan.py (MIT, Copyright (c) 2026 Ahmad Adi); see NOTICE.
def tail_lines(data, n):
    """`tail -N`: the last N lines; a final partial line counts as one."""
    if not data:
        return b""
    body = data[:-1] if data.endswith(b"\n") else data
    parts = body.split(b"\n")
    kept = parts[-n:] if n < len(parts) else parts
    out = b"\n".join(kept)
    if data.endswith(b"\n"):
        out += b"\n"
    return out


def memory_tail(cwd, n=MEM_TAIL):
    p = os.path.join(hdir(cwd), 'MASTER.md')
    try:
        with open(p, 'rb') as f:  # bound the work: only the last ~64 KB of a long memory file is ever decoded
            f.seek(0, 2); sz = f.tell(); f.seek(max(0, sz - 65536)); raw = f.read()
        txt = tail_lines(raw, 400).decode('utf-8', 'ignore')
        return [l for l in txt.splitlines() if l.startswith('- ')][-n:]
    except OSError:
        return []


def chain_id(cwd, task=''):
    """Stable id linking successive handoffs of one task: reuse the previous state's chain, else new. Returns (chain, seq)."""
    try:
        old = json.load(open(task_path(cwd, task)))
        return old.get('chain') or hashlib.sha1((cwd + task + str(old.get('time'))).encode()).hexdigest()[:8], int(old.get('seq', 0)) + 1
    except Exception:
        return hashlib.sha1((cwd + task + str(time.time())).encode()).hexdigest()[:8], 1


def import_jsonl(path, n=8):
    """Facts from a crashed/ended chat log (MEASURED, no model call): last user asks, files edited, last tool errors. Bad/partial lines skipped."""
    asks, files, errs = [], [], []
    for ln in open(path, errors='replace'):
        try:
            m = json.loads(ln).get('message') or {}
        except Exception:
            continue
        c = m.get('content') if isinstance(m, dict) else None
        if isinstance(c, str) and c.strip() and m.get('role') == 'user':
            asks.append(c.strip()[:160])
        for b in c if isinstance(c, list) else []:
            if not isinstance(b, dict):
                continue
            if b.get('type') == 'text' and m.get('role') == 'user' and b.get('text', '').strip():
                asks.append(b['text'].strip()[:160])
            inp = b.get('input') or {}
            if b.get('type') == 'tool_use' and inp.get('file_path') and b.get('name') in ('Edit', 'Write', 'MultiEdit'):
                files.append(inp['file_path'])
            if b.get('type') == 'tool_result' and b.get('is_error'):
                errs.append(str(b.get('content'))[:120])
    return {'asks': asks[-3:], 'files': list(dict.fromkeys(files))[-n:], 'errors': errs[-3:]}


def handoff(cwd, task='', done=(), left=(), nxt='', test_cmd='', facts=()):
    """Write state + daily note. Returns (md_path, state). Done items count as verified only if the test passed."""
    snap = snapshot(cwd)
    test = {'cmd': '', 'ok': None, 'last': ''}
    if test_cmd:
        ok, last = run_test(cwd, test_cmd)
        test = {'cmd': test_cmd, 'ok': ok, 'last': last}
    for f in facts:
        remember(cwd, f)
    chain, seq = chain_id(cwd, task)
    state = {'v': 1, 'chain': chain, 'seq': seq, 'time': time.strftime('%Y-%m-%d %H:%M'), 'cwd': cwd, 'task': task, 'done': list(done),
             'left': list(left), 'next': nxt, 'test': test, **snap}
    tp = task_path(cwd, task)
    os.makedirs(os.path.dirname(tp), exist_ok=True)
    json.dump(state, open(tp + '.tmp', 'w'), indent=1)
    os.replace(tp + '.tmp', tp)
    verified = test['ok'] is True
    lines = [f"# Handoff {state['time']} (tz): {task or 'task'} [chain {chain} #{seq}]",
             'Status: ' + ('tests pass' if verified else 'tests FAILED' if test['ok'] is False else 'tests not run'),
             f"Done ({'verified by test' if verified else 'UNVERIFIED'}): " + ('; '.join(done) or 'nothing listed'),
             'Left: ' + ('; '.join(left) or 'nothing listed'),
             'NEXT ACTION: ' + (nxt or 'not set'),
             f"Git: {snap['branch']}@{snap['head']}, {len(snap['changed'])} uncommitted" if snap['repo'] else 'Git: not a repo',
             'Changed: ' + (', '.join(list(snap['changed'])[:12]) + (f" +{len(snap['changed']) - 12} more" if len(snap['changed']) > 12 else '')
                            if snap['changed'] else 'none'),
             'Test: ' + (f"`{test['cmd']}` -> {'exit 0' if test['ok'] else 'FAILED'}: {test['last']}" if test['cmd'] else 'none run'),
             'Resume: tz resume (verifies this against git and tests before you continue)']
    md = os.path.join(hdir(cwd), time.strftime('%Y-%m-%d') + '-tz.md')
    open(md, 'w', encoding='utf-8').write('\n'.join(lines[:30]) + '\n')
    return md, state


def resume(cwd, run_tests=False):
    """Compare saved state with now. Returns (text, drift list). Read-only for the work tree."""
    try:
        sp = newest_task(cwd) or ''
        s = json.load(open(sp))
        try:  # continuation-consumed signal: a new chat read this handoff (TZ's own state file, fail open)
            s['consumed'] = list(s.get('consumed') or [])[-4:] + [int(time.time())]
            json.dump(s, open(sp, 'w'), indent=1)
        except OSError:
            pass
    except (OSError, ValueError):
        try:  # no tz handoff yet: fall back to the active `tz next` task pack so a fresh chat still resumes
            import tznext
            p = tznext.pack(cwd)
        except Exception:
            p = ''
        if p:
            return 'TZ resume (from tz next, no tz handoff yet):\n' + p, ['no-handoff']
        return 'TZ resume: no valid task state in handoffs/tasks/. Run `tz handoff` first, or read the newest handoffs/*.md.', ['no-state']
    now = snapshot(cwd)
    drift = []
    if s.get('repo') != now['repo']:
        drift.append('git repo presence changed')
    if now['repo'] and s.get('repo'):
        if now['branch'] != s['branch']:
            drift.append(f"branch {s['branch']} -> {now['branch']}")
        if now['head'] != s['head']:
            n = (git(cwd, 'rev-list', '--count', f"{s['head']}..HEAD") or '?').strip()
            drift.append(f"HEAD {s['head']} -> {now['head']} ({n} new commits)")
    old, cur = s.get('changed', {}), now['changed']
    mod = [f for f in cur if f in old and cur[f] != old[f]]
    new = [f for f in cur if f not in old]
    gone = [f for f in old if f not in cur]
    for label, fl in (('edited since handoff', mod), ('new uncommitted', new), ('no longer changed (committed/reverted)', gone)):
        if fl:
            drift.append(f"{label}: " + ', '.join(fl[:6]) + (f' +{len(fl) - 6}' if len(fl) > 6 else ''))
    t = s.get('test') or {}
    tline = 'Test: none recorded'
    if t.get('cmd'):
        tline = f"Test at handoff: `{t['cmd']}` -> {'pass' if t['ok'] else 'FAILED'}"
        if run_tests:
            ok, last = run_test(cwd, t['cmd'])
            tline += f" | now: {'pass' if ok else 'FAILED'} ({last})"
            if ok != t['ok']:
                drift.append('test result changed')
    out = [f"TZ resume: {s.get('task') or 'task'} (handoff {s.get('time')})",
           'State: ' + ('CLEAN, matches handoff' if not drift else 'DRIFT, check before trusting the notes'),
           *[f'  - {d}' for d in drift],
           'Done: ' + ('; '.join(s.get('done', [])) or 'none') + ('' if t.get('ok') else ' (UNVERIFIED: no passing test at handoff)'),
           'Left: ' + ('; '.join(s.get('left', [])) or 'none'), tline,
           'NEXT ACTION: ' + (s.get('next') or 'not set'),
           'Uncommitted changes are untouched; nothing was modified.']
    mem = memory_tail(cwd)
    if mem:
        out += ['Project memory:', *mem]
    return '\n'.join(out), drift


def daily(cwd, line):
    """Append one line to handoffs/DAILY.md under today's heading. Never rewrites history."""
    os.makedirs(hdir(cwd), exist_ok=True)
    p = os.path.join(hdir(cwd), 'DAILY.md')
    old = open(p, encoding='utf-8', errors='ignore').read() if os.path.exists(p) else '# Daily log (tz)\n'
    head = f"\n## {time.strftime('%Y-%m-%d')}\n"
    if head not in old:
        old += head
    open(p, 'w', encoding='utf-8').write(old.rstrip('\n') + f"\n- {time.strftime('%H:%M')} {line}\n")


def checkpoint(cwd):
    """Cheap safe checkpoint (no test run, no commands): refresh git snapshot of the newest task state. Keeps notes and test record.
    Returns state path or None if there is no task state yet."""
    tp = newest_task(cwd)
    try:
        s = json.load(open(tp or ''))
    except (OSError, ValueError):
        return None
    s.update(snapshot(cwd), time=time.strftime('%Y-%m-%d %H:%M'), checkpoint=True)
    json.dump(s, open(tp + '.tmp', 'w'), indent=1)
    os.replace(tp + '.tmp', tp)
    daily(cwd, f"checkpoint: {s.get('task') or 'task'} ({len(s['changed'])} uncommitted)")
    return tp


def wrap(cwd, summary='', decisions=(), test_cmd='', force=False):
    """Close the active task. 'done' only if the given test passed; otherwise status stays open (force => done-unverified).
    Decisions go to MASTER.md, one line to DAILY.md. Returns (status, message)."""
    tp = newest_task(cwd)
    try:
        s = json.load(open(tp or ''))
    except (OSError, ValueError):
        return 'no-state', 'tz task-wrap: no task state. Run tz handoff first.'
    ok = None
    if test_cmd:
        ok, last = run_test(cwd, test_cmd)
        s['test'] = {'cmd': test_cmd, 'ok': ok, 'last': last}
    elif (s.get('test') or {}).get('ok'):
        ok = False  # a pass recorded earlier is not proof for the code as it is now
    snap = snapshot(cwd)
    drift = snap['changed'] != s.get('changed') and ok is not True
    status = 'done' if ok else ('done-unverified' if force else 'open')
    if status == 'open':
        return 'open', 'tz task-wrap: not closed. Pass --test "<your test command>" and make it pass, or --force for done-unverified.' + (' (files changed since last handoff)' if drift else '')
    s.update(snap, status=status, time=time.strftime('%Y-%m-%d %H:%M'), next='start the next task in a fresh session')
    json.dump(s, open(tp + '.tmp', 'w'), indent=1)
    os.replace(tp + '.tmp', tp)
    for d in decisions:
        remember(cwd, d)
    daily(cwd, f"{status.upper()}: {s.get('task') or 'task'}" + (f" - {summary}" if summary else '') + f" ({len(snap['changed'])} uncommitted files left for you to commit)")
    return status, f"tz task-wrap: {status}. Logged to handoffs/DAILY.md; {len(decisions)} decision(s) to MASTER.md. Next independent task: start a fresh session (nothing was committed)."


def _interactive():
    """stdin is a real terminal. Windows: isatty() is also True for NUL (</dev/null), so ask the console API instead."""
    if not sys.stdin.isatty():
        return False
    if os.name != 'nt':
        return True
    try:
        import ctypes
        k = ctypes.windll.kernel32
        return bool(k.GetConsoleMode(k.GetStdHandle(-10), ctypes.byref(ctypes.c_uint())))
    except Exception:
        return False


def confirm(cmd, yes):
    """Run a user-supplied test command only after consent: --yes, or an interactive y at a terminal. Never silently."""
    if not cmd or yes:
        return True
    if _interactive():
        return input(f'tz will run this command with your permissions:\n  {cmd}\nRun it? [y/N] ').strip().lower() == 'y'
    print(f'tz: refusing to run `{cmd}` without consent. Re-run with --yes to allow it.', file=sys.stderr)
    return False


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='tz handoff|resume')
    ap.add_argument('cmd', choices=['handoff', 'resume', 'task-wrap', 'checkpoint', 'import'])
    ap.add_argument('--cwd', default=os.getcwd())
    ap.add_argument('--task', default='')
    ap.add_argument('--done', action='append', default=[])
    ap.add_argument('--left', action='append', default=[])
    ap.add_argument('--next', dest='nxt', default='')
    ap.add_argument('--test', default='', help='test command to run and record')
    ap.add_argument('--remember', action='append', default=[], help='persistent project fact')
    ap.add_argument('--summary', default='')
    ap.add_argument('--yes', action='store_true', help='consent to run the --test command')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--from', dest='src', default='', help='import: crashed/ended chat .jsonl')
    ap.add_argument('--run-test', action='store_true', help='resume: rerun recorded test')
    a = ap.parse_args(argv)
    cwd = os.path.abspath(a.cwd)
    if not os.path.isdir(cwd):
        print(f'tz: not a directory: {cwd}', file=sys.stderr)
        return 2
    if a.cmd in ('handoff', 'task-wrap') and not confirm(a.test, a.yes):
        return 2
    if a.cmd == 'task-wrap':
        st, msg = wrap(cwd, a.summary, a.remember, a.test, a.force)
        print(msg)
        return 0 if st in ('done', 'done-unverified') else 1
    if a.cmd == 'import':
        if not os.path.isfile(a.src):
            print('tz import: pass --from CHAT.jsonl'); return 2
        f = import_jsonl(a.src)
        md, st = handoff(cwd, a.task, done=[], left=['last ask: ' + x for x in f['asks'][-1:]], nxt='review files edited in the crashed chat',
                         facts=())
        print(f"imported [MEASURED from log, chain {st['chain']} #{st['seq']}]: files {f['files']}; last errors {f['errors']}; last asks {f['asks']}")
        return 0
    if a.cmd == 'checkpoint':
        p = checkpoint(cwd)
        print('checkpoint saved' if p else 'no task state; nothing to checkpoint')
        return 0 if p else 1
    if a.cmd == 'handoff':
        md, _ = handoff(cwd, a.task, a.done, a.left, a.nxt, a.test, a.remember)
        print(open(md, encoding='utf-8').read(), end='')
        return 0
    if a.run_test:
        try:
            rec = json.load(open(newest_task(cwd) or '')).get('test', {}).get('cmd', '')
        except (OSError, ValueError):
            rec = ''
        if not confirm(rec, a.yes):
            return 2
    text, drift = resume(cwd, a.run_test)
    print(text)
    return 1 if 'no-state' in drift else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
