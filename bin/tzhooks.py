#!/usr/bin/env python3
# Hook execution-time baseline + TZ's own live hook overhead. All local, no model calls.
# `tz hooks bench [--mb N] [--n N] [--json]`: runs the real hook scripts with each event payload against a synthetic
#   transcript in a temp HOME (live ~/.claude untouched). Wall ms per run = python start + hook body, MEASURED on this machine.
# `tz hooks live [--json]`: per-event count / total / max body ms that the guard recorded in ~/.claude/token-zombie/hook-times.json
#   (MEASURED in-process; excludes interpreter start, which `bench` includes) + chars TZ injected (EST tokens = chars/4).
import json, os, statistics, subprocess, sys, tempfile, time

D = os.path.dirname(os.path.abspath(__file__))
EVENTS = [('UserPromptSubmit', 'tz-guard.py', {'prompt': 'fix the bug'}),
          ('PreToolUse', 'tz-guard.py', {'tool_name': 'Read', 'tool_input': {'file_path': '/etc/hosts'}}),
          ('PreToolUse:Grep', 'tz-guard.py', {'tool_name': 'Grep', 'tool_input': {'pattern': 'x', 'path': '.'}}),
          ('PostToolUse', 'tz-guard.py', {'tool_name': 'Bash', 'tool_input': {'command': 'ls'}, 'tool_response': {}}),
          ('Stop', 'tz-guard.py', {}), ('SessionStart', 'tz-start.py', {}),
          ('PreCompact', 'tz-guard.py', {}), ('SessionEnd', 'tz-guard.py', {}),
          ('SubagentStart', 'tz-guard.py', {'agent_id': 'a1', 'agent_type': 'general-purpose'}),
          ('SubagentStop', 'tz-guard.py', {'agent_id': 'a1', 'agent_type': 'general-purpose'}),
          ('InstructionsLoaded', 'tz-guard.py', {'file_path': '/tmp/CLAUDE.md', 'load_reason': 'session_start'}),
          ('PostCompact', 'tz-guard.py', {'compact_summary': 'summary'}),
          ('PostToolUseFailure', 'tz-guard.py', {'tool_name': 'Bash', 'tool_input': {'command': 'false'}, 'error': 'exit 1'}),
          ('PostToolBatch', 'tz-guard.py', {}),
          ('PreModelSwitch', 'tz-guard.py', {'model': 'claude-sonnet-5-5'}), ('PostModelSwitch', 'tz-guard.py', {'model': 'claude-opus-5-5'}),
          ('WorktreeCreate', 'tz-guard.py', {'name': 'w1'}), ('WorktreeRemove', 'tz-guard.py', {'name': 'w1'}),
          ('FileChanged', 'tz-guard.py', {'file_path': '/tmp/x.py'})]


def transcript(path, mb):
    """Synthetic chat log: `mb` MB of startup/tool lines before the first reply usage, then a few replies."""
    pad = json.dumps({'type': 'user', 'message': {'content': 'x' * 4000}}) + '\n'
    rep = lambda n: json.dumps({'type': 'assistant', 'message': {'id': f'm{n}', 'usage': {'input_tokens': 5, 'output_tokens': 50,
                               'cache_read_input_tokens': 40000 + n * 1000, 'cache_creation_input_tokens': 500}}}) + '\n'
    with open(path, 'w') as f:
        f.write(pad * max(1, int(mb * 1024 * 1024 / len(pad))))
        for n in range(20):
            f.write(rep(n) + pad)


