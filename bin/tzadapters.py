#!/usr/bin/env python3
# `tz adapters [--rules NAME [--out FILE]]`: capability table of supported agents; --rules prints/writes generated rules text.
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adapters


def main(argv):
    if argv and argv[0] == '--rules':
        n = argv[1] if len(argv) > 1 else ''
        if n not in adapters.NAMES:
            print('unknown agent; one of: ' + ' '.join(adapters.NAMES), file=sys.stderr)
            return 2
        m = adapters.load(n)
        txt = m.generate_rules()
        if not txt:
            print(f'{n}: no rules file target; nothing generated')
            return 0
        if '--out' in argv:
            open(argv[argv.index('--out') + 1], 'w').write(txt + '\n')
            print(f"wrote rules for {n} ({m.RULES_FILE})")
        else:
            print(txt)
        return 0
    if argv and argv[0] == '--usage':
        import json
        n = argv[1] if len(argv) > 1 else ''
        m = adapters.load(n) if n in adapters.NAMES else None
        if not m or not hasattr(m, 'usage'):
            print('no usage parser for ' + (n or '(none)') + '; available: ' + ' '.join(x for x in adapters.NAMES if hasattr(adapters.load(x), 'usage')), file=sys.stderr)
            return 2
        try:
            days = int(argv[argv.index('--days') + 1]) if '--days' in argv else 7
        except (ValueError, IndexError):
            print('--days needs an integer', file=sys.stderr)
            return 2
        u = m.usage(days)
        if '--json' in argv:
            print(json.dumps(u, indent=1))
        else:
            t = u['total']
            print(f"{n} usage (MEASURED, last {days}d): {u['session_count']} sessions, input {t['input_tokens']} (cached {t['cached_input_tokens']}), output {t['output_tokens']} (reasoning {t['reasoning_output_tokens']}), total {t['total_tokens']}")
            for s in u['sessions']:
                print(f"  {s['file'][8:44]:36} {str(s['model'] or '-'):16} total {s['total_tokens']}")
        return 0
    if argv and argv[0] == '--json':
        import json
        print(json.dumps([adapters.info(n) for n in adapters.NAMES], indent=1))
        return 0
    print('agent        status     here  ' + ' '.join(k[:10].ljust(10) for k in adapters.KEYS))
    for n in adapters.NAMES:
        i = adapters.info(n)
        c = i['capabilities']
        here = {True: 'yes', False: 'no', None: '?'}[i['installed_here']]
        print(n.ljust(12) + f" {i['status']:10} {here:5} " + ' '.join(str(c[k] if isinstance(c[k], bool) or c[k] == 'UNKNOWN' else 'yes')[:10].ljust(10) for k in adapters.KEYS))
    print('only claude is REAL for hooks; codex is REAL for usage parsing (tz adapters --usage codex). RULES-ONLY = generates a rules file, nothing else works. here = binary on PATH (measured). Details: tz adapters --json')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
