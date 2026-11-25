#!/usr/bin/env python3
# Token-zombie lean start: inject only HANDOFF.md's top block (up to the first '---' line, max 15 lines)
# and the head of the newest handoffs/*.md (max 30 lines), so a huge HANDOFF.md is never read whole.
# source=compact: inject only the continuation note from tz-compact.py.
import glob, json, os, sys

TOP, DAILY, CAP = 15, 30, 2500  # lines, lines, chars
# TZ core rules: one compact block merging the useful caveman, ponytail and Karpathy rules plus the owner's CLAUDE.md
# rules (caveman+ponytail cost ~7.7k chars each chat, ~2k tok per subagent [measured]). Specialist skills stay on demand.
# Injected only when neither plugin is enabled, so nothing is said twice. Off: config "lean_rules": false.
LEAN = ('TOKEN ZOMBIE core rules (lean rules). Replies: answer first, terse; no greeting, recap, filler or offers. Keep every '
        'fact, negation (not/never/only), code, command, path, number and error exact. Full sentences for security warnings, '
        'irreversible steps and questions to the owner. Work: match effort to the task; state assumptions when unclear; '
        'read code before editing it; never re-read a file or re-run a call whose result you have; batch independent calls; '
        'keep decisions already made. Code: smallest complete change; reuse the codebase, stdlib and installed deps before '
        'new code; no unasked features, options or abstractions; touch only what the task needs, match the style, fix root '
        'causes; check security and correctness of what you change; test real changes (one small test for new logic) and '
        'loop until it passes. Review, audit and commit skills only on demand. '
        'Mark a deliberate shortcut in a code comment as `shortcut: <limit>, <when to upgrade>`; never cut input '
        'validation or data-loss error handling. '
        'End with one line: what you skipped or did not check.')


def lean():
    home = os.path.expanduser('~/.claude')
    try:
        if json.load(open(os.path.join(home, 'token-zombie', 'config.json'))).get('lean_rules') is False:
            return ''
    except Exception:
        pass
    try:
        on = [k for k, v in (json.load(open(os.path.join(home, 'settings.json'))).get('enabledPlugins') or {}).items() if v]
    except Exception:
        on = []
    return '' if any(k.split('@')[0] in ('caveman', 'ponytail') for k in on) else LEAN


def head(path, n, stop_at_rule):
    out = []
    with open(path, encoding='utf-8', errors='ignore') as f:
        for i, line in enumerate(f):
            if i >= n or (stop_at_rule and i and line.strip() == '---'):
                break
            out.append(line.rstrip())
    return '\n'.join(out)


def _plan(d, peek=False, _c={}):
    """v2.1 plan re-injection (feature plan_reinject, default off); computed once per run."""
    if 'v' not in _c:
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import tzfit
            _c['v'] = tzfit.plan_inject(d)
        except Exception:
            _c['v'] = ''
    return _c['v']


