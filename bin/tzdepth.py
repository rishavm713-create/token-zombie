"""tzdepth: response-depth budget advisor. Idea+table from everything-claude-code
skills/token-budget-advisor (MIT, see third_party/everything-claude-code/LICENSE); stdlib rebuild."""
import re

MULT = {'simple': (3, 8), 'medium': (8, 20), 'medium-high': (10, 25), 'complex': (15, 40), 'creative': (10, 30)}
LEVELS = (25, 50, 75, 100)


def est_tokens(text):
    """prose: words*1.3; code-heavy (fenced block or mostly symbols): chars/4."""
    if '```' in text or len(re.findall(r'[{}();=<>\[\]]', text)) > len(text) / 12:
        return max(1, len(text) // 4)
    return max(1, round(len(text.split()) * 1.3))


def classify(text):
    t = text.lower()
    if re.search(r'\b(story|essay|poem|narrative)\b', t):
        return 'creative'
    if re.search(r'\b(compare|architecture|analy[sz]e|design|trade-?offs?)\b', t) or len(text.split()) > 120:
        return 'complex'
    if '```' in text or re.search(r'\b(write|implement|fix|refactor)\b', t):
        return 'medium-high'
    if re.search(r'\b(how|why|explain)\b', t):
        return 'medium'
    return 'simple'


def window(text, cap=None):
    n, (lo, hi) = est_tokens(text), MULT[classify(text)]
    lo, hi = n * lo, n * hi
    if cap:
        lo, hi = min(lo, cap), min(hi, cap)
    return n, lo, hi


def options(text, cap=None):
    """{level%: tokens} using the top of the window."""
    _, _, hi = window(text, cap)
    return {p: round(hi * p / 100) for p in LEVELS}


def parse_level(msg):
    """'50%', 'tldr', 'exhaustive' -> level or None."""
    m = re.search(r'\b(25|50|75|100)\s*%?', msg.lower())
    if m and (('%' in msg) or msg.strip().isdigit()):
        return int(m.group(1))
    t = msg.lower()
    for w, p in (('tldr', 25), ('short', 25), ('brief', 25), ('exhaustive', 100), ('full', 100)):
        if w in t:
            return p
    return None


def render(text, cap=None):
    n, lo, hi = window(text, cap)
    o = options(text, cap)
    return f'input ~{n} tok, answer window {lo}-{hi} tok\n' + '\n'.join(f'[{p}%] ~{v} tok' for p, v in o.items())


def main(argv=None):
    import sys
    argv = sys.argv[1:] if argv is None else argv
    print(render(' '.join(argv) if argv else sys.stdin.read()))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
