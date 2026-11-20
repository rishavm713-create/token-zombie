# cursor adapter. Declared capabilities only; NOT integrated or tested against the live tool (rules file generation only).
from adapters import make, rules_text
NAME = 'cursor'
BINARY = 'cursor'  # command looked up on PATH to see if the host is installed here
STATUS = 'RULES-ONLY'
NOTE = 'Rules via .cursor/rules only. No hook, statusline or transcript API known to tz.'
RULES_FILE = '.cursor/rules/token-zombie.mdc'


def capabilities():
    return make(NAME, **{'hooks': False, 'statusline': False, 'subagent_models': False, 'session_spawn': False, 'transcripts': False})


def generate_rules():
    return rules_text() if RULES_FILE else ''
