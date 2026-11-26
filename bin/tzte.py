# tz te: front door to the bundled TokenEconomizer (third_party/tokeneconomizer, MIT, see NOTICE).
#   tz te <args>            run its CLI for the current folder (status, microskills, toolprune, config, history ...)
#   tz te backfill [--dry-run]   fill the "blank start" gap now: import earlier Claude Code sessions for EVERY
#                                project folder in ~/.claude/projects, not only on each folder's first session.
# No model calls; the import reads local logs only. Needs history_import=on (set below if off).
import glob, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
TE = os.path.join(ROOT, 'third_party', 'tokeneconomizer', 'scripts', 'te')


def _cwd_of(proj):
    logs = sorted(glob.glob(os.path.join(proj, '*.jsonl')), key=os.path.getmtime, reverse=True)[:3]
    for f in logs:
        try:
            with open(f, encoding='utf-8') as fh:
                for _, line in zip(range(60), fh):
                    c = json.loads(line).get('cwd')
                    if c:
                        return c
        except (OSError, ValueError):
            continue
    return None


def _run(args, cwd=None):
    cmd = [TE] + (['--cwd', cwd] if cwd else []) + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300)


def backfill(rest):
    dry = '--dry-run' in rest
    base = os.environ.get('CLAUDE_CONFIG_DIR') or os.path.expanduser('~/.claude')
    done = seen = 0
    seen_set = set()
    for proj in sorted(glob.glob(os.path.join(base, 'projects', '*'))):
        cwd = _cwd_of(proj)
        if not cwd or not os.path.isdir(cwd) or cwd in seen_set or cwd.startswith(('/tmp', '/private/tmp', '/private/var/folders', '/var/folders')):
            continue
        seen_set.add(cwd)
        seen += 1
        r = _run(['history', 'import'] + (['--dry-run'] if dry else []), cwd)
        out = (r.stdout or r.stderr).strip().splitlines()
        print(f'{cwd}: {out[0] if out else "no output"}')
        done += r.returncode == 0 or bool(out and out[0].startswith('not imported'))  # already-learned folders are skipped by design
    print(f'tz te backfill: {done}/{seen} folders ok' + (' (dry run)' if dry else ''))
    return 0 if done == seen else 1



def main(rest):
    if not os.path.exists(TE):
        print('tz te: bundled TokenEconomizer not found at ' + TE, file=sys.stderr)
        return 1
    if rest[:1] == ['backfill']:
        if '--dry-run' not in rest:
            _run(['config', 'set', 'history_import=on', '--global'])
        return backfill(rest[1:])
    return subprocess.call([TE, '--cwd', os.getcwd()] + rest)
