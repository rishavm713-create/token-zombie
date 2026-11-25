#!/usr/bin/env python3
# Owner-workflow defaults. All advice/local files only: nothing is spawned, pushed or installed.
#   tz split "task A" "task B" ..   one session per task: cheapest fitting model, worktree cmd, lock for shared resources, test last
#   tz lock acquire|release|status NAME [--ttl S]   atomic lock dir for a shared resource (live test, device, port); stale after ttl (default 1800s)
#   tz hsize [DIR] [--json]          handoff size check: daily notes <=30 lines, master top block <=15 lines, weekly merge due
import json, os, re, sys, time, glob
from tzlib import feature, mode, _conf

D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
SHARED = re.compile(r'\b(live test|e2e|premiere|simulator|device|browser|port \d+|database|db|deploy|install|publish)\b', re.I)
BUILD_FIRST = 'build the whole batch first with syntax checks only; one live test at the end, holding the lock'


# large single build task (keyword heuristic, kept narrow: it can start sessions): "from scratch", or a build verb + determiner + whole product
LARGE = re.compile(r'\bfrom scratch\b|\b(build|create|implement|redesign|rewrite|migrate|refactor|overhaul)\s+(?:(?:me|us)\s+)?'
                   r'(?:a|an|the|our|my|this)\s+(?:[\w-]+\s+){0,4}?'
                   r'(app|application|system|platform|dashboard|website|service|pipeline|plugin|codebase|backend|frontend)\b', re.I)
QUESTION = re.compile(r'^(why|how|what|where|when|which|who|is|are|does|do|did|explain)\b', re.I)
BUDGET = ('Ship-fast time budget: hours, not days. State your time estimate in hours before starting and break the work into pieces of '
          '30 minutes or less. If this session is already one piece of a split, do not start more sessions; use subagents. '
          'Never push, tag or publish without the owner OK. Off: tz speed off.')


def split_hint(ts):
    """Advice for a prompt holding several independent tasks. auto_split on (owner default): start them in parallel now."""
    plan = 'Plan: tz split ' + ' '.join('"' + t[:60].replace('"', "'") + '"' for t in ts[:4])
    if feature('auto_split'):
        return (f'TOKEN ZOMBIE (owner standing order, auto_split): {len(ts)} independent tasks in this prompt. Start them in parallel NOW, '
                'no card: start_session initiation user_asked, one session per task (max 5 at once, the rest as cards), cheapest fitting model, '
                'each in its own git worktree/branch; inside each session split the work into small independent pieces run as parallel '
                'Sonnet/Haiku subagents; build everything first, test once at the end, commit on its own branch. This session then merges the '
                'branches, runs the full test suite once and pushes only after the owner OK (no tag/release). ' + plan)
    return (f'TOKEN ZOMBIE (suggestion): {len(ts)} independent tasks in this prompt. One task per session: '
            'propose each as its own session card (start_session, own_initiative, cheapest fitting model, own worktree; the owner clicks to start, or says to do it here), '
            'shared live tests behind tz lock, build everything first, test once at the end. ' + plan)

# prompts that did not come from the owner's keyboard: never an approval, never a reason to auto-start sessions
NOT_OWNER = re.compile(r'<(cross-session-message|task-notification|scheduled-task|[a-z-]*event)\b|another claude session sent a message', re.I)
# an approval is a short owner prompt that STARTS with the go-ahead verb (after yes/ok/..); anything hedged, negated or asked is not one
APPROVE = re.compile(r'^(?:(?:yes|yep|yeah|ok|okay|sure|approved?|lgtm|go ahead|go|please|now|and|you can)\b[\s,.!:;-]*)*'
                     r'(?:push|ship|release|tag|publish)(?:$|[.!,]|\s+(?:and\b|it\b|this\b|that\b|them\b|all\b|now\b|the (?:branch|release|tag|changes|commits?)\b|'
                     r'to (?:github|origin|main)\b|v?\d))', re.I)
HEDGE = re.compile(r"\?|\b(no|not|never|don'?t|do not|wait|hold|stop|cancel|later|after|before|if|when|once|unless|until|but|should|can we|draft|notes?)\b", re.I)
FLOW = ('Ship flow (automatic): when the pieces finish, merge the branches, run the full suite once, push, watch CI on all OSes and fix '
        'failures without weakening any test. Push only after the owner says yes in their own prompt; tag or release only when CI is green '
        'AND the owner approved that tag. Report in short lines: each session link + status, then what is next (merge, test, push).')


