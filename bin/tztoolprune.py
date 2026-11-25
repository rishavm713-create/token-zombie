#!/usr/bin/env python3
# tz toolprune: list tools that were offered every turn but never called, optionally deny them (bare names in permissions.deny).
# Evidence rules, protected set, apply/restore bookkeeping adapted from microsoft/TokenEconomizer
# (tokeneconomizer/plugin/fold.py enough_evidence, plugin/denylist.py, toolprune/tools.py PROTECTED_TOOLS, plugin/config.py defaults)
# (MIT, Copyright (c) Microsoft Corporation), see NOTICE. Re-implemented stdlib-only against Claude Code transcripts.
# Also: mcp_dup(), PreToolUse advice for a repeated identical MCP call (own design; idea source token-optimizer, no code reused).
import argparse, fnmatch, glob, hashlib, json, os, re, sys, time

# TokenEconomizer defaults (config.py:194-199): evidence prompts, min sessions, session floor; high-risk tools need 3x.
EVIDENCE, MIN_SESSIONS, SESSIONS, HIGH_RISK_FACTOR, WINDOW = 10, 2, 5, 3, 10
# Work surface and the tools Claude Code itself needs to run (tools.py:41-48 + interactive ones). Never listed, never denied.
PROTECTED = frozenset({'Bash', 'PowerShell', 'Edit', 'Write', 'Read', 'Grep', 'Glob', 'MultiEdit', 'Task', 'Agent', 'TodoWrite',
                       'AskUserQuestion', 'ExitPlanMode', 'EnterPlanMode', 'Skill', 'ToolSearch', 'WebFetch', 'WebSearch',
                       'TaskCreate', 'TaskUpdate', 'TaskGet', 'TaskList', 'TaskOutput'})
PROTECT_GLOBS = ('mcp__token-zombie__*',)   # our own tools stay available
HIGH_RISK = frozenset({'NotebookEdit'})
MCP_GUESS = 600                             # [est] chars of one MCP tool schema when only its name is known
APPLIED = 'untool_applied.json'
PENDING = 'untool_pending.json'
# upstream toolprune_quiet_minutes (config.py:198) and the 24 h cap from the research spec
QUIET_MINUTES, PENDING_CAP_H = 60, 24


def protected(name, extra=()):
    return name in PROTECTED or any(fnmatch.fnmatch(name, g) for g in PROTECT_GLOBS + tuple(extra))


def _lines(path):
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            for ln in f:
                try:
                    yield json.loads(ln)
                except ValueError:
                    continue
    except OSError:
        return


def _is_prompt(d):
    """A real user prompt: user message with text, not a tool result, not meta/sidechain."""
    m = d.get('message') or {}
    if d.get('type') != 'user' or d.get('isSidechain') or d.get('isMeta') or m.get('role') != 'user':
        return False
    c = m.get('content')
    if isinstance(c, str):
        return bool(c.strip())
    return isinstance(c, list) and any(isinstance(b, dict) and b.get('type') == 'text' and b.get('text', '').strip() for b in c) \
        and not any(isinstance(b, dict) and b.get('type') == 'tool_result' for b in c)


def read_session(path):
    """-> (used tool names, listed tool names, prompt count) for one transcript."""
    used, listed, prompts = set(), set(), 0
    for d in _lines(path):
        a = d.get('attachment')
        if isinstance(a, dict) and a.get('type') == 'deferred_tools_delta':
            listed.update(a.get('addedNames') or [])
            listed.difference_update(a.get('removedNames') or [])
        if _is_prompt(d):
            prompts += 1
        m = d.get('message')
        if d.get('type') == 'assistant' and isinstance(m, dict) and isinstance(m.get('content'), list):
            for b in m['content']:
                if isinstance(b, dict) and b.get('type') == 'tool_use' and b.get('name'):
                    used.add(b['name'])
    return used, listed, prompts


