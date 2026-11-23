#!/usr/bin/env python3
# Supervisor + shared status bus. tick() is cheap (no tests, no network, no launches): usage level + burn -> auto checkpoint
# -> handoff prep at CRITICAL -> write ~/.claude/token-zombie/status.json (read by dash/companion/statusline).
# Honest limit: the host cannot be forced to open a fresh session; next-session emits the exact command/brief. Launch only with --yes.
import json, os, shlex, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tzusage, tzhandoff
from tzmascot import mascot_state, EMOJI
import tzbus


sdir = tzbus.sdir
CKPT_GAP = 120  # seconds between auto checkpoints (each logs a DAILY line)


def _w(path, obj):
    json.dump(obj, open(path + '.tmp', 'w'), indent=1)
    os.replace(path + '.tmp', path)


def _r(path, dflt, ok=None):
    """Read JSON. Missing -> dflt. Unreadable, malformed or schema-invalid -> quarantine (see _quarantine), return dflt.
    Schema: ok(v) when given, else v must be a dict when dflt is None, else the same type as dflt."""
    try:
        v = json.load(open(path))
        good = bool(ok(v)) if ok else isinstance(v, dict if dflt is None else type(dflt))
    except FileNotFoundError:
        return dflt
    except Exception:
        good = False
    if good:
        return v
    _quarantine(path)  # corrupt (interrupted write, hand edit): keep evidence, start clean
    return dflt


