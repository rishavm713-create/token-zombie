# codex adapter. REAL for usage: parses ~/.codex/sessions rollout logs (token_count events). No tz hooks/statusline.
import glob, json, os, shutil, time
from adapters import make, rules_text
NAME = 'codex'
BINARY = 'codex'  # command looked up on PATH to see if the host is installed here
STATUS = 'REAL'
NOTE = 'Usage parser REAL (MEASURED tokens from ~/.codex/sessions rollout logs) + rules via AGENTS.md. No tz hooks/statusline.'
RULES_FILE = 'AGENTS.md'


def capabilities():
    return make(NAME, **{'hooks': False, 'statusline': False, 'subagent_models': 'UNKNOWN', 'session_spawn': 'UNKNOWN', 'transcripts': '~/.codex/sessions/*/*/*/rollout-*.jsonl (usage parser: real)', 'usage': True})


def generate_rules():
    return rules_text() if RULES_FILE else ''


FIELDS = ('input_tokens', 'cached_input_tokens', 'output_tokens', 'reasoning_output_tokens', 'total_tokens')


def sessions_dir():
    home = os.environ.get('CODEX_HOME') or os.path.join(os.environ.get('HOME') or os.path.expanduser('~'), '.codex')
    return os.path.join(home, 'sessions')


def installed_here():
    return bool(shutil.which(BINARY)) or os.path.isdir(sessions_dir())


def _parse(path):
    """Last cumulative total_token_usage + model of one rollout file. Malformed lines skipped."""
    tot, model = None, None
    try:
        f = open(path, encoding='utf-8', errors='replace')
    except OSError:
        return None
    with f:
        for line in f:
            if '"token_count"' not in line and '"turn_context"' not in line:
                continue
            try:
                d = json.loads(line)
                p = d.get('payload') or {}
                if d.get('type') == 'turn_context' and isinstance(p.get('model'), str):
                    model = p['model']
                elif p.get('type') == 'token_count':
                    t = (p.get('info') or {}).get('total_token_usage')
                    if isinstance(t, dict):
                        tot = {k: int(t.get(k) or 0) for k in FIELDS}
            except (ValueError, TypeError, AttributeError):
                continue
    return {'tokens': tot, 'model': model} if tot else None


def usage(since_days=7):
    """MEASURED tokens per session (last cumulative total, never a sum of cumulative values) and overall total."""
    cut = time.time() - since_days * 86400
    sess, total = [], {k: 0 for k in FIELDS}
    for fp in sorted(glob.glob(os.path.join(sessions_dir(), '*', '*', '*', 'rollout-*.jsonl'))):
        try:
            mt = os.path.getmtime(fp)
        except OSError:
            continue
        if mt < cut:
            continue
        r = _parse(fp)
        if not r:
            continue
        sess.append({'file': os.path.basename(fp), 'model': r['model'], **r['tokens']})
        for k in FIELDS:
            total[k] += r['tokens'][k]
    return {'agent': NAME, 'source': 'MEASURED', 'days': since_days, 'sessions': sess, 'session_count': len(sess), 'total': total}
