#!/usr/bin/env python3
# `tz worker detect|add|list|test|run|rm` and `tz hw`: provider-independent worker registry (TZ 3.0 phase 1).
# A worker is one of: cli (command template with {prompt}, no shell), http (OpenAI-compatible /chat/completions,
# e.g. llama-server or Ollama on localhost), offline (no model, deterministic tz tools only).
# Registry: ~/.claude/token-zombie/workers.json. Nothing is called unless you run/test it. Stdlib only.
import json, os, platform, shlex, shutil, subprocess, sys, urllib.request
STATE = os.environ.get('TZ_WORKERS_DIR') or os.path.expanduser('~/.claude/token-zombie')
# Known CLIs and how to call them non-interactively. Flags are the documented headless forms; verify with `tz worker test`.
KNOWN = {
    'claude': 'claude -p {prompt}', 'codex': 'codex exec {prompt}', 'gemini': 'gemini -p {prompt}',
    'opencode': 'opencode run {prompt}', 'aider': 'aider --yes --message {prompt}',
}
# Tier table from docs/OPEN-CORE-DECISION.md section 4 (ESTIMATES, not measured on this machine).
TIERS = [(8, '1.5-4B dense, 4-bit: classification and tiny edits only'),
         (16, '7-14B dense, 4-bit, 8-16k context: drafts, single-file edits, review'),
         (24, '30B-A3B MoE at Q3-Q4, short context: slow local agent'),
         (32, '30B-A3B Q4 with 16-32k context, or 14-24B dense: usable local worker'),
         (10**6, '70B-class Q4 or 30B-A3B high precision: strong local worker')]


def path():
    return os.path.join(STATE, 'workers.json')


def load():
    try:
        return json.load(open(path()))
    except Exception:
        return {}


def save(w):
    os.makedirs(STATE, exist_ok=True)
    json.dump(w, open(path(), 'w'), indent=1)


def detect():
    """Installed worker CLIs and local runtimes found on PATH (no calls made)."""
    found = {n: shutil.which(n) for n in list(KNOWN) + ['ollama', 'llama-server']}
    return {k: v for k, v in found.items() if v}


def invoke(name, prompt, cwd=None, timeout=900):
    """Run one worker. Returns (text, error). cli: argv list, never a shell; http: OpenAI-compatible chat call."""
    w = load().get(name)
    if not w:
        return '', 'unknown worker %s' % name
    try:
        if w['kind'] == 'offline':
            return '', 'offline worker runs tz tools only, no model'
        if w['kind'] == 'cli':
            argv = [a.replace('{prompt}', prompt) for a in shlex.split(w['cmd'])]
            r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout)
            return r.stdout.strip(), None if r.returncode == 0 else 'exit %d: %s' % (r.returncode, r.stderr[-200:])
        body = json.dumps({'model': w.get('model', ''), 'messages': [{'role': 'user', 'content': prompt}]}).encode()
        req = urllib.request.Request(w['url'].rstrip('/') + '/chat/completions', body, {'Content-Type': 'application/json'})
        d = json.load(urllib.request.urlopen(req, timeout=timeout))
        return d['choices'][0]['message']['content'], None
    except Exception as e:
        return '', '%s: %s' % (type(e).__name__, e)


def hw():
    mem = 0
    try:
        mem = int(subprocess.run(['sysctl', '-n', 'hw.memsize'], capture_output=True, text=True).stdout) // 2**30
    except Exception:
        try:
            mem = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') // 2**30
        except Exception:
            pass
    chip = platform.processor() or platform.machine()
    if platform.system() == 'Darwin':
        chip = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'], capture_output=True, text=True).stdout.strip() or chip
    tier = next((t for g, t in TIERS if mem <= g), TIERS[-1][1]) if mem else 'unknown memory: cannot pick a tier'
    return {'chip': chip, 'memory_gb': mem, 'tier': tier, 'runtimes': {k: v for k, v in detect().items() if k in ('ollama', 'llama-server')}}


def main(argv):
    c = argv[0] if argv else ''
    a = argv[1:]
    if c == 'hw':
        h = hw()
        print('%s, %s GB unified/RAM' % (h['chip'], h['memory_gb']))
        print('fits (ESTIMATE, not measured): ' + h['tier'])
        print('local runtimes: ' + (', '.join(h['runtimes']) or 'none found (install llama.cpp or Ollama)'))
        return 0
    w = load()
    if a and a[0] == 'worker':
        a = a[1:]
    sub = a[0] if a else 'list'
    rest = a[1:]
    op = lambda k, d=None: rest[rest.index(k) + 1] if k in rest and rest.index(k) + 1 < len(rest) else d
    if sub == 'detect':
        for n, p in detect().items():
            print('%-12s %s%s' % (n, p, '' if n in w else '   (add with: tz worker add %s --kind cli --cmd "%s")' % (n, KNOWN.get(n, '...')) if n in KNOWN else ''))
        return 0
    if sub == 'list':
        print('%-10s %-8s %s' % ('offline', 'builtin', 'deterministic tz tools, 0 tokens'))
        for n, v in w.items():
            print('%-10s %-8s %s' % (n, v['kind'], v.get('cmd') or v.get('url')))
        return 0
    if sub == 'add' and rest:
        n, kind = rest[0], op('--kind', 'cli')
        if kind == 'cli':
            cmd = op('--cmd') or KNOWN.get(n)
            if not cmd or '{prompt}' not in cmd:
                print('usage: tz worker add NAME --kind cli --cmd "tool {prompt}"', file=sys.stderr); return 2
            w[n] = {'kind': 'cli', 'cmd': cmd}
        elif kind == 'http':
            if not op('--url'):
                print('usage: tz worker add NAME --kind http --url http://localhost:8080/v1 [--model M]', file=sys.stderr); return 2
            w[n] = {'kind': 'http', 'url': op('--url'), 'model': op('--model', '')}
        else:
            print('kind must be cli or http', file=sys.stderr); return 2
        save(w); print('added %s' % n); return 0
    if sub == 'rm' and rest:
        w.pop(rest[0], None); save(w); return 0
    if sub in ('test', 'run') and rest:
        prompt = ' '.join(rest[1:]) if sub == 'run' else 'Reply with the single word OK.'
        txt, err = invoke(rest[0], prompt, os.getcwd())
        print(txt if sub == 'run' else ('OK' if not err and txt else 'FAIL ' + (err or 'empty reply')))
        if err:
            print(err, file=sys.stderr)
        return 1 if err or not txt else 0
    print('usage: tz worker detect|list|add NAME --kind cli|http ...|rm NAME|test NAME|run NAME "prompt"   |   tz hw', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