def approval(prompt):
    """The owner's own go-ahead to push/ship/tag/release/publish, as their exact words; '' otherwise."""
    if NOT_OWNER.search(prompt or ''):
        return ''
    p = SYS.sub(' ', prompt or '').strip()
    return p if len(p) <= 200 and APPROVE.search(p) and not HEDGE.search(p) else ''


def approval_hint(words):
    got = {v.lower() for v in re.findall(r'\b(push|ship|tag|release|publish)\b', words, re.I)}
    tag = got & {'tag', 'release', 'publish'}
    return ('TOKEN ZOMBIE (ship_fast): owner approval in their own prompt: "' + words.replace('"', "'") + '". It covers only what these words '
            'name. If another session has the context for this work, forward the approval to it (SendMessage), quoting these words exactly; '
            'do not redo its work. If this session has it: run the full suite if not run since the last change, then do what was approved, '
            'watch CI on all OSes and fix failures without weakening any test. '
            + ('Tag or release only after CI is green, and only the tag these words approve.' if tag else
               'No tag, release or publish: these words do not approve one.') + ' Report in short lines with each session link and status.')


def ship_hint(prompt, ts):
    """The one split/speed hint per prompt. ship_fast on: multi-part or large build tasks also get parallel orders and an hours budget."""
    if not feature('ship_fast'):
        return split_hint(ts) if ts else ''
    if NOT_OWNER.search(prompt or ''):
        return ''
    ok = approval(prompt)
    if ok:
        return approval_hint(ok)
    if ts:
        head = split_hint(ts)
    else:
        p = SYS.sub(' ', prompt or '').strip()
        if p.startswith('/') or len(p) > 1500 or QUESTION.search(p) or not LARGE.search(p):
            return ''
        start = ('Start them in parallel NOW, no card: start_session initiation user_asked, one session per independent piece (max 5 at once, '
                 'the rest as cards), cheapest fitting model, each in its own git worktree/branch.' if feature('auto_split') else
                 'Propose each independent piece as its own session card (start_session, own_initiative, cheapest fitting model, own worktree).')
        head = ('TOKEN ZOMBIE (ship_fast): large build task. Cut it into independent pieces. ' + start + ' Inside each session run small '
                'parts as parallel Sonnet/Haiku subagents; build everything first, test once at the end, commit on its own branch. This '
                'session then merges the branches and runs the full test suite once. If it cannot be cut, stay in one session and use subagents.')
    return head + ' ' + BUDGET + ' ' + FLOW


def speed(args):
    """tz speed on|off|status: the ship_fast switch in config.json "features"."""
    op = args[0] if args else 'status'
    if len(args) > 1 or op not in ('on', 'off', 'status'):
        print('usage: tz speed on|off|status', file=sys.stderr)
        return 2
    if op != 'status':
        p = os.path.expanduser('~/.claude/token-zombie/config.json')
        conf, old = {}, None
        if os.path.exists(p):
            old = open(p).read()
            try:
                conf = json.loads(old)
            except ValueError:
                conf = None
        if not isinstance(conf, dict) or not isinstance(conf.get('features', {}), dict):
            print(f'tz speed: {p} (or its "features") is not a JSON object; refusing to touch it', file=sys.stderr)
            return 1
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if old is not None:
            open(f'{p}.bak-speed-{time.strftime("%Y%m%d-%H%M%S")}', 'w').write(old)
        conf.setdefault('features', {})['ship_fast'] = op == 'on'
        json.dump(conf, open(p + '.tmp', 'w'), indent=2)
        os.replace(p + '.tmp', p)
        _conf['features'] = conf['features']
    print(speed_line())
    return 0


def speed_line():
    f = _conf.get('features') if isinstance(_conf.get('features'), dict) else {}
    src = ('mode off' if mode() == 'off' else 'env TZ_FEAT_SHIP_FAST' if os.environ.get('TZ_FEAT_SHIP_FAST') is not None
           else 'config.json' if 'ship_fast' in f else 'default')
    return f'speed = {"on" if feature("ship_fast") else "off"} ({src})'


def lockdir(name):
    base = os.path.expanduser(os.environ.get('TZ_LOCK_DIR', '~/.claude/token-zombie/locks'))
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, re.sub(r'[^A-Za-z0-9_.-]', '-', name)[:60] or 'lock')