def enough_evidence(sessions, prompts, high_risk=False, evidence=EVIDENCE, min_sessions=MIN_SESSIONS, floor=SESSIONS):
    """TokenEconomizer rule: enough prompts across >= min sessions, or `floor` sessions however short; high-risk x3."""
    k = HIGH_RISK_FACTOR if high_risk else 1
    return (sessions >= min_sessions and prompts >= evidence * k) or sessions >= floor * k


def recent_sessions(root, n):
    fs = [f for f in glob.glob(os.path.join(root, '*', '*.jsonl')) if os.path.isfile(f)]
    return sorted(fs, key=os.path.getmtime, reverse=True)[:n]


def est_chars(name, deferred):
    return len(name) + 1 if deferred else MCP_GUESS


def analyse(root, n=WINDOW, evidence=EVIDENCE, min_sessions=MIN_SESSIONS, floor=SESSIONS, protect=()):
    """Rows for every non-protected listed tool: streak (newest sessions in a row with zero calls), prompts in them, verdict."""
    files = recent_sessions(root, n)
    sess = [read_session(f) for f in files]          # newest first
    deferred = set().union(*[s[1] for s in sess]) if sess else set()
    names = set(deferred)
    for u, _, _ in sess:
        names.update(x for x in u if x.startswith('mcp__'))   # a called MCP tool was certainly listed
    rows = []
    for t in sorted(names):
        if protected(t, protect):
            continue
        streak = prompts = 0
        for u, _, p in sess:
            if t in u:
                break
            streak += 1; prompts += p
        hr = t in HIGH_RISK
        ok = streak > 0 and enough_evidence(streak, prompts, hr, evidence, min_sessions, floor)
        rows.append({'tool': t, 'streak': streak, 'prompts': prompts, 'high_risk': hr,
                     'chars': est_chars(t, t in deferred), 'verdict': 'prune' if ok else 'keep',
                     'used_ever': any(t in u for u, _, _ in sess)})
    return {'sessions': len(files), 'rows': rows}


def report(res):
    out = [f"tz toolprune: {res['sessions']} newest session(s) scanned; per-turn cost is [est] chars/4 (names and schema guesses, not measured)"]
    if not res['rows']:
        out.append('no listed tools found in these transcripts')
    else:
        out.append(f"{'tool':44} {'streak':>6} {'prompts':>7} {'est tok/turn':>12}  verdict")
        for r in res['rows']:
            out.append(f"{r['tool'][:44]:44} {r['streak']:>6} {r['prompts']:>7} {r['chars'] // 4:>12}  {r['verdict']}")
        pr = [r for r in res['rows'] if r['verdict'] == 'prune']
        out.append(f"{len(pr)} prunable, ~{sum(r['chars'] for r in pr) // 4} tokens/turn [est]. Nothing changed; use --apply to deny them (--restore undoes it).")
    return '\n'.join(out)


# ---- apply / restore (settings file edits) ----
def read_settings(path):
    try:
        text = open(path, encoding='utf-8').read()
    except FileNotFoundError:
        return {}, False
    if not text.strip():
        return {}, True
    try:
        obj = json.loads(text)
    except ValueError as e:
        raise RuntimeError(f'refusing to edit {path}: not valid JSON ({e})')
    if not isinstance(obj, dict):
        raise RuntimeError(f'refusing to edit {path}: not a JSON object')
    return obj, True


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    open(tmp, 'w', encoding='utf-8').write(json.dumps(obj, indent=2) + '\n')
    os.replace(tmp, path)


def _sha(path):
    try:
        return hashlib.sha256(open(path, 'rb').read()).hexdigest()
    except OSError:
        return None


def _exclude(project, *names):
    """Keep our per-user files out of git (TokenEconomizer does the same for its settings file)."""
    p = os.path.join(project, '.git', 'info', 'exclude')
    if not os.path.isdir(os.path.dirname(p)):
        return
    have = open(p).read() if os.path.exists(p) else ''
    add = [n for n in names if n not in have.split('\n')]
    if add:
        open(p, 'a').write(('' if have.endswith('\n') or not have else '\n') + '\n'.join(add) + '\n')


