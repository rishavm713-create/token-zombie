#!/usr/bin/env python3
# `tz agent "<task>" [--test CMD] [--worktree] [--files a,b] [--budget TOK] [--turns N] [--worker NAME] [--timeout S] [--dry]`: runs the tz code pipeline for real.
# Minimal loop in the spirit of mini-SWE-agent (MIT): one `claude -p` call per phase, small step cap, token budget, stop on failed test.
# Every phase is one ledger event (tz.db) and one checkpoint file. Permissions: edits only inside the work dir, no push/rm -rf/sudo.
# CLAUDE_BIN overrides the host binary (tests use tests/fake/claude.py). Fail-open: a ledger error never stops the run.
import json, os, re, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.expanduser('~/.claude/token-zombie')
DENY = ['Bash(git push:*)', 'Bash(rm -rf:*)', 'Bash(sudo:*)']
ALLOW = ['Read', 'Edit', 'Write', 'Glob', 'Grep', 'Bash(git:*)', 'Bash(python3:*)', 'Bash(npm:*)', 'Bash(bash:*)', 'Bash(rg:*)']
PHASES = ('plan', 'build', 'test', 'debug')


def slug(t):
    return ''.join(c if c.isalnum() else '-' for c in t.lower()).strip('-')[:40] or 'task'


def owners_path():
    return os.path.join(STATE, 'owners.json')


def claim(task, files, force=False):
    """File ownership: a file belongs to one task. Returns the list of files already owned by another task (empty = claimed)."""
    try:
        o = json.load(open(owners_path()))
    except Exception:
        o = {}
    clash = sorted(f for f in files if o.get(f) not in (None, task))
    if clash and not force:
        return clash
    for f in files:
        o[f] = task
    os.makedirs(STATE, exist_ok=True)
    json.dump(o, open(owners_path(), 'w'))
    return []


def release(task):
    try:
        o = {k: v for k, v in json.load(open(owners_path())).items() if v != task}
        json.dump(o, open(owners_path(), 'w'))
    except Exception:
        pass


def make_worktree(task, cwd):
    """Real worktree + branch for this task (tz/<slug>); returns its path."""
    p = os.path.join(os.path.dirname(os.path.abspath(cwd)), slug(task))
    if not os.path.isdir(p):
        subprocess.run(['git', 'worktree', 'add', p, '-b', 'tz/' + slug(task)], cwd=cwd, check=True, capture_output=True)
    return p


def call_claude(prompt, model, cwd, turns, timeout=1800):
    """One host call. Returns (text, tokens, error). Tokens = sum of usage in the stream (MEASURED when the host reports it)."""
    cmd = [os.environ.get('CLAUDE_BIN', 'claude'), '-p', prompt, '--model', model, '--output-format', 'stream-json', '--verbose',
           '--max-turns', str(turns), '--permission-mode', 'acceptEdits', '--allowedTools', ','.join(ALLOW), '--disallowedTools', ','.join(DENY)]
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        return '', 0, str(e)
    tok, text = 0, ''
    for ln in r.stdout.splitlines():
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        m = d.get('message')
        u = (m.get('usage') if isinstance(m, dict) else None) or {}
        tok += sum(u.get(k) or 0 for k in ('input_tokens', 'output_tokens', 'cache_creation_input_tokens'))
        if d.get('type') == 'result':
            text = str(d.get('result') or '')
    return text, tok, None if r.returncode == 0 else 'host exit %d' % r.returncode


def call(prompt, model, cwd, turns, worker=None, timeout=1800, edits=False):
    """One worker call through the registry. Returns (text, tokens, error, measured).
    'claude' (default, unless TZ_WORKER or `tz worker default` says otherwise) keeps the original host path with MEASURED usage.
    cli workers edit files themselves; http workers return text, so for edit phases a unified diff is requested and applied with git apply;
    the offline worker has no model and only reports that. Tokens for non-claude workers are EST (chars/4)."""
    import tzworkers
    w = worker or os.environ.get('TZ_WORKER') or tzworkers.default()
    if w == 'claude':
        t, k, e = call_claude(prompt, model, cwd, turns, timeout)
        return t, k, e, True
    reg = tzworkers.load()
    if w == 'offline':
        return '', 0, 'offline worker has no model: this phase needs a worker (tz worker default NAME)', False
    if w not in reg:
        return '', 0, 'unknown worker %s (tz worker list)' % w, False
    ask = prompt + ('\nReply ONLY with a unified diff in git apply format.' if edits and reg[w]['kind'] == 'http' else '')
    text, err = tzworkers.invoke(w, ask, cwd, timeout)
    if not err and edits and reg[w]['kind'] == 'http':
        err = tzworkers.apply_patch(text, cwd)
    return text, (len(ask) + len(text)) // 4, err, False


