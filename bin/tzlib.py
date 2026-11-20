# Shared helpers for token-zombie hooks: read token usage from a Claude Code chat log (jsonl).
import json, os, re

# All thresholds are tunable: env TZ_<KEY> beats ~/.claude/token-zombie/config.json beats these defaults.
DEFAULTS = {'limit': 100000,    # growth past first reply: suggest fresh session for the NEXT task
            'hard': 175000,     # growth: hand the rest of the task to a fresh session at a safe point
            'read_warn': 40000, # bytes: first whole Read of a bigger file asks for a targeted read once
            'plan_warn': 90, 'plan_stop': 97,  # plan-usage % (only from real provider data)
            'startup_warn': 60000,
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


def cfg(key):
    return int(os.environ.get(f'TZ_{key.upper()}') or _conf.get(key) or PROFILES[mode()].get(key) or DEFAULTS[key])


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
