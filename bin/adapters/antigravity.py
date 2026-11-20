# antigravity adapter. Declared capabilities only; NOT integrated or tested against the live tool (rules file generation only).
from adapters import make, rules_text
NAME = 'antigravity'
BINARY = 'antigravity'  # command looked up on PATH to see if the host is installed here
STATUS = 'RULES-ONLY'
NOTE = 'Rules via AGENTS.md assumed; every other capability UNKNOWN.'
RULES_FILE = 'AGENTS.md (UNVERIFIED)'


def capabilities():
    return make(NAME, **{'hooks': 'UNKNOWN', 'statusline': False, 'subagent_models': 'UNKNOWN', 'session_spawn': 'UNKNOWN', 'transcripts': False})


def generate_rules():
    return rules_text() if RULES_FILE else ''