def apply(settings, tools, project=None, protect=()):
    """Append bare names to permissions.deny; record exactly what we added. Returns the list added."""
    tools = [t for t in tools if not protected(t, protect)]
    cur, existed = read_settings(settings)           # re-read right before writing (concurrent edits)
    perms = cur.get('permissions') if isinstance(cur.get('permissions'), dict) else None
    deny = perms.get('deny') if perms and isinstance(perms.get('deny'), list) else None
    add = [t for t in dict.fromkeys(tools) if t not in (deny or [])]
    if not add:
        return []
    if 'permissions' in cur and perms is None:      # refuse before any file (backup included) is written
        raise RuntimeError(f'refusing to edit {settings}: permissions is not an object')
    if deny is None and perms and 'deny' in perms:
        raise RuntimeError(f'refusing to edit {settings}: permissions.deny is not a list')
    rec_path = os.path.join(os.path.dirname(settings), APPLIED)
    rec = json.load(open(rec_path)) if os.path.exists(rec_path) else {'added': []}
    backup = None
    if existed:
        backup = settings + f'.tzbak-{int(time.time())}'
        open(backup, 'wb').write(open(settings, 'rb').read())
    if perms is None:
        perms = cur['permissions'] = {}
    if deny is None:
        rec['created_deny'] = True
        deny = perms['deny'] = []
    deny.extend(add)
    _write(settings, cur)
    rec.update({'settings': settings, 'added': rec['added'] + add, 'created_file': rec.get('created_file', not existed),
                'backup': backup if existed and not rec.get('backup') else rec.get('backup'),
                'sha_after': _sha(settings), 'when': int(time.time())})
    _write(rec_path, rec)
    if project:
        _exclude(project, '.claude/settings.local.json', '.claude/' + APPLIED, '.claude/*.tzbak-*')
    return add


def restore(settings):
    """Remove exactly the entries we added. Untouched file since apply -> byte-identical copy from the backup."""
    rec_path = os.path.join(os.path.dirname(settings), APPLIED)
    if not os.path.exists(rec_path):
        return []
    rec = json.load(open(rec_path))
    added = rec.get('added') or []
    bk = rec.get('backup')
    if rec.get('sha_after') and _sha(settings) == rec['sha_after']:
        if rec.get('created_file'):
            os.remove(settings)
        elif bk and os.path.exists(bk):
            open(settings, 'wb').write(open(bk, 'rb').read())
        else:
            added = None
    else:
        added = None
    if added is None:                                # the person edited it since: remove only our entries
        added = rec.get('added') or []
        cur, _ = read_settings(settings)
        deny = (cur.get('permissions') or {}).get('deny')
        if isinstance(deny, list):
            deny[:] = [d for d in deny if d not in added]
            if not deny and rec.get('created_deny'):
                del cur['permissions']['deny']
                if not cur['permissions']:
                    del cur['permissions']
            _write(settings, cur)
    os.remove(rec_path)
    return added


# ---- deferred apply: a changed tool list re-writes the cached history of a resumed chat, so wait for a quiet repo ----
def config_protect():
    """fnmatch patterns from config.json "toolprune_protect" (upstream key of the same name)."""
    try:
        from tzlib import _conf
        v = _conf.get('toolprune_protect')
    except ImportError:
        return ()
    return tuple(x for x in v if isinstance(x, str)) if isinstance(v, list) else ()


def transcripts_dir(root, project):
    return os.path.join(root, re.sub(r'[^A-Za-z0-9]', '-', os.path.abspath(project)))


def quiet(tdir, minutes, ignore=None):
    """True when no transcript in `tdir` (except `ignore`) changed within `minutes`."""
    cut = time.time() - minutes * 60
    return all(os.path.getmtime(f) <= cut for f in glob.glob(os.path.join(glob.escape(tdir), '*.jsonl')) if f != ignore)


