# codex adapter. Declared capabilities only; NOT integrated or tested against the live tool (rules file generation only).
from adapters import make, rules_text
NAME = 'codex'
BINARY = 'codex'  # command looked up on PATH to see if the host is installed here
STATUS = 'RULES-ONLY'
NOTE = 'Rules via AGENTS.md only. No tz hooks, no usage parser: format not parsed. Missing API: lifecycle hooks/statusline we can rely on.'
RULES_FILE = 'AGENTS.md'


def capabilities():
    return make(NAME, **{'hooks': False, 'statusline': False, 'subagent_models': 'UNKNOWN', 'session_spawn': 'codex exec (UNVERIFIED)', 'transcripts': '~/.codex/sessions (format not parsed)'})


def generate_rules():
    return rules_text() if RULES_FILE else ''
