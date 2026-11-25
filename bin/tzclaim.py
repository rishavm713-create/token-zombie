#!/usr/bin/env python3
# adapted from obra/superpowers skills/verification-before-completion (MIT, Copyright (c) 2025 Jesse Vincent), see NOTICE
"""unverified_claim: Stop-time advice when a reply claims success with no check run after the last change. Never blocks."""
import json, os, re, sys

TAIL = 2_000_000  # bytes of transcript read: a turn longer than this only loses its oldest calls
EDIT = ('Edit', 'Write', 'MultiEdit', 'NotebookEdit')
DOCS = ('.md', '.txt', '.rst')  # WHY: no test proves a prose edit
READONLY_AGENTS = ('explore', 'plan', 'web-fetch', 'claude-code-guide')

# "tests pass" style claims need a check even if this turn changed nothing
STRONG = re.compile(r"\b(all (the )?(\d+ )?tests? (now )?pass(es|ed|ing)?|tests? (now |all |are |is )*(pass(es|ed|ing)?|green)|"
                    r"build (now )?(passes|passed|succeeds|succeeded|is green)|lint(er)? (is )?(clean|passes)|"
                    r"works now|now works|should (now )?(work|pass|be fixed))\b", re.I)
# everyday words: only a claim about work when the turn actually changed something
WEAK = re.compile(r"\b(done|fixed|complete|completed|finished|(is |now )working|ready (to|for) (merge|ship|review))\b", re.I)
HEDGE = re.compile(r"\b(not|never|no|cannot|yet to|once|when|if|until|before|unless|to be)\b|n't\b", re.I)
HONEST = re.compile(r"\b(unverified|not (yet )?(been )?(verified|tested|run))\b", re.I)

CHECK = re.compile(
    r"(pytest|py\.test|jest|vitest|mocha|rspec|phpunit|ctest|tox|nox|tsc|ruff|eslint|mypy|pyright|flake8|xcodebuild|"
    r"make|ninja|rake|(go|cargo) (test|build|vet|check|clippy|nextest)|swift (build|test)|dotnet (test|build)|"
    r"deno (test|check|lint)|node --test|(mvnw?|gradlew?) .*\b(test|verify|package|build|check)|"
    r"(npm|yarn|pnpm|bun)( run)? (test|build|lint|typecheck|type-check|check)|tz verify|"
    r"python[\d.]* (-\S+ )*-m (pytest|unittest|py_compile|mypy)|"
    r"(python[\d.]*|bash|sh|zsh|node) (-\S+ )*(\S*/)?(test[\w.-]*|run_all\.sh|\S*[_.]test\.\w+|tests?/\S+)|"
    r"(\S*/)?(run_all\.sh|tests?/\S+\.sh))(?=\s|$|:)")
VCS = re.compile(r"git (-C \S+ )?(diff|status|show)\b")
WRAP = re.compile(r"^(\(?\s*)?((\w+=\S*|rtk|time|sudo|env|nohup|npx|bunx|uv run|poetry run|pipenv run|bundle exec|"
                  r"timeout \S+)\s+)*(\./(?=gradlew|mvnw)|\S*/bin/(?=\w))?")


def parts(cmd):
    """Command words at the start of each shell segment (so `grep pytest x` is not a test run)."""
    return [WRAP.sub('', p.strip()) for p in re.split(r'&&|\|\||[;|\n]', cmd or '') if p.strip()]


def is_check(cmd):
    """True if the shell command runs a test, build or lint."""
    return any(CHECK.match(p) for p in parts(cmd))


def claim(text):
    """(phrase, strong) for the first unhedged success claim in a reply, or None."""
    t = re.sub(r'```.*?```|`[^`\n]*`|"[^"\n]*"', ' ', text or '', flags=re.S)
    if HONEST.search(t):
        return None  # the reply already says it was not verified
    found = None
    for s in re.split(r'(?<=[.!?])\s+|\n+|[;:,] ', t):
        if s.rstrip().endswith('?'):
            continue
        for rx, strong in ((STRONG, True), (WEAK, False)):
            m = rx.search(s)
            if m and not HEDGE.search(s[:m.start()]):
                if strong:
                    return m.group(0), True
                found = found or (m.group(0), False)
    return found


