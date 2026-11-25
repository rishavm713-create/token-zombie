# Shared helpers for token-zombie hooks: read token usage from a Claude Code chat log (jsonl).
import json, os, re

# All thresholds are tunable: env TZ_<KEY> beats ~/.claude/token-zombie/config.json beats these defaults.
DEFAULTS = {'limit': 100000,    # growth past first reply: suggest fresh session for the NEXT task
            'hard': 175000,     # growth: hand the rest of the task to a fresh session at a safe point
            'read_warn': 40000, # bytes: first whole Read of a bigger file asks for a targeted read once
            'plan_warn': 90, 'plan_stop': 97,  # plan-usage % (only from real provider data)
            'startup_warn': 60000,
            # v2.1 tips (tztips): token numbers are chat size; each block also has a feature switch below
            'instr_warn_tokens': 3000, 'bulk_read_n': 8, 'size_soft': [50000, 100000], 'size_cap': 150000,
            'paste_warn_chars': 8000, 'mcp_unused_sessions': 5,
            'fresh_overlap': 30, # %: prompt words already seen in this chat at or above this => follow-up, stay
            'cache_ttl': 300,   # seconds: provider prompt-cache life; idle longer => staying re-writes the whole history
            'ctx_window': 200000}  # tokens: ESTIMATE of the model context window (logs do not state it)  # tokens: --startup warns when the median new-chat size is above this
try:
    _conf = json.load(open(os.path.expanduser('~/.claude/token-zombie/config.json')))
except Exception:
    _conf = {}


# Mode profiles (config.json "mode"). full = DEFAULTS. Only differences are listed; `hard`/`plan_stop` safety fires in every mode.
ADVICE = ('pack_hints', 'read_nudge', 'dup_advice', 'next_task')
PROFILES = {
    'off': {'advice': ()},
    'lite': {'limit': 150000, 'hard': 175000, 'read_warn': 100000, 'advice': ('read_nudge', 'next_task')},
    'full': {'advice': ADVICE},
    'ultra': {'limit': 60000, 'hard': 120000, 'read_warn': 20000, 'plan_warn': 80, 'plan_stop': 95, 'advice': ADVICE},
}


def mode():
    m = _conf.get('mode')
    return m.strip().lower() if isinstance(m, str) and m.strip().lower() in PROFILES else 'full'


def advice(name):
    return name in PROFILES[mode()]['advice']