def ledger(**k):
    try:
        import tzdb
        tzdb.record('agent', k.get('run', ''), **k)
    except Exception:
        pass


def checkpoint(run, rows):
    d = os.path.join(STATE, 'agent'); os.makedirs(d, exist_ok=True)
    json.dump(rows, open(os.path.join(d, run + '.json'), 'w'))


def run(task, cwd, test=None, budget=400000, turns=20, worktree=False, dry=False, worker=None, timeout=1800):
    import tzsplit
    pipe = {r['phase']: r for r in tzsplit.code_pipeline(task) if r['phase'] in PHASES}
    rid = '%s-%d' % (slug(task)[:20], int(time.time()))
    if worktree and not dry:
        cwd = make_worktree(task, cwd)
    rows, spent, measured = [], 0, [True]
    def phase(ph, extra=''):
        nonlocal spent
        r = pipe[ph]
        if dry:
            rows.append(dict(phase=ph, model=r['model'], skill=r['skill'], status='dry')); return 'dry'
        if spent >= budget:
            rows.append(dict(phase=ph, status='budget')); return 'budget'
        sk = ' Use the %s skill if available.' % r['skill'] if r['skill'] else ''
        t0 = time.time()
        text, tok, err, m = call('Task: %s\nPhase: %s. %s%s %s' % (task, ph, r['rule'], sk, extra), r['model'], cwd, turns, worker, timeout, ph in ('build', 'debug'))
        measured[0] = measured[0] and m
        spent += tok
        st = 'error' if err else 'ok'
        rows.append(dict(phase=ph, model=r['model'], worker=worker or os.environ.get('TZ_WORKER') or 'default', tokens=tok, ms=int((time.time() - t0) * 1000), status=st, note=(err or text)[:200]))
        ledger(run=rid, phase=ph, model=r['model'], tokens=tok, status=st)
        checkpoint(rid, rows)
        return st
    for ph in ('plan', 'build'):
        if phase(ph) != 'ok' and not dry:
            return rid, rows, spent, measured[0]
    if test:
        for attempt in range(3):  # test, then at most 2 debug rounds; a failed run feeds its tail to debug
            p = subprocess.run(test, shell=True, cwd=cwd, capture_output=True, text=True)
            rows.append(dict(phase='test', status='pass' if p.returncode == 0 else 'fail', note=(p.stdout + p.stderr)[-200:]))
            ledger(run=rid, phase='test', status=rows[-1]['status'])
            checkpoint(rid, rows)
            if p.returncode == 0 or dry:
                break
            if attempt == 2 or phase('debug', 'The check `%s` failed:\n%s' % (test, (p.stdout + p.stderr)[-1500:])) != 'ok':
                break
    return rid, rows, spent, measured[0]


def main(argv):
    if argv and argv[0] == 'agent':
        argv = argv[1:]
    op = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
    words, skip = [], False
    for i, a in enumerate(argv):
        if skip:
            skip = False
        elif a in ('--test', '--budget', '--turns', '--files', '--worker', '--timeout'):
            skip = True
        elif not a.startswith('--'):
            words.append(a)
    task = ' '.join(words)
    if not task:
        print('usage: tz agent "<task>" [--test CMD] [--worktree] [--files a,b] [--budget TOK] [--turns N] [--dry]', file=sys.stderr); return 2
    if op('--files'):  # file ownership: refuse when another task already owns one of these files
        clash = claim(task, op('--files').split(','))
        if clash:
            print('refused: owned by another task: ' + ', '.join(clash), file=sys.stderr); return 3
    rid, rows, spent, meas = run(task, os.getcwd(), op('--test'), int(op('--budget', 400000)), int(op('--turns', 20)), '--worktree' in argv, '--dry' in argv, op('--worker'), int(op('--timeout', 1800)))
    for r in rows:
        print('%-6s %-7s %s%s' % (r['phase'], r.get('model', ''), r['status'], '  %s tok' % r['tokens'] if 'tokens' in r else ''))
    print('run %s: %d tokens (%s)' % (rid, spent, 'MEASURED from host usage' if meas else 'EST chars/4: this worker reports no usage'))
    return 0 if rows and rows[-1]['status'] in ('ok', 'pass', 'dry') else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
