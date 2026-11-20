# Agent adapters: common interface. Only claude is real (hooks, statusline, transcript parser). Others declare capabilities honestly
# (UNKNOWN where unverified) and can generate a rules file from SKILL.md sections 1-5.
import importlib, os, re
NAMES = ['claude', 'codex', 'cursor', 'windsurf', 'gemini', 'cline', 'roo', 'antigravity']
KEYS = ('hooks', 'statusline', 'subagent_models', 'session_spawn', 'transcripts')


def load(name):
    return importlib.import_module(f'adapters.{name}')


def rules_text():
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'SKILL.md')
    try:
        t = open(p, encoding='utf-8').read()
    except OSError:
        return ''
    t = re.sub(r'^---.*?---\s*', '', t, count=1, flags=re.S)
    parts = re.split(r'(?m)^(?=## )', t)
    return '\n'.join(parts[:6]).strip()  # intro + first 5 sections


def make(name, **caps):
    full = {k: 'UNKNOWN' for k in KEYS}
    full.update(caps)
    return full


def info(name):
    """Shared interface for the supervisor: what this host really supports. installed_here is MEASURED (PATH lookup), capabilities are declared."""
    import shutil
    m = load(name)
    return dict(name=name, status=m.STATUS, capabilities=m.capabilities(), rules_file=m.RULES_FILE, note=m.NOTE,
                installed_here=bool(m.BINARY and shutil.which(m.BINARY)) if m.BINARY else None)


def supports(name, cap):
    """True only when the capability is declared True/non-empty AND the adapter is REAL. Anything else is False (UNKNOWN counts as no)."""
    i = info(name)
    v = i['capabilities'].get(cap)
    return i['status'] == 'REAL' and bool(v) and v != 'UNKNOWN'
