#!/usr/bin/env python3
# tz facts (micro-skills): a failure that recurs across sessions in one repo becomes a short saved fact, shown at session start.
# Adapted from microsoft/TokenEconomizer tokeneconomizer/microskills/{lifecycle.py,envfacts.py,observe.py} (MIT, Copyright (c) 2026
# Microsoft), see NOTICE. Divergences: reads Claude Code transcripts; no model-backed proposer; only the form_repair,
# absent_tool and boundary families; much narrower shell parsing; `python3` may repair a missing `python`.
import argparse, glob, hashlib, json, os, re, shlex, sys, time

# upstream lifecycle constants (lifecycle.py, envfacts.py)
K_PROMOTE, GAMMA, LAMBDA, SCORE_FLOOR, FIRE_GATE, FIRE_MIN_N = 3, 0.8, 5.0, 0.0, 0.40, 4
MAX_FACTS, MAX_TOKENS, CONTRADICT_STREAK = 4, 150, 2
HEADER = '# environment facts learned from earlier sessions in this repository'
LINT = re.compile(r"\b(skip|no need|don'?t|do not|stop|done|completed?|finish(?:ed)?|verify|verification|instead of (?:running|testing))\b", re.I)

ERRORS = (   # first match names the class (observe.py ERROR_CLASSES)
    ('module_missing', r'ModuleNotFoundError|No module named|Cannot find module|ERR_MODULE_NOT_FOUND'),
    ('command_missing', r'command not found|: not found\b|is not recognized'),
    ('script_missing', r"can't open file .*No such file or directory"),
    ('permission_denied', r'Permission denied|EACCES'),
    ('usage_error', r'(?m:^usage:)|unrecognized arguments|no such option|error: argument|unknown option'),
    ('connection_refused', r"Connection refused|Failed to connect to|couldn't connect to|Could not connect|ECONNREFUSED"),
    ('name_resolution', r'Could not resolve host|Temporary failure in name resolution|Name or service not known|getaddrinfo|nodename nor servname|ENOTFOUND'),
    ('unreachable', r'Network is unreachable|No route to host|Connection timed out|Operation timed out|ETIMEDOUT'),
)
NETWORK = ('connection_refused', 'name_resolution', 'unreachable')
FORM_ERRORS = ('module_missing', 'command_missing', 'script_missing', 'usage_error', 'permission_denied')
PHRASE = {'module_missing': 'ModuleNotFoundError', 'command_missing': 'command not found', 'script_missing': 'a file-not-found error',
          'usage_error': 'a usage error', 'permission_denied': 'permission denied'}
NOT_FOUND = re.compile(r"([^\s:'\"]+):\s+(?:command\s+)?not found\b(?!:)|command not found:\s+(\S+)|'([^']+)' is not recognized", re.I)
TESTS_RAN = re.compile(r'\b\d+ (?:passed|failed)\b|\bRan [1-9]\d* tests?\b|\bTests:\s+\d+|test result:|\bpass \d+ fail \d+')
HOST = re.compile(r"https?://(?:[^/\s'\"]*@)?([A-Za-z0-9.-]+(?::\d+)?)")   # userinfo (tokens) is never kept
# WHY: form words are re-injected into later sessions, so only plain path/name characters are ever stored.
SAFE = re.compile(r'^[A-Za-z0-9_./~+:-]{1,60}$')

INTERP = {'python', 'python3', 'node', 'ruby', 'perl', 'php', 'deno', 'julia', 'lua', 'Rscript', 'elixir'}
RUNNERS = {'pytest', 'tox', 'nox', 'jest', 'vitest', 'mocha', 'rspec', 'phpunit', 'ctest', 'bats'}
BUILDERS = {'make', 'cmake', 'ninja', 'bazel', 'tsc', 'eslint', 'prettier', 'ruff', 'flake8', 'pylint', 'mypy', 'pyright', 'black',
            'isort', 'gcc', 'g++', 'clang', 'javac', 'webpack', 'vite', 'pre-commit', 'shellcheck', 'golangci-lint'}
