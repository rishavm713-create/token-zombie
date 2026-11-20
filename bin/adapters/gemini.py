# gemini adapter. Declared capabilities only; NOT integrated or tested against the live tool (rules file generation only).
from adapters import make, rules_text
NAME = 'gemini'
BINARY = 'gemini'  # command looked up on PATH to see if the host is installed here
STATUS = 'RULES-ONLY'
NOTE = 'Rules via GEMINI.md only. gemini -p exists but headless spawn is not tested by tz.'
RULES_FILE = 'GEMINI.md'


def capabilities():
    return make(NAME, **{'hooks': False, 'statusline': False, 'subagent_models': 'UNKNOWN', 'session_spawn': 'gemini -p (UNVERIFIED)', 'transcripts': False})


def generate_rules():
    return rules_text() if RULES_FILE else ''