def lock(op, name, ttl=1800):
    p = lockdir(name)
    meta = os.path.join(p, 'owner.json')
    held = None
    if os.path.isdir(p):
        try:
            held = json.load(open(meta))
        except (OSError, ValueError):
            held = {'ts': os.path.getmtime(p)}
        if time.time() - held.get('ts', 0) > ttl:
            held = None  # stale
    if op == 'status':
        return (0, f'{name}: held pid {held.get("pid", "?")} for {int(time.time() - held["ts"])}s') if held else (0, f'{name}: free')
    if op == 'release':
        for f in glob.glob(os.path.join(p, '*')):
            os.remove(f)
        if os.path.isdir(p):
            os.rmdir(p)
        return 0, f'{name}: released'
    if op == 'acquire':
        if held is None and os.path.isdir(p):
            lock('release', name)
        try:
            os.mkdir(p)
        except FileExistsError:
            return 1, f'{name}: busy (held {int(time.time() - held["ts"])}s); wait or release if the holder is gone'
        json.dump({'ts': time.time(), 'pid': os.getppid()}, open(meta, 'w'))
        return 0, f'{name}: acquired (stale after {ttl}s); release: tz lock release {name}'
    return 2, 'usage: tz lock acquire|release|status NAME [--ttl S]'


# system text (reminders, notifications, code fences) is data, never a task list
SYS = re.compile(r'<(system-reminder|task-notification|pasted_content|cross-session-message|scheduled-task|[a-z-]*event)\b[^>]*>.*?</\1>|&lt;system-reminder>.*?(?=\n\n|$)|```.*?```', re.S | re.I)


def detect(prompt):
    """Independent tasks in one prompt: numbered/bulleted lines or 'also/then ...' clauses. [] when fewer than 2 (heuristic, advice only)."""
    prompt = SYS.sub(' ', prompt or '')
    if len(prompt) > 1500:  # long pasted text is a document, not a task list
        return []
    items = [re.sub(r'^\s*(\d+[.)]|[-*])\s*', '', l).strip() for l in (prompt or '').splitlines() if re.match(r'^\s*(\d+[.)]|[-*])\s+\S', l)]
    if len(items) < 2:
        items = [x.strip() for x in re.split(r'\b(?:also|and then|then)\b|;', prompt or '', flags=re.I) if len(x.split()) >= 4]
    return items if len(items) >= 2 else []


# coding pipeline: phase -> (model, [skills in preference order], one-line rule). Skills come from the `coding` pack; tz only names those that exist.
CODE = [('plan', 'sonnet', ['planning-and-task-breakdown', 'grill-me'], 'goal + acceptance check in 2 lines, smallest plan, owner approves'),
        ('build', 'sonnet', ['incremental-implementation', 'karpathy-guidelines'], 'smallest complete change, reuse code, syntax check only; whole batch first'),
        ('debug', 'sonnet', ['debugging-and-error-recovery', 'diagnosing-bugs'], 'only when a check fails: reproduce, root cause, fix once'),
        ('test', 'sonnet', ['test-driven-development', 'doubt-driven-development'], 'one real test per new logic, then ONE full run (background if >2 min)'),
        ('review', 'sonnet', ['code-review-and-quality', 'security-and-hardening'], 'read the diff only; owner picks findings to fix'),
        ('simplify', 'haiku', ['code-simplification', 'simplify-codebase'], 'remove what is not needed; no new features'),
        ('ship', 'sonnet', ['git-workflow-and-versioning', 'pr'], 'commit/push only after owner OK; handoff note last')]


AGENT = {'plan': 'Plan (read-only architect; Explore on haiku first to locate code)', 'build': 'main chat (general-purpose agent only for independent files)',
         'debug': 'main chat', 'test': 'verifier', 'review': 'reviewer', 'simplify': 'main chat', 'ship': 'main chat'}


def code_pipeline(task=''):
    """Coding workflow with the best installed skill per phase. Advice only: names skills, never turns a pack on or runs anything."""
    roots = [os.path.expanduser(r) for r in ('~/.claude/skills', '~/.claude/skills-off/coding', '~/.claude/skills-off/devmisc')]
    have = lambda n: next((r for r in roots if os.path.isdir(os.path.join(r, n))), None)
    out = []
    hard = False
    if task:
        import tzroute
        hard = tzroute.complexity(task) >= 5
    for ph, model, skills, rule in CODE:
        if hard and ph in ('plan', 'review', 'debug'):
            model = 'opus'  # hard task: the decisions that cost most when wrong get the strongest model
        found = [(n, 'on' if have(n) == roots[0] else 'pack coding') for n in skills if have(n)]
        out.append(dict(phase=ph, model=model, agent=AGENT[ph], skill=found[0][0] if found else None, state=found[0][1] if found else None, rule=rule))
    return out


