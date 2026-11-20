#!/usr/bin/env python3
# Status bus I/O, dependency-light (statusline imports this: no transcript parsing, no tzusage).
# status.json = written by the supervisor tick. activity.json = written by every hook event (tiny).
# Activity is MEASURED only from hook events: working after Prompt/Tool events, idle after Stop/SessionEnd.
# No event for ACT_STALE seconds while "working" (Stop never arrived: crash/interrupt) or no hooks installed => UNKNOWN. Never guessed from file mtimes.
import json, os, time

ACT_STALE = 900
WORK = ('UserPromptSubmit', 'PreToolUse', 'PostToolUse', 'SubagentStop', 'PreCompact', 'SessionStart')
IDLE = ('Stop', 'SessionEnd')


def sdir():
    d = os.path.expanduser('~/.claude/token-zombie')
    os.makedirs(d, exist_ok=True)
    return d


def read(name, dflt):
    try:
        v = json.load(open(os.path.join(sdir(), name)))
        return v if isinstance(v, type(dflt)) else dflt
    except Exception:
        return dflt


def write(name, obj):
    p = os.path.join(sdir(), name)
    tmp = f'{p}.{os.getpid()}.tmp'
    json.dump(obj, open(tmp, 'w'), indent=1)
    os.replace(tmp, p)


def record_event(ev, session=''):
    write('activity.json', dict(event=ev, ts=int(time.time()), session=session))


def activity(now=None):
    """(value, source): working|idle|UNKNOWN, 'hook' when measured."""
    a = read('activity.json', {})
    if not a.get('ts'):
        return 'UNKNOWN', 'no hook events seen'
    age = (now or time.time()) - a['ts']
    if a.get('event') in IDLE:
        return 'idle', 'hook'
    if a.get('event') in WORK and age <= ACT_STALE:
        return 'working', 'hook'
    return 'UNKNOWN', 'stale: no Stop event'


def read_bus(now=None):
    """status.json merged with live activity; {} when nothing recorded. Always a dict, never raises."""
    s = read('status.json', {})
    if s:
        s['activity'], s['activity_src'] = activity(now)
    return s