def _facts(d):
    """Opt-in (micro_skills) learned-facts block, or ''. Fail open."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import tzfacts
        return tzfacts.session_start(d)
    except Exception:
        return ''


def _fit(txt):
    """Cap SessionStart text with the shared budget fitter (Claude Code truncates hook output near 10k chars)."""
    try:
        import tzfit
        return tzfit.fit(txt)
    except Exception:
        return txt



def _warn():
    """HARD RULE: one line when this plugin checkout is not on main or panel files are edited, so a stale/broken bar load is visible. Silent outside git."""
    try:
        import subprocess
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
        g = lambda *a: subprocess.run(['git', '-C', root, *a], capture_output=True, text=True, timeout=5)
        b = g('rev-parse', '--abbrev-ref', 'HEAD')
        if b.returncode != 0:
            return ''
        br, dirty = b.stdout.strip(), g('status', '--porcelain', '--', 'hooks', 'types').stdout.strip()
        w = []
        if br != 'main':
            w.append(f'plugin folder is on branch {br}, not main')
        if dirty:
            w.append('panel files (hooks/, types/) have uncommitted edits')
        return ('TZ WARNING: ' + '; '.join(w) + ' - the bar may be stale or broken') if w else ''
    except Exception:
        return ''


def _vis():
    """One user-visible line (systemMessage) so TZ shows in every UI, incl. the desktop app; feature banner, default on."""
    try:
        if not _tzl.feature('banner'):
            return _warn()
        v = ''
        try:
            v = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.claude-plugin', 'plugin.json'))).get('version', '')
        except Exception:
            pass
        return 'Token Zombie ' + (('v' + v + ' ') if v else '') + 'is on: saves tokens automatically. See savings: tz gain' + (' | ' + _warn() if _warn() else '')
    except Exception:
        return ''

try:
    _raw = sys.stdin.read()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import tzlib as _tzl
    if _tzl.dup_hook(os.path.basename(__file__), _raw):
        sys.exit(0)  # same event already handled by the other registered copy
    d = json.loads(_raw)
    cwd = d.get('cwd') or os.getcwd()
    if d.get('source') in ('compact', 'clear'):
        try:
            import tztokopt
            tztokopt.reset(d.get('session_id', 'x'))
        except Exception:
            pass
    parts, pk = [], ''
    if d.get('source') == 'compact':  # after compaction: only the continuation note tz-compact.py saved
        note = os.path.expanduser(f"~/.claude/token-zombie/compact-{d.get('session_id', 'x')}.md")
        if os.path.isfile(note):
            txt = 'TOKEN ZOMBIE continuation (saved just before compaction; facts from git + chat log):\n' + open(note).read()[:1500]
        else:
            txt = ''
        txt = '\n\n'.join(x for x in (lean(), txt, _facts(d), _plan(d)) if x)
        if txt:
            print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': txt}}))
        sys.exit(0)
    master = os.path.join(cwd, 'HANDOFF.md')
    if os.path.isfile(master):
        parts.append(f'## {master} (top block only)\n' + head(master, TOP, True))
    daily = sorted(glob.glob(os.path.join(cwd, 'handoffs', '*.md')), key=os.path.getmtime)
    if daily:
        parts.append(f'## {daily[-1]} (newest handoff)\n' + head(daily[-1], DAILY, False))
    try:  # active task pack (<=2k tok), when handoffs/tasks has one
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import tznext
        pk = tznext.pack(cwd)
        if not pk:  # feature beads_prime (default off): short brief of ready tasks when no task pack
            import tzbeads
            pk = tzbeads.on_start(cwd)
    except Exception:
        pass
    try:  # oversized handoff notes: one line, advice only
        import tzsplit
        hs = tzsplit.hsize(cwd) if os.path.isdir(os.path.join(cwd, 'handoffs')) else {}
        if hs.get('over_30') or hs.get('master_top_over_15') or hs.get('merge_due'):
            parts.append(f"TOKEN ZOMBIE: handoff notes oversized ({len(hs.get('over_30', []))} daily >30 lines"
                         + (', merge due' if hs.get('merge_due') else '') + '); run tz hsize, trim or merge when the task ends.')
    except Exception:
        pass
    L = lean()
    try:  # v2.1: instruction-file report, opt-in defaults offer
        import tztips
        tips = tztips.start_tips(d)
    except Exception:
        tips = ''
    try:  # v2.1 opt-in: recent observed work (tz obs)
        import tzobs
        obs = tzobs.hook(d) if _tzl.feature('obs_inject') else ''
    except Exception:
        obs = ''
    tips = '\n\n'.join(x for x in (tips, obs) if x)
    facts = _facts(d)
    if parts or pk or L or tips or facts or _plan(d, peek=True):
        txt = (('TOKEN ZOMBIE start context. Use this; do not read the full HANDOFF.md unless the step needs a detail.\n'
               + '\n\n'.join(parts))[:CAP] if parts else '') + ('\n\n' + pk if pk else '')
        txt = _fit('\n\n'.join(x for x in (L, txt.strip(), tips, facts, _plan(d)) if x))
        _o = {'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': txt}}
        if _vis():
            _o['systemMessage'] = _vis()
        print(json.dumps(_o))
    elif _vis():
        print(json.dumps({'systemMessage': _vis()}))
    if d.get('source') != 'resume' and os.environ.get('TZ_FRESH_BG') != '0':  # panel's fresh-chat number; detached, never delays start
        import subprocess
        subprocess.Popen([sys.executable, '-c', 'import sys; sys.path.insert(0, sys.argv[1]); import tzopt, tzusage; tzopt.fresh_file(); tzusage.record()',
                          os.path.dirname(os.path.abspath(__file__))], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
except Exception:
    sys.exit(0)
