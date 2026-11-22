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


def live():
    p = os.path.expanduser('~/.claude/token-zombie/hook-times.json')
    try:
        return json.load(open(p))
    except Exception:
        return {}


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='tz hooks')
    ap.add_argument('cmd', choices=['bench', 'live'])
    ap.add_argument('--mb', type=float, default=20)
    ap.add_argument('--n', type=int, default=7)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
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
            print(f"  {k:18} n {v.get('n', 0):6}  total {v.get('ms', 0):9.0f} ms  max {v.get('max', 0):6.0f} ms  injected ~{v.get('chars', 0) // 4} tok [EST]")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