PACKAGE = {'pip', 'pip3', 'uv', 'poetry', 'pipenv', 'conda', 'npm', 'yarn', 'pnpm', 'bun', 'gem', 'bundle', 'composer', 'cargo', 'go',
           'mvn', 'gradle', 'dotnet', 'brew'}
SUBCMD = {'npm', 'yarn', 'pnpm', 'bun', 'cargo', 'go', 'mvn', 'gradle', 'dotnet', 'swift', 'mix'}
LAUNCH = {('uv', 'run'), ('poetry', 'run'), ('pipenv', 'run'), ('pdm', 'run'), ('hatch', 'run'), ('rye', 'run'), ('bundle', 'exec'), ('pipx', 'run')}


# ---- observe ----
def error_class(out):
    """Name of the first environmental error class in the output, else None."""
    return next((n for n, rx in ERRORS if re.search(rx, out or '', re.I)), None)


def _words(seg):
    try:
        return shlex.split(seg, comments=True)
    except ValueError:                   # a split inside quotes: the command cannot be attributed
        return None


def _form(words):
    """How the command was spelled, arguments dropped: ['uv','run','pytest','-q'] -> 'uv run pytest'."""
    n = 1
    if tuple(words[:2]) in LAUNCH:
        n = 3
    elif words[0] in ('npx', 'uvx'):
        n = 2
    elif words[1:2] == ['-m'] and os.path.basename(words[0]) in INTERP:
        n = 3
    elif words[0] in SUBCMD and len(words) > 1:
        n = 3 if words[1] == 'run' else 2
    parts = words[:n]
    return ' '.join(parts) if all(SAFE.match(w) for w in parts) else ''


def _intent(form):
    w = form.split(' && ')[-1].split()
    tool = os.path.basename(w[-1])
    head = os.path.basename(w[0])
    if tool in RUNNERS or tool == 'unittest' or (head in SUBCMD and tool == 'test'):
        return 'run_tests'
    if tool in BUILDERS or (head in SUBCMD and tool in ('build', 'check', 'lint', 'vet', 'compile', 'typecheck', 'clippy')):
        return 'run_build'
    if head in INTERP and len(w) == 1:
        return 'run_interpreter'
    return 'package_tool' if head in PACKAGE or tool in PACKAGE else 'other'


def classify(cmd):
    """-> {form, intent, env, hosts} for a command with exactly one meaningful segment, else None (blame would be a guess)."""
    if '<<' in cmd:
        return None
    found, activate = [], ''
    for seg in re.split(r'&&|\|\||;|\n', cmd):
        w = _words(seg.split(' | ')[0])
        if w is None:
            return None
        if w[:1] == ['rtk']:
            w = w[2:] if w[1:2] == ['bypass'] else w[1:]
        env = False
        while w and re.match(r'^[A-Za-z_]\w*=', w[0]):
            w, env = w[1:], True
        if not w or w[0] in ('cd', 'echo', 'export', 'true', 'set', 'pwd', 'head', 'tail', 'cat'):
            continue
        if w[0] in ('source', '.') and len(w) == 2 and w[1].endswith('activate') and SAFE.match(w[1]):
            activate = f'source {w[1]} && '
            continue
        found.append((w, env, seg))
    if len(found) != 1:
        return None
    w, env, seg = found[0]
    form = _form(w)
    if not form:
        return None
    fetch = w[0] in ('curl', 'wget') or (w[0] == 'git' and w[1:2] and w[1] in ('clone', 'fetch', 'pull', 'ls-remote'))
    return {'form': activate + form, 'intent': 'fetch_remote' if fetch else _intent(activate + form), 'env': env,
            'hosts': sorted(set(HOST.findall(seg)))}