def defer(settings, tools, project, minutes=QUIET_MINUTES, protect=()):
    """Save an approved proposal to be applied once the project is quiet."""
    _write(os.path.join(os.path.dirname(settings), PENDING),
           {'tools': tools, 'minutes': minutes, 'protect': list(protect), 'when': int(time.time())})
    _exclude(project, '.claude/' + PENDING)


def run_pending(settings, project, tdir, ignore=None):
    """-> (status, tools): 'none' | 'expired' | 'apply-pending' | 'applied'."""
    path = os.path.join(os.path.dirname(settings), PENDING)
    try:
        with open(path, encoding='utf-8') as f:
            p = json.load(f)
        tools, minutes, when = list(p['tools']), float(p['minutes']), float(p['when'])
    except (OSError, ValueError, KeyError, TypeError):
        return 'none', []
    if time.time() - when > PENDING_CAP_H * 3600:     # stale evidence: ask again instead of applying
        os.remove(path)
        return 'expired', []
    if not quiet(tdir, minutes, ignore):
        return 'apply-pending', tools
    add = apply(settings, tools, project, config_protect() + tuple(p.get('protect') or ()))
    os.remove(path)
    return 'applied', add


def apply_pending(data, root=None):
    """SessionStart / SessionEnd: apply a saved proposal when the project is quiet; one line or ''. feature('toolprune_pending')."""
    try:
        from tzlib import feature
        if not feature('toolprune_pending'):
            return ''
        project = data.get('cwd') or os.getcwd()
        tp = data.get('transcript_path')
        tdir = os.path.dirname(tp) if tp else transcripts_dir(root or os.path.expanduser('~/.claude/projects'), project)
        # a resumed chat is exactly what the wait protects, so only a brand-new or ending chat is ignored
        ignore = tp if data.get('source') == 'startup' or data.get('hook_event_name') == 'SessionEnd' else None
        status, tools = run_pending(os.path.join(project, '.claude', 'settings.local.json'), project, tdir, ignore)
    except (ImportError, OSError, RuntimeError):
        return ''
    if status != 'applied' or not tools:
        return ''
    return (f'TOKEN ZOMBIE: removed {len(tools)} never-used tool(s) from this project ({", ".join(tools[:5])}); '
            'takes effect in the next session. Undo: tz toolprune --restore.')


# ---- MCP duplicate-call advice (PreToolUse) ----
MUTATORS = ('send', 'create', 'post', 'delete', 'update', 'write', 'run', 'set', 'add', 'remove', 'start', 'stop', 'edit', 'click',
            'type', 'navigate', 'open', 'close', 'upload', 'push', 'execute', 'exec', 'submit', 'reset')
LOCAL_WRITERS = ('Write', 'Edit', 'MultiEdit', 'NotebookEdit', 'Bash', 'PowerShell')


def _norm(x):
    if isinstance(x, dict):
        return {k: _norm(v) for k, v in sorted(x.items()) if v is not None}
    if isinstance(x, list):
        return [_norm(v) for v in x]
    return x


def sig(tool, inp):
    return tool + ' ' + json.dumps(_norm(inp), sort_keys=True, separators=(',', ':'))


def _mutating(tool):
    leaf = tool.split('__')[-1].lower()
    return any(m in leaf for m in MUTATORS)


def mcp_dup(data):
    """One advice line when this mcp__ call repeats an earlier identical one whose result was fine and nothing changed since, else ''."""
    try:
        from tzlib import feature
        if not feature('mcp_dedup'):
            return ''
    except ImportError:
        pass
    tool = data.get('tool_name') or ''
    tp = data.get('transcript_path')
    if not tool.startswith('mcp__') or _mutating(tool) or not tp or not os.path.exists(tp):
        return ''
    want = sig(tool, data.get('tool_input') or {})
    seen = {}                                        # tool_use id -> (position, sig) of earlier identical calls
    res = {}                                         # id -> is_error
    last_change, pos = -1, 0
    for d in _lines(tp):
        m = d.get('message')
        c = m.get('content') if isinstance(m, dict) else None
        if not isinstance(c, list):
            continue
        for b in c:
            if not isinstance(b, dict):
                continue
            pos += 1
            if b.get('type') == 'tool_use':
                n = b.get('name') or ''
                if n in LOCAL_WRITERS or (n.startswith('mcp__') and _mutating(n)):
                    last_change = pos
                elif n == tool and sig(n, b.get('input') or {}) == want:
                    seen[b.get('id')] = pos
            elif b.get('type') == 'tool_result':
                res[b.get('tool_use_id')] = bool(b.get('is_error'))
    good = [p for i, p in seen.items() if i in res and not res[i] and p > last_change]
    if not good:
        return ''
    return (f'TOKEN ZOMBIE: identical {tool} call (same arguments) already answered earlier in this chat and nothing was written since; '
            'reuse that result instead of calling again [advice only, not blocked].')


