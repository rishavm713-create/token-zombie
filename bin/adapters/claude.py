# claude adapter. REAL: tz hooks/usage parser work here.
from adapters import make, rules_text
NAME = 'claude'
BINARY = 'claude'  # command looked up on PATH to see if the host is installed here
STATUS = 'REAL'
NOTE = 'Hooks (7 events), statusLine, headless `claude -p`, transcripts ~/.claude/projects: implemented and tested here.'
RULES_FILE = None


def capabilities():
    return make(NAME, **{'hooks': True, 'statusline': True, 'subagent_models': True, 'session_spawn': 'claude -p (headless)', 'transcripts': '~/.claude/projects/*/*.jsonl (usage parser: real)'})


def generate_rules():
    return rules_text() if RULES_FILE else ''