def _tool_of(form):
    return form.split()[-1].rsplit('/', 1)[-1] if form else ''


def outcome(o, text, is_error):
    """Set o['outcome'] ('ran' / error class / 'failed'), o['not_found'] and o['tests_ran'] from the tool result."""
    o['tests_ran'] = bool(TESTS_RAN.search(text))
    m = NOT_FOUND.search(text)
    o['not_found'] = bool(m) and os.path.basename(next(g for g in m.groups() if g)) == _tool_of(o['form'].split(' && ')[-1].split()[0])
    err = error_class(text)
    if o['intent'] == 'run_tests' and o['tests_ran']:
        o['outcome'] = 'ran'                # the runner started: failing tests are not an environment failure
    elif o['not_found']:
        o['outcome'] = 'command_missing'    # a pipe can hide the exit code
    elif is_error or (o['intent'] == 'fetch_remote' and err in NETWORK and len(text) < 600):
        o['outcome'] = err if err and err != 'command_missing' else 'failed'
    else:
        o['outcome'] = 'ran'
    return o


def observe(path):
    """Shell observations of one Claude Code transcript, in call order."""
    calls, obs = {}, []
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            try:
                content = json.loads(line)['message']['content']
            except (ValueError, KeyError, TypeError):
                continue
            for b in content if isinstance(content, list) else []:
                if not isinstance(b, dict):
                    continue
                if b.get('type') == 'tool_use' and b.get('name') in ('Bash', 'PowerShell'):
                    calls[b.get('id')] = str((b.get('input') or {}).get('command') or '')
                elif b.get('type') == 'tool_result' and b.get('tool_use_id') in calls:
                    o = classify(calls.pop(b['tool_use_id']))
                    c = b.get('content')
                    if isinstance(c, list):
                        c = '\n'.join(x.get('text', '') for x in c if isinstance(x, dict))
                    if o:
                        obs.append(outcome(o, str(c or ''), bool(b.get('is_error'))))
    return obs


def failed(o):
    """The way the command was CALLED fails here (a runner rejecting its arguments does not count)."""
    return o['outcome'] in FORM_ERRORS and not (o['intent'] == 'run_tests' and o['outcome'] == 'usage_error')


def worked(o):
    return o['outcome'] == 'ran' and (o['intent'] != 'run_tests' or o['tests_ran'])


def is_bare(form):
    """No activation prefix, launcher or explicit path."""
    return (' && ' not in form and '/' not in form.split()[0] and ' run ' not in form       # only activation adds ' && '
            and not form.startswith(('npx ', 'uvx ', 'bundle ')))


def repairs(form, a_form, intent):
    """Can `form` stand in for the failing `a_form`?"""
    if form == a_form:
        return False
    if intent == 'run_build':
        skip = {'run', 'npx', 'uv', 'uvx', 'pipx', 'poetry', 'pipenv', '-m', 'python', 'python3'}
        return bool((set(form.split()) & set(a_form.split())) - skip)
    return intent == 'run_tests' or not is_bare(form) or (a_form, form) == ('python', 'python3')


# ---- lifecycle: CANDIDATE -> ACTIVE after K_PROMOTE confirmations -> RETIRED; shown only past the firing gate ----
def new_fact(family, high, **params):
    return {'family': family, 'high': high, 'params': params, 'state': 'CANDIDATE', 'confirms': [], 'contradicts': [], 'fire': [0, 0]}


def score(f, now):
    return sum(GAMMA ** (now - i) for i in f['confirms']) - LAMBDA * sum(GAMMA ** (now - i) for i in f['contradicts'])


