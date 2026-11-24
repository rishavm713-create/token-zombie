#!/usr/bin/env python3
# `tz similar [QUERY..] [--n N]`: read-only GitHub repo search (via the user's `gh`) for tools like tz, ranked by recent maintenance then stars.
# Prints name / stars / last push / licence / description. Nothing is cloned or installed: vet a repo with `tz skills preview DIR` after cloning it yourself.
import json, subprocess, sys, time

DEFAULT = 'claude code token saving'


def search(q, n=10):
    r = subprocess.run(['gh', 'search', 'repos', q, '--limit', str(n * 2), '--json', 'fullName,stargazersCount,pushedAt,license,description,url'],
                       capture_output=True, text=True, timeout=60)
    if r.returncode:
        raise RuntimeError((r.stderr or 'gh failed').strip()[:200])
    rows = json.loads(r.stdout or '[]')
    rows.sort(key=lambda x: (x.get('pushedAt', '')[:7], x.get('stargazersCount', 0)), reverse=True)
    return rows[:n]


def main(argv):
    n = 10
    if '--n' in argv:
        i = argv.index('--n'); n = int(argv[i + 1]); argv = argv[:i] + argv[i + 2:]
    q = ' '.join(argv) or DEFAULT
    try:
        rows = search(q, n)
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as e:
        print(f'tz similar: {e}', file=sys.stderr); return 1
    for x in rows:
        lic = (x.get('license') or {}).get('name') or 'no licence'
        print(f"{x['fullName']}  *{x['stargazersCount']}  pushed {x['pushedAt'][:10]}  {lic}\n   {(x.get('description') or '')[:110]}")
    print(f'{len(rows)} repos (GitHub search, read-only). Ideas only: check licence, never run unvetted code (tz skills preview DIR).')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