def _rows(path):
    """Parsed transcript lines from the tail; bad lines are skipped."""
    with open(path, 'rb') as f:
        f.seek(max(0, os.path.getsize(path) - TAIL))
        for raw in f:
            try:
                r = json.loads(raw)
            except ValueError:
                continue
            if isinstance(r, dict) and not r.get('isSidechain'):
                yield r


def _blocks(row):
    c = (row.get('message') or {}).get('content')
    if isinstance(c, str):
        return [{'type': 'text', 'text': c}]
    return [b for b in c or [] if isinstance(b, dict)]


def turn(path):
    """Since the last user message: {'id', 'text' (last reply), 'calls': [{name, input, ok}]}."""
    t = {'id': '', 'text': '', 'calls': []}
    ids = {}
    for r in _rows(path):
        bl = _blocks(r)
        if r.get('type') == 'user':
            res = [b for b in bl if b.get('type') == 'tool_result']
            for b in res:
                c = ids.get(b.get('tool_use_id'))
                if c:
                    c['ok'] = not b.get('is_error')
            if not res and not r.get('isMeta'):
                t, ids = {'id': r.get('uuid') or r.get('timestamp') or '', 'text': '', 'calls': []}, {}
        elif r.get('type') == 'assistant':
            for b in bl:
                if b.get('type') == 'text' and b.get('text', '').strip():
                    t['text'] = b['text']
                elif b.get('type') == 'tool_use':
                    c = {'name': b.get('name') or '', 'input': b.get('input') or {}, 'ok': True}
                    t['calls'].append(c)
                    ids[b.get('id')] = c
    return t


def evidence(calls):
    """What happened after the last change: changed (None/'edit'/'agent'), ran, failed, looked (VCS diff)."""
    e = {'changed': None, 'ran': False, 'failed': False, 'looked': False}
    for c in calls:
        n, i = c['name'], c['input']
        f = str(i.get('file_path') or i.get('notebook_path') or '')
        edit = n in EDIT and not f.lower().endswith(DOCS)
        agent = n in ('Agent', 'Task') and str(i.get('subagent_type') or '').lower() not in READONLY_AGENTS
        if edit or agent:  # an earlier green run does not count
            e = {'changed': 'edit' if edit else 'agent', 'ran': False, 'failed': False, 'looked': False}
        elif n == 'Bash':
            cmd = i.get('command') or ''
            if is_check(cmd):
                e['ran'], e['failed'] = c['ok'], not c['ok']
            if any(VCS.match(p) for p in parts(cmd)):
                e['looked'] = True
    return e


def judge(text, calls):
    """Advice line for a reply and the turn's tool calls, or ''."""
    c = claim(text)
    if not c:
        return ''
    phrase, strong = c
    e = evidence(calls)
    if e['ran'] or (not strong and (not e['changed'] or (e['changed'] == 'agent' and e['looked']))):
        return ''
    why = 'the last test/build run failed' if e['failed'] else 'no test/build ran after the last change'
    if e['changed'] == 'agent' and not e['failed']:
        why = 'the delegated work was not checked (diff or test)'
    return f'TOKEN ZOMBIE unverified_claim: reply says "{phrase}" but {why}. Run the check or say "not verified".'


def _seen(sid, key):
    """True if this turn was already advised; records it otherwise."""
    p = os.path.expanduser('~/.claude/token-zombie/claim-' + re.sub(r'\W', '_', sid or 'x'))
    try:
        with open(p) as f:
            if f.read() == key:
                return True
    except OSError:
        pass
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w') as f:
        f.write(key)
    return False


def stop_advice(data):
    """Stop hook: one advice line, once per user turn, or ''. Never raises, never blocks."""
    try:
        from tzlib import feature
        if not feature('unverified_claim'):
            return ''
        t = turn(data.get('transcript_path') or '')
        # WHY payload first: the last reply may not be flushed to the transcript yet
        m = judge(data.get('last_assistant_message') or t['text'], t['calls'])
        return '' if not m or _seen(data.get('session_id'), t['id']) else m
    except Exception:
        return ''


def main(argv):
    """tz claim <transcript.jsonl>: check the last turn; exit 1 if a claim is unbacked."""
    if len(argv) != 1 or not os.path.isfile(argv[0]):
        print('usage: tz claim <transcript.jsonl>')
        return 2
    t = turn(argv[0])
    m = judge(t['text'], t['calls'])
    print(m or 'tz claim: no unbacked success claim in the last turn (heuristic)')
    return 1 if m else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