def fold_verdict(f, now, verdict, fired, exercised):
    """Fold one session's evidence into a fact."""
    if f['family'] == 'form_repair' and exercised:   # one lucky bare run must not retire a long-confirmed repair
        n = f['params'].get('streak', 0) + 1 if verdict == 'contradict' else 0
        f['params']['streak'] = n
        if verdict == 'contradict' and n < CONTRADICT_STREAK:
            verdict = None
    if exercised:
        f['fire'] = [f['fire'][0] + bool(fired), f['fire'][1] + 1]
    if verdict:
        f[verdict + 's'].append(now)
    if f['state'] == 'CANDIDATE':
        if verdict == 'contradict' and f['high']:
            f['state'] = 'RETIRED'
        elif len(f['confirms']) >= K_PROMOTE:
            f['state'] = 'ACTIVE'
    elif f['state'] == 'ACTIVE' and ((f['high'] and verdict == 'contradict') or score(f, now) < SCORE_FLOOR):
        f['state'] = 'RETIRED'


def injectable(f):
    n, d = f['fire']
    return f['state'] == 'ACTIVE' and d >= FIRE_MIN_N and n / d >= FIRE_GATE


# ---- families ----
def working_form(f):
    """Best working replacement: worked minus failed sessions, positive only."""
    good, bad = f['params']['good'], f['params']['bad']
    pool = {k: v - bad.get(k, 0) for k, v in good.items() if v > bad.get(k, 0)}
    return max(pool, key=lambda k: (pool[k], good[k])) if pool else None


def _form_repair(facts, obs, injected, now):
    typed = lambda o: worked(o) and not o['env']
    for intent in ('run_interpreter', 'run_tests', 'run_build', 'package_tool'):
        seq = [o for o in obs if o['intent'] == intent]
        errs = {}
        for i, a in enumerate(seq):
            bare_only = intent not in ('run_tests', 'run_build')
            if failed(a) and (not bare_only or is_bare(a['form'])) and any(typed(b) and repairs(b['form'], a['form'], intent) for b in seq[i + 1:]):
                fid = f"form_repair:{intent}:{a['form']}"
                facts.setdefault(fid, new_fact('form_repair', False, intent=intent, a=a['form'], good={}, bad={}))
                errs[fid] = a['outcome']
        ok_forms = {o['form'] for o in seq if typed(o)}
        bad_forms = {o['form'] for o in seq if failed(o) and not o['env']} - ok_forms
        for fid, f in facts.items():
            p = f['params']
            if f['family'] != 'form_repair' or p['intent'] != intent:
                continue
            if fid in errs:
                p['error'] = errs[fid]
            for form in ok_forms:           # one session is one piece of evidence per form
                if repairs(form, p['a'], intent):
                    p['good'][form] = p['good'].get(form, 0) + 1
            for form in bad_forms & set(p['good']):
                p['bad'][form] = p['bad'].get(form, 0) + 1
    for fid, f in facts.items():
        if f['family'] != 'form_repair':
            continue
        p = f['params']
        seq = [o for o in obs if o['intent'] == p['intent']]
        a_failed = any(o['form'] == p['a'] and failed(o) for o in seq)
        b_ran = any(worked(o) and (o['form'] in p['good'] or (not is_bare(o['form']) and repairs(o['form'], p['a'], p['intent']))) for o in seq)
        # only the bare form running tests/build cleanly contradicts: an interpreter one-liner proves nothing
        a_ok = any(o['form'] == p['a'] and worked(o) and o['intent'] in ('run_tests', 'run_build') for o in obs)
        verdict = 'confirm' if a_failed or (b_ran and not a_ok) else 'contradict' if a_ok else None
        fold_verdict(f, now, verdict, a_failed or (fid in injected and b_ran), bool(seq))