def bench(mb=20, n=7):
    T = tempfile.mkdtemp(prefix='tzhooks-')
    H = os.path.join(T, 'home'); os.makedirs(H + '/.claude')
    tp = os.path.join(T, 'chat.jsonl'); transcript(tp, mb)
    env = dict(os.environ, HOME=H, TZ_SUP=os.environ.get('TZ_SUP', '1'))
    rows = {}
    for name, script, extra in EVENTS:
        ev = name.split(':')[0]
        ms = []
        for i in range(n):
            pl = dict(extra, hook_event_name=ev, session_id='bench', transcript_path=tp, cwd=T)
            t = time.perf_counter()
            subprocess.run([sys.executable, os.path.join(D, script)], input=json.dumps(pl), capture_output=True, text=True, env=env, timeout=30)
            ms.append((time.perf_counter() - t) * 1000)
        ms.sort()
        rows[name] = dict(median=round(statistics.median(ms), 1), p95=round(ms[min(len(ms) - 1, int(len(ms) * .95))], 1), max=round(ms[-1], 1))
    t = time.perf_counter(); subprocess.run([sys.executable, '-c', 'pass']); py = round((time.perf_counter() - t) * 1000, 1)
    return dict(transcript_mb=mb, runs=n, python_start_ms=py, events=rows, basis='MEASURED wall ms, this machine')


def live(home=None):
    """Aggregate per-event hook stats (MEASURED) over every live-<session>.json the guard wrote."""
    import glob
    d = os.path.join(home or os.path.expanduser('~'), '.claude', 'token-zombie')
    agg = {}
    for f in glob.glob(os.path.join(d, 'live-*.json')):
        try:
            hs = json.load(open(f)).get('hooks') or {}
        except Exception:
            continue
        for ev, h in hs.items():
            a = agg.setdefault(ev, dict(n=0, ms=0.0, max=0.0, chars=0, fail=0, samples=[]))
            a['n'] += h.get('n', 0); a['ms'] += h.get('ms', 0); a['max'] = max(a['max'], h.get('max', 0))
            a['chars'] += h.get('chars', 0); a['fail'] += h.get('fail', 0); a['samples'] += h.get('samples', [])
    for a in agg.values():
        sm = sorted(a.pop('samples'))
        a['p50'] = round(statistics.median(sm), 1) if sm else None
        a['p95'] = round(sm[min(len(sm) - 1, int(len(sm) * .95))], 1) if sm else None
        a['sampled'] = len(sm)
    return agg


def proof():
    """Events the mod really received in live chats (hookproof-<session>.json, written by hooks/tools.ts). [MEASURED]; none = the mod has not run in a live chat yet."""
    import glob
    fs = sorted(glob.glob(os.path.join(os.path.expanduser('~/.claude/token-zombie'), 'hookproof-*.json')), key=os.path.getmtime)[-5:]
    if not fs:
        print('hook proof: no live-chat record yet (the mod writes it on the first prompt in a chat with this plugin loaded)'); return 0
    for f in fs:
        try:
            d = json.load(open(f))
            print(os.path.basename(f)[10:-5][:12], ', '.join('%s x%d' % kv for kv in sorted(d.get('seen', {}).items())))
        except Exception:
            continue
    return 0


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='tz hooks')
    ap.add_argument('cmd', choices=['bench', 'live', 'proof'])
    ap.add_argument('--mb', type=float, default=20)
    ap.add_argument('--n', type=int, default=7)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    if a.cmd == 'proof':
        return proof()
    r = bench(a.mb, a.n) if a.cmd == 'bench' else live()
    if a.json:
        print(json.dumps(r, indent=1)); return 0
    if a.cmd == 'bench':
        print(f"hook wall time [MEASURED], {r['runs']} runs, transcript {r['transcript_mb']} MB, bare python start {r['python_start_ms']} ms")
        for k, v in r['events'].items():
            print(f"  {k:18} median {v['median']:7.1f}  p95 {v['p95']:7.1f}  max {v['max']:7.1f} ms")
        return 0
    if not r:
        print('no live hook timings yet (UNKNOWN): the guard records them once this version is installed'); return 0
    for k, v in sorted(r.items()):
        if isinstance(v, dict):
            print(f"  {k:18} n {v.get('n', 0):6}  p50 {v.get('p50')} p95 {v.get('p95')} max {v.get('max', 0):6.0f} ms  fail {v.get('fail', 0)}  injected ~{v.get('chars', 0) // 4} tok [EST]")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