def plan(tasks):
    import tzroute, tzmore
    out = []
    for i, t in enumerate(tasks, 1):
        r = tzroute.route(t)
        ag = {'RESEARCH': 'Explore (haiku)', 'AUDIT': 'reviewer', 'ENGINEERING': 'main chat; Plan/verifier/reviewer per tz code'}.get(r['mode'], 'main chat')
        out.append(dict(n=i, task=t, model=r['model'], mode=r['mode'], agent=ag, worktree=tzmore.worktree_cmd(t),
                        lock=sorted({m.lower() for m in SHARED.findall(t)}) or None))
    shared = {}
    for x in out:
        for k in x['lock'] or []:
            shared.setdefault(k, []).append(x['n'])
    return dict(sessions=out, lock_needed={k: v for k, v in shared.items() if len(v) > 1}, rule=BUILD_FIRST,
                basis='EST keyword heuristic; one session per task, each in its own worktree; the checking step runs last')


def hsize(root):
    hd = os.path.join(root, 'handoffs')
    bad, days = [], set()
    for f in sorted(glob.glob(os.path.join(hd, '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*.md'))):
        n = sum(1 for _ in open(f, errors='replace'))
        days.add(os.path.basename(f)[:10])
        if n > 30:
            bad.append((os.path.relpath(f, root), n))
    top = None
    for name in ('HANDOFF.md', os.path.join('docs', 'HANDOFF.md')):
        p = os.path.join(root, name)
        if os.path.exists(p):
            top = 0
            for ln in open(p, errors='replace'):
                if ln.strip() == '---':
                    break
                top += 1
            top = (name, top)
            break
    return dict(over_30=bad, daily_days=len(days), merge_due=len(days) >= 7, master_top=top,
                master_top_over_15=bool(top and top[1] > 15))


def main(argv):
    c, a = argv[0], argv[1:]
    js = '--json' in a
    a = [x for x in a if x != '--json']
    if c == 'speed':
        return speed(a)
    if c == 'lock':
        ttl = 1800
        if '--ttl' in a:
            i = a.index('--ttl'); ttl = int(a[i + 1]); del a[i:i + 2]
        if len(a) < 2:
            print('usage: tz lock acquire|release|status NAME [--ttl S]', file=sys.stderr); return 2
        rc, msg = lock(a[0], a[1], ttl); print(msg); return rc
    if c == 'split':
        if not a:
            print('usage: tz split "task A" "task B" ...', file=sys.stderr); return 2
        r = plan(a)
        if js:
            print(json.dumps(r, indent=1)); return 0
        for x in r['sessions']:
            print(f"{x['n']}. [{x['model']}] {x['task']}\n   {x['worktree']}" + (f"\n   shared: {', '.join(x['lock'])}" if x['lock'] else ''))
        for k, v in r['lock_needed'].items():
            print(f"lock '{k}' shared by tasks {v}: tz lock acquire {k}  ... tz lock release {k}")
        print('rule: ' + r['rule'] + '\nTZ starts nothing; open one session per line yourself.')
        return 0
    if c == 'code' and '--run' in a:  # executes the pipeline: tz code --run [--test CMD] [--worktree] <task>
        import tzagent
        return tzagent.main([x for x in a if x != '--run'])
    if c == 'code':
        rows = code_pipeline(' '.join(a))
        if js:
            print(json.dumps(rows, indent=1)); return 0
        for r in rows:
            print(f"{r['phase']:8} [{r['model']}] agent: {r['agent']} | " + (f"/{r['skill']} ({r['state']})" if r['skill'] else '(no skill, follow the rule)') + f"  {r['rule']}")
        print('one task per session; build first, test once; pack on only when a phase needs it: ~/.claude/skillpack on coding, off when done.')
        return 0
    if c == 'hsize':
        r = hsize(os.path.abspath(a[0] if a else '.'))
        if js:
            print(json.dumps(r)); return 0
        for f, n in r['over_30']:
            print(f'OVER: {f} has {n} lines (max 30): trim to done/left/next')
        if r['master_top_over_15']:
            print(f'OVER: {r["master_top"][0]} top block {r["master_top"][1]} lines (max 15, end with ---)')
        if r['merge_due']:
            print(f'MERGE DUE: {r["daily_days"]} daily days; merge into the master top block')
        if not (r['over_30'] or r['master_top_over_15'] or r['merge_due']):
            print('handoff sizes ok')
        return 1 if (r['over_30'] or r['master_top_over_15']) else 0
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