def _absent_tool(facts, obs, injected, now):
    repaired = {f['params']['a'] for f in facts.values() if f['family'] == 'form_repair' and working_form(f)}
    ran = {_tool_of(o['form']) for o in obs if worked(o)}
    for o in obs:
        form = o['form']
        if (o['intent'] in ('run_build', 'run_tests', 'package_tool') and o['outcome'] == 'command_missing' and o['not_found']
                and ' ' not in form and is_bare(form) and form not in repaired and form not in ran):
            facts.setdefault(f'absent_tool:{form}', new_fact('absent_tool', True, tool=form, intent=o['intent']))
    for fid, f in facts.items():
        if f['family'] != 'absent_tool':
            continue
        tool = f['params']['tool']
        against = tool in repaired or tool in ran
        missing = any(o['form'] == tool and o['outcome'] == 'command_missing' and o['not_found'] for o in obs)
        # once shown, count only sessions that ran another check of the same kind
        fired = missing or (fid in injected and not against and any(o['intent'] == f['params']['intent'] for o in obs))
        fold_verdict(f, now, 'contradict' if against else 'confirm' if fired else None, fired, fired or against)


def _boundary(facts, obs, now):
    fetches = [o for o in obs if o['intent'] == 'fetch_remote']
    refused = [h for o in fetches if o['outcome'] in NETWORK for h in o['hosts']]
    reached = {h for o in fetches if o['outcome'] == 'ran' for h in o['hosts']}
    fid = 'boundary:fetch_remote'
    if refused:
        facts.setdefault(fid, new_fact('boundary', True, hosts={}))
    f = facts.get(fid)
    if not f:
        return
    hosts = f['params']['hosts']
    for h in refused:
        hosts[h] = hosts.get(h, 0) + 1
    verdict = 'contradict' if reached & set(hosts) else 'confirm' if refused else None
    fold_verdict(f, now, verdict, bool(refused), any(o['hosts'] for o in fetches))


# ---- rendering ----
def claim(f):
    """One declarative line, or '' when there is nothing safe to say."""
    p = f['params']
    if f['family'] == 'form_repair':
        b = working_form(f)
        s = f"`{p['a']} …` fails here with {PHRASE.get(p.get('error'), 'an environment error')}; `{b} …` works." if b else ''
    elif f['family'] == 'absent_tool':
        s = f"`{p['tool']} …` fails here with command not found, and no other way to run it has worked."
    else:
        top = sorted(p['hosts'], key=lambda h: -p['hosts'][h])[:3]
        s = f"Outbound connections to {', '.join(top)} are refused here; nothing can be fetched from them."
    return '' if LINT.search(s) else s


def select(state):
    """-> (ids, block) of the facts that pass the gate, capped at MAX_FACTS and ~MAX_TOKENS [est chars/4]."""
    order = {'form_repair': 0, 'absent_tool': 1, 'boundary': 2}
    ready = [(i, f) for i, f in state['facts'].items() if injectable(f) and claim(f)]
    ready.sort(key=lambda x: (order[x[1]['family']], -x[1]['fire'][0] / x[1]['fire'][1]))
    ids, lines = [], [HEADER]
    for i, f in ready:
        line = '- ' + claim(f)
        if len(ids) < MAX_FACTS and len('\n'.join(lines + [line])) <= MAX_TOKENS * 4:
            ids.append(i)
            lines.append(line)
    return ids, '\n'.join(lines) if ids else ''


# ---- state ----
def repo_root(cwd):
    d = os.path.abspath(cwd)
    while d != os.path.dirname(d):
        if os.path.exists(os.path.join(d, '.git')):
            return d
        d = os.path.dirname(d)
    return os.path.abspath(cwd)


def state_path(cwd):
    key = hashlib.sha1(repo_root(cwd).encode()).hexdigest()[:16]
    return os.path.join(os.path.expanduser('~/.claude/token-zombie/facts'), key + '.json')


def load(cwd):
    base = {'repo': repo_root(cwd), 'now': 0, 'facts': {}, 'forgotten': {}, 'folded': [], 'injected': {}}
    try:
        with open(state_path(cwd), encoding='utf-8') as f:
            base.update(json.load(f))
    except (OSError, ValueError, TypeError):      # missing or damaged state: start over, never break a hook
        pass
    return base


