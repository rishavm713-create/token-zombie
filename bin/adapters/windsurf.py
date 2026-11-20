# windsurf adapter. Declared capabilities only; NOT integrated or tested against the live tool (rules file generation only).
from adapters import make, rules_text
NAME = 'windsurf'
BINARY = 'windsurf'  # command looked up on PATH to see if the host is installed here
STATUS = 'RULES-ONLY'
NOTE = 'Rules via .windsurf/rules only. No hook, statusline or transcript API known to tz.'
RULES_FILE = '.windsurf/rules/token-zombie.md'


def capabilities():
    return make(NAME, **{'hooks': False, 'statusline': False, 'subagent_models': False, 'session_spawn': False, 'transcripts': False})


def generate_rules():
    return rules_text() if RULES_FILE else ''
