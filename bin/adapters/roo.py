# roo adapter. Declared capabilities only; NOT integrated or tested against the live tool (rules file generation only).
from adapters import make, rules_text
NAME = 'roo'
BINARY = None  # command looked up on PATH to see if the host is installed here
STATUS = 'RULES-ONLY'
NOTE = 'VS Code extension: rules via .roo/rules only. No CLI to detect.'
RULES_FILE = '.roo/rules/token-zombie.md'


def capabilities():
    return make(NAME, **{'hooks': False, 'statusline': False, 'subagent_models': False, 'session_spawn': False, 'transcripts': False})


def generate_rules():
    return rules_text() if RULES_FILE else ''