def _quarantine(path):
    """Move path to the first free name of path.corrupt, path.corrupt.1, .2 ...; never overwrites earlier evidence."""
    for n in range(1000):
        q = path + '.corrupt' + (f'.{n}' if n else '')
        try:  # claim the name atomically, so two hooks quarantining at once never share one
            os.close(os.open(q, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        except FileExistsError:
            continue
        except OSError:
            return
        try:
            os.replace(path, q)
        except OSError:  # source already gone (another hook moved it): drop the empty claim
            try:
                os.remove(q)
            except OSError:
                pass
        return


def tasks():
    return _r(os.path.join(sdir(), 'tasks.json'), {'tasks': []},
              lambda v: isinstance(v, dict) and isinstance(v.get('tasks'), list) and all(isinstance(t, dict) and 'status' in t for t in v['tasks']))


def task_set(tid, project='', status='open', session=''):
    if status not in ('open', 'done', 'blocked'):
        raise SystemExit('status must be open|done|blocked')
    d = tasks()
    t = next((x for x in d['tasks'] if x['id'] == tid), None)
    if not t:
        t = dict(id=tid, project=project, status=status, sessions=[])
        d['tasks'].append(t)
    t['status'] = status
    if project:
        t['project'] = project
    if session and session not in t['sessions']:
        t['sessions'].append(session)
    t['updated'] = time.strftime('%Y-%m-%d %H:%M')
    _w(os.path.join(sdir(), 'tasks.json'), d)
    return t


def risk(info):
    """low|medium|high: from level and minutes until the window is full (est)."""
    lv, mins = info.get('level'), info.get('mins') or 0
    if lv in ('CRITICAL', 'EXHAUSTED'):
        return 'high'
    if lv == 'APPROACHING LIMIT' or (0 < mins < 15):
        return 'high' if 0 < mins < 5 else 'medium'
    return 'medium' if lv == 'ELEVATED' else 'low'


def tick(transcript, cwd, rl=None):
    t0 = time.time()
    _, info = tzusage.report(transcript, rl)
    lv = tzusage.level(info['ctx_pct'], info['limits'])
    info['level'] = lv
    acts = []
    try:
        import tzintegrity
        if info.get('ctx_pct'):
            m = tzintegrity.ctx_mark(cwd, info['ctx_pct'])
            if m:
                acts.append(f'ctx-mark-{m}')
    except Exception:
        pass  # fail open
    prev = _r(os.path.join(sdir(), 'status.json'), {})
    last_ck = prev.get('last_checkpoint', 0)
    if lv in ('APPROACHING LIMIT', 'CRITICAL', 'EXHAUSTED') and time.time() - last_ck >= CKPT_GAP:
        if tzhandoff.checkpoint(cwd):
            acts.append('checkpoint')
            last_ck = int(time.time())
    if lv in ('CRITICAL', 'EXHAUSTED'):
        acts.append('handoff-prep')  # brief only; the model/user writes the handoff, tz runs no tests here
    open_t = [t for t in tasks()['tasks'] if t['status'] == 'open']
    s = dict(ts=int(time.time()), cwd=cwd, level=lv, ctx_pct=info['ctx_pct'], state=info['state'], mins=int(info['mins'] or 0),
             rate=int(info['rate'] or 0), last_checkpoint=last_ck, risk=risk(dict(info, level=lv)), actions=acts, open_tasks=len(open_t),
             limits=info['limits'], tokens=info['totals'],
             task_just_done=bool(prev.get('open_tasks', 0) > len(open_t)), tick_ms=0, label={'ctx_pct': 'actual/est', 'mins': 'est', 'activity': 'MEASURED from hook events, else UNKNOWN'})
    s['activity'], s['activity_src'] = tzbus.activity()
    s['mascot'] = mascot_state(s)
    s['emoji'] = EMOJI[s['mascot']]
    s['tick_ms'] = int((time.time() - t0) * 1000)
    _w(os.path.join(sdir(), 'status.json'), s)
    return s


def on_event(data):
    """Called by the hook for every lifecycle event. Cheap path for tool events; full tick only on prompt/compact/stop. TZ_SUP=0 = no-op."""
    if os.environ.get('TZ_SUP') == '0':
        return None
    ev = data.get('hook_event_name') or ''
    tzbus.record_event(ev, data.get('session_id', ''))
    if ev in ('UserPromptSubmit', 'PreCompact', 'Stop', 'SessionEnd'):
        return tick(data.get('transcript_path'), data.get('cwd') or os.getcwd())
    return None


def next_session(cwd):
    """Exact command/brief for a fresh session. Does not launch anything."""
    txt = tzhandoff.resume(cwd)[0]
    brief = 'Continue from the handoff. Run `tz resume`, then do the printed next action. One task, small reads only.'
    return f'cd {cwd} && claude -p {shlex.quote(brief)}\n--- resume summary ---\n{txt}'


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='tz sup')
    ap.add_argument('cmd', choices=['start', 'tick', 'status', 'next-session', 'task'])
    ap.add_argument('args', nargs='*')
    ap.add_argument('--transcript')
    ap.add_argument('--cwd', default=os.getcwd())
    ap.add_argument('--rate-limits')
    ap.add_argument('--yes', action='store_true')
    a = ap.parse_args(argv)
    cwd = os.path.abspath(a.cwd)
    if a.cmd == 'task':  # tz sup task <id> [open|done|blocked] [--cwd project]
        if not a.args:
            print(json.dumps(tasks(), indent=1))
            return 0
        print(json.dumps(task_set(a.args[0], cwd, a.args[1] if len(a.args) > 1 else 'open'), indent=1))
        return 0
    if a.cmd in ('start', 'tick'):
        rl = json.loads(a.rate_limits) if a.rate_limits else None
        s = tick(a.transcript or tzusage.find_transcript(cwd), cwd, rl)
        print(f"{s['emoji']} {s['level']} ctx {s['ctx_pct']}% risk {s['risk']} actions {','.join(s['actions']) or '-'}")
        return 0
    if a.cmd == 'status':
        s = _r(os.path.join(sdir(), 'status.json'), None)
        print(json.dumps(s, indent=1) if s else 'no status yet: run `tz sup tick`')
        return 0
    cmdline = next_session(cwd)
    print(cmdline)
    if a.yes:  # only launch on explicit consent; headless, one prompt
        subprocess.Popen(['claude', '-p', 'Continue from the handoff. Run `tz resume` and do the next action.'], cwd=cwd,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print('launched headless claude -p (--yes)')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
