#!/usr/bin/env python3
"""tz scrub FILE...: replace secret values (from env vars named like KEY/TOKEN/SECRET/PASSWORD, or --secret V) with [REDACTED] in place-safe copies on stdout.
JSON/JSONL stay valid: digit-only secrets are replaced only inside string tokens (adapted from harbor redaction.py, Apache-2.0, see third_party/harbor/NOTICE).
mark_untrusted(): wraps tool output as data (idea from morluto/rea provenance flag, MIT). Fail-open, stdlib only."""
import os, re, sys

_STR = re.compile(r'"[^"\\\n]*(?:\\.[^"\\\n]*)*(?:"|\\?$)', re.MULTILINE)
_NAME = re.compile(r'(KEY|TOKEN|SECRET|PASSWORD|PASSWD)', re.I)


def env_secrets(env=None, floor=8):
    """Secret values from the environment; short values are skipped (they would mangle ordinary text)."""
    return [v for k, v in (env if env is not None else os.environ).items() if _NAME.search(k) and len(v) >= floor]


def _sub(text, secrets):
    for s in secrets:
        text = text.replace(s, '[REDACTED]')
    return text


def scrub(text, secrets, suffix=''):
    secrets = sorted({s for s in secrets if s}, key=len, reverse=True)
    if not any(s in text for s in secrets):
        return text
    if suffix.lower() in ('.json', '.jsonl') and any(s.isdigit() and s in text for s in secrets):
        text = _STR.sub(lambda m: _sub(m.group(), secrets), text)
        secrets = [s for s in secrets if not s.isdigit()]
    return _sub(text, secrets)


def mark_untrusted(text, source='tool'):
    """Tag text that came from outside so the model treats it as data, not instructions."""
    return f'<untrusted source="{source}">\n{text}\n</untrusted>'


def main(argv):
    secrets = env_secrets() + [argv[i + 1] for i, a in enumerate(argv) if a == '--secret' and i + 1 < len(argv)]
    files = [a for i, a in enumerate(argv) if not a.startswith('--') and (i == 0 or argv[i - 1] != '--secret')]
    for f in files:
        try:
            sys.stdout.write(scrub(open(f, errors='replace').read(), secrets, os.path.splitext(f)[1]))
        except OSError as e:
            print(f'tz scrub: {f}: {e}', file=sys.stderr); return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