# v2.1 feature registry (one place): name -> default. env TZ_FEAT_<NAME>=0/1 beats config.json "features" beats this.
# mode "off" turns every feature off. Hook-side features only; commands (tz toolprune, tz mem, ...) always work on demand.
FEATURES = {'cache_ttl_auto': 1,  # measured 1 h vs 5 min prompt-cache life (tzcont.cache_ttl)
            'dup_skeleton': 1,    # read_guard=deny: the deny carries the file skeleton instead of nothing
            'safety_net': 1,      # parsed destructive-command / secret-path checks (tzsafety) inside the policy engine
            'stuck_detect': 1,    # OpenHands-style stuck patterns (tzstuck) on tool results
            'mcp_dedup': 1,       # advice when an identical read-only MCP call already succeeded with no write since (tztoolprune.mcp_dup)
            'auto_split': 1,      # several independent tasks: start parallel sessions now (0 = propose cards only)
            'ship_fast': 1,       # multi-part/large build: parallel sessions + subagents, hours budget (tz speed on|off)
            'plan_reinject': 0,   # re-inject capped plan head after compaction (opt-in: adds context)
            'crash_restart': 0,   # `tz sup` tick restarts crashed `tz agent` runs (spends model tokens)
            'learn_loop': 0,      # tzcompound check hook: nudge to capture a lesson after a fail -> pass
            # v2.1 tips: advice is on; anything that blocks or can steer quality down is opt-in
            'size_gate': 0,       # opt-in, once per tier: soft warning on total chat size (the default growth warning stays)
            'size_cap': 0,        # BLOCKS new prompts at size_cap tokens (handoff saved first)
            'task_switch': 1,     # unrelated new task detected: offer a fresh chat
            'idle_cost': 1,       # idle past the cache life: show the re-write cost and offer a fresh chat
            'home_cwd': 1,        # chat started in ~: suggest the project folder
            'paste_warn': 1,      # very large pasted prompt
            'paste_block': 0,     # BLOCKS a very large pasted prompt after saving it to handoffs/paste-<time>.md
            'small_msgs': 1,      # several short prompts in a row: send one full message
            'archive_advice': 1,  # once per chat at a task end: offer the app's auto-archive setting (asks first)
            'model_advice': 1,    # mechanical task on a big model
            'plan_advice': 1,     # big vague task: plan first
            'instr_advice': 1,    # oversized or duplicate always-loaded instruction files
            'defaults_advice': 0, # one-time offer of `tz defaults` (suggests cheaper default models)
            'bulk_read_block': 0, # BLOCKS one Read/Grep/Glob after bulk_read_n in a row (use an Explore subagent)
            'log_compress': 1,    # build/test logs in crushed output: keep every failure line, original stored (tzlogc)
            'skill_lint': 1,      # advice when a written SKILL.md breaks the skill spec (tzaskills)
            'read_delta': 0,      # opt-in, BLOCKS a re-read of a changed file once and shows the diff instead (tztokopt)
            'check_pipe': 1,      # advice when test/build output is piped through head/tail/grep (tzhumanlayer)
            'scope_check': 1,     # advice when curl/wget targets a host outside .tz/scope.json (tzscope)
            'beads_prime': 0,     # opt-in: ready-task brief at session start when no task pack (adds context)
            'safety_extra': 0,    # opt-in: BLOCKS extra destructive/secret commands (tzrules)
            'safety_strict': 0,   # opt-in: stricter rules, also BLOCKS (tzrules)
            'custom_rules': 0,    # opt-in: user rulebooks (tzrules)
            # v2.1 group 2 repo ports: all opt-in (they block or add context / change output)
            'git_guard': 0,        # BLOCKS risky git commands on PreToolUse (tzgitguard)
            'unverified_claim': 0, # Stop: one advice line when success is claimed with no passing check (tzclaim)
            'micro_skills': 0,     # facts learned from repeated failures, added at SessionStart (tzfacts)
            'rtk_filters': 0,      # extra per-command output filters in tzcrush (tzrtk)
            # v2.1 group 3 ports; blocking, recording and injecting ones are opt-in
            'budget_warn': 1,         # one line when a budget set with `tz budget set` climbs a level (silent with no budget)
            'budget_block': 0,        # BLOCKS new prompts at a budget HARD_STOP (handoff saved first)
            'stale_warn': 1,          # before a broad test run: warn once when the branch is behind main
            'stale_block': 0,         # BLOCKS that test run once instead
            'obs_record': 0,          # record prompts/tool observations in the local ledger (tz obs)
            'obs_file_context': 0,    # inject earlier work on a file before it is read
            'obs_inject': 0,          # inject the recent-work index at session start
            'line_custom_command': 0}


def feature(name):
    if mode() == 'off':
        return False
    e = os.environ.get(f'TZ_FEAT_{name.upper()}')
    if e is not None:
        return e.strip() not in ('0', '', 'off', 'false')
    f = _conf.get('features') if isinstance(_conf.get('features'), dict) else {}
    return bool(f.get(name, FEATURES.get(name, 0)))


def cfg(key):
    v = os.environ.get(f'TZ_{key.upper()}') or _conf.get(key) or PROFILES[mode()].get(key) or DEFAULTS[key]
    if isinstance(DEFAULTS[key], list):
        return [int(x) for x in (json.loads(v) if isinstance(v, str) else v)]
    return int(v)


LIMIT, HARD = cfg('limit'), cfg('hard')


def _usage(line):
    if '"usage"' not in line:
        return 0
    try:
        u = json.loads(line).get('message', {}).get('usage') or {}
    except Exception:
        return 0
    return (u.get('input_tokens') or 0) + (u.get('cache_read_input_tokens') or 0) + (u.get('cache_creation_input_tokens') or 0)