def main(argv=None):
    ap = argparse.ArgumentParser(prog='tz toolprune', description='find listed-but-never-called tools; optionally deny them')
    ap.add_argument('--root', default=os.path.expanduser('~/.claude/projects'), help='transcripts dir (one subdir per project)')
    ap.add_argument('--project', default=os.getcwd(), help='project dir whose .claude/settings.local.json is edited')
    ap.add_argument('--settings', help='settings file to edit (default <project>/.claude/settings.local.json)')
    ap.add_argument('--window', type=int, default=WINDOW, help='newest N sessions to scan')
    ap.add_argument('--evidence', type=int, default=EVIDENCE)
    ap.add_argument('--min-sessions', type=int, default=MIN_SESSIONS)
    ap.add_argument('--sessions', type=int, default=SESSIONS, help='sessions that are enough without the prompt count')
    ap.add_argument('--protect', action='append', default=[], help='extra fnmatch pattern never pruned')
    ap.add_argument('--json', action='store_true')
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--apply', action='store_true', help='write the proposal into permissions.deny (backup + record)')
    g.add_argument('--restore', action='store_true', help='remove exactly what --apply added')
    g.add_argument('--apply-pending', action='store_true', help='apply a deferred proposal if the project is quiet')
    ap.add_argument('--when-idle', type=int, nargs='?', const=QUIET_MINUTES, metavar='MIN',
                    help=f'with --apply: wait until no chat of the project changed for MIN minutes (default {QUIET_MINUTES})')
    a = ap.parse_args(argv)
    settings = a.settings or os.path.join(a.project, '.claude', 'settings.local.json')
    protect = tuple(a.protect) + config_protect()
    tdir = transcripts_dir(a.root, a.project)
    if a.apply_pending:
        status, tools = run_pending(settings, a.project, tdir)
        print(f'{status}: ' + (', '.join(tools) or 'nothing'))
        return 0
    if a.restore:
        pending = os.path.join(os.path.dirname(settings), PENDING)
        if os.path.exists(pending):
            os.remove(pending)                       # undo also cancels a not-yet-applied proposal
        r = restore(settings)
        print(f'restored {len(r)} entr{"y" if len(r) == 1 else "ies"}: ' + ', '.join(r) if r else 'nothing recorded to restore')
        return 0
    res = analyse(a.root, a.window, a.evidence, a.min_sessions, a.sessions, protect)
    print(json.dumps(res, indent=1) if a.json else report(res))
    if a.apply:
        want = [r['tool'] for r in res['rows'] if r['verdict'] == 'prune']
        try:
            if a.when_idle is not None and want and not quiet(tdir, a.when_idle):
                defer(settings, want, a.project, a.when_idle, protect)
                print(f'apply-pending: {len(want)} tool(s) saved; applied after {a.when_idle} quiet minutes (cap {PENDING_CAP_H} h)')
                return 0
            add = apply(settings, want, a.project, protect)
        except RuntimeError as e:
            print(e, file=sys.stderr); return 1
        print(f'denied {len(add)} tool(s) in {settings}; takes effect in the next session' if add else 'nothing to apply')
    return 0


if __name__ == '__main__':
    sys.exit(main())