def save(cwd, state):
    p = state_path(cwd)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = f'{p}.{os.getpid()}.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=1)
    os.replace(tmp, p)


def fold(state, sid, transcript):
    """Fold one finished session into the state, once per session id. True when folded."""
    if sid in state['folded']:
        return False
    obs = observe(transcript)
    shown = set(state['injected'].pop(sid, []))
    facts, now = state['facts'], state['now']
    _form_repair(facts, obs, shown, now)
    _absent_tool(facts, obs, shown, now)
    _boundary(facts, obs, now)
    for i in state['forgotten']:
        facts.pop(i, None)                  # a forgotten fact is never learned again under that id
    state['now'] = now + 1
    state['folded'] = (state['folded'] + [sid])[-500:]
    return True


def _on():
    try:
        from tzlib import feature
        return feature('micro_skills')
    except Exception:
        return False


def session_start(data):
    """SessionStart: the facts block for this repo, or ''. Gated by feature('micro_skills')."""
    if not _on():
        return ''
    cwd = data.get('cwd') or os.getcwd()
    state = load(cwd)
    ids, block = select(state)
    if ids:                                 # remembered so a fact that prevents its failure still counts as firing
        state['injected'] = dict(list(state['injected'].items())[-50:])
        state['injected'][data.get('session_id') or 'x'] = ids
        save(cwd, state)
    return block


def session_end(data):
    """SessionEnd: learn from the finished transcript. Gated by feature('micro_skills')."""
    tp = data.get('transcript_path')
    if not _on() or not tp or not os.path.isfile(tp):
        return False
    cwd = data.get('cwd') or os.getcwd()
    state = load(cwd)
    done = fold(state, data.get('session_id') or os.path.basename(tp)[:-6], tp)
    if done:
        save(cwd, state)
    return done


def learn(cwd, root, quiet=300):
    """Fold every not-yet-folded transcript of this repo, oldest first; files touched in the last `quiet` s are likely live."""
    d = os.path.join(root, re.sub(r'[^A-Za-z0-9]', '-', repo_root(cwd)))
    files = sorted(glob.glob(os.path.join(glob.escape(d), '*.jsonl')), key=os.path.getmtime)
    state = load(cwd)
    n = sum(fold(state, os.path.basename(p)[:-6], p) for p in files if time.time() - os.path.getmtime(p) >= quiet)
    if n:
        save(cwd, state)
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(prog='tz facts', description='facts learned from failures that recur across sessions')
    ap.add_argument('action', nargs='?', default='show', choices=['show', 'learn', 'block', 'forget', 'unforget'])
    ap.add_argument('id', nargs='?')
    ap.add_argument('--project', default=os.getcwd())
    ap.add_argument('--root', default=os.path.expanduser('~/.claude/projects'))
    a = ap.parse_args(argv)
    if a.action == 'learn':
        print(f'folded {learn(a.project, a.root)} new session(s) [actual]')
    state = load(a.project)
    if a.action in ('forget', 'unforget'):
        src, dst = (state['facts'], state['forgotten']) if a.action == 'forget' else (state['forgotten'], state['facts'])
        if a.id not in src:
            print(f'no fact to {a.action} with id {a.id!r}', file=sys.stderr)
            return 1
        dst[a.id] = src.pop(a.id)
        save(a.project, state)
        print(f'{a.action}: {a.id}')
    elif a.action == 'block':
        print(select(state)[1] or 'no fact passes the gate yet')
    else:
        print(f"tz facts: {state['now']} session(s) folded, {len(state['facts'])} fact(s), {len(state['forgotten'])} forgotten")
        for i, f in state['facts'].items():
            mark = 'shown' if injectable(f) and claim(f) else 'not shown'
            print(f"{f['state']:9} confirms {len(f['confirms'])} fired {f['fire'][0]}/{f['fire'][1]} {mark:9} {i}\n    {claim(f) or '(no claim yet)'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