def chat_tokens(path, base=None):
    """(first reply size, latest size) in tokens; (0, 0) if unknown. A known base (cached by the caller) skips the head scan."""
    if not path or not os.path.exists(path):
        return 0, 0
    size = os.path.getsize(path)
    with open(path, 'rb') as f:
        # first reply can sit past big startup lines (hooks, attachments): stream until found
        for raw in ([] if base else f):
            base = _usage(raw.decode('utf-8', 'ignore'))
            if base or f.tell() > 20_000_000:
                break
        f.seek(max(0, size - 400000))
        tail = f.read().decode('utf-8', 'ignore').splitlines()
    last = next((n for n in map(_usage, reversed(tail)) if n), 0)
    return base or 0, last


def skills_off(root=os.path.expanduser('~/.claude/skills-off')):
    """(count, tokens) of skill descriptions kept out of startup. Cached 10 min."""
    cache = os.path.expanduser('~/.claude/token-zombie/off-cache2.json')
    try:
        c = json.load(open(cache))
        if os.path.getmtime(cache) > __import__('time').time() - 600:
            return c['n'], c['tok']
    except Exception:
        pass
    n = chars = 0
    for d, _, files in os.walk(root):
        if 'SKILL.md' not in files:
            continue
        n += 1
        try:
            head = open(os.path.join(d, 'SKILL.md'), encoding='utf-8', errors='ignore').read(3000)
            fm = head.split('---')[1] if head.startswith('---') else ''
            # only name + description are listed at startup, not other frontmatter keys
            m = re.search(r'^description:\s*(.*)$', fm, re.M)
            chars += len(m.group(1) if m else '') + len(os.path.basename(d)) + 10
        except Exception:
            pass
    tok = chars // 4
    try:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        json.dump({'n': n, 'tok': tok}, open(cache, 'w'))
    except Exception:
        pass
    return n, tok


# Skill pack keyword map (prompt words -> ~/.claude/skillpack pack). Used by tz-guard hints and tz route.
PACKS = {'video': 'video|caption|shorts|reel|podcast|youtube edit', 'motion': 'motion graphic|explainer|animated|manim|launch film',
         'sound': 'sfx|sound effect|audio clean|voice clean', 'remotion': 'remotion|hyperframes', 'design': 'ui design|polish ui|design system|critique',
         'web': 'gsap|clone (a )?site|slides', 'content': 'youtube script|thumbnail|newsletter|seo title', 'linkedin': 'linkedin',
         'social': 'instagram|carousel', 'seo': r'\bseo\b|\bgeo\b', 'book': 'novel|chapter|manuscript|kdp|book cover',
         'jobs': 'job search|cover letter|apply for', 'admin': 'invoice|inbox|meeting notes|expense', 'coding': 'refactor|write tests|tdd|code review|spec'}


def dup_hook(name, raw, window=5):
    """True if this exact hook payload was already handled by `name` in the last `window` s.
    Claude Code runs a hook twice when TZ is registered both as a plugin and in settings.json; the second copy then exits."""
    import hashlib, time
    if os.environ.get('TZ_DEDUPE') == '0':
        return False
    d = os.path.expanduser('~/.claude/token-zombie/hookseen')
    p = os.path.join(d, hashlib.sha1((name + '\0' + raw).encode('utf-8', 'replace')).hexdigest()[:20])
    try:
        os.makedirs(d, exist_ok=True)
        now = time.time()
        try:
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
        except FileExistsError:
            if now - os.path.getmtime(p) < window:
                return True
            os.utime(p, None)
        if int(now) % 50 == 0:  # occasional sweep
            for f in os.listdir(d):
                q = os.path.join(d, f)
                if now - os.path.getmtime(q) > 600:
                    os.remove(q)
    except OSError:
        return False  # fail open: run the hook
    return False


def agents_snapshot(state_dir):
    """Per-session agent snapshots (agents-<session>.json, one writer each, so sessions never overwrite each other).
    Returns the newest one; falls back to the old shared agents.json. {} if none."""
    import glob, json, os
    best, bt = {}, -1
    for f in glob.glob(os.path.join(state_dir, 'agents-*.json')) + [os.path.join(state_dir, 'agents.json')]:
        try:
            v = json.load(open(f))
            t = v.get('ts') if isinstance(v, dict) else None
            if isinstance(t, (int, float)) and t > bt:
                best, bt = v, t
        except Exception:
            continue
    return best
