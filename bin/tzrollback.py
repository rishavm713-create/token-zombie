#!/usr/bin/env python3
# tz rollback: snapshot a work dir before an agent run, restore only the files the run changed.
# Snapshot = `git stash create` commit (or HEAD when clean) + the untracked-file list. Never touches files the run did not change.
# Limit: untracked files that existed before the run and were edited by it are not restored (git does not track them).
import json, os, subprocess, sys
STATE = os.path.expanduser('~/.claude/token-zombie')

def git(cwd, *a):
    return subprocess.run(['git'] + list(a), cwd=cwd, capture_output=True, text=True)

def untracked(cwd):
    return set(x for x in git(cwd, 'ls-files', '-o', '--exclude-standard').stdout.split('\n') if x)

def path(rid):
    return os.path.join(STATE, 'agent', rid + '.snap.json')

def snapshot(cwd, rid):
    """Idempotent: an existing snapshot (resumed run) is kept, because it describes the state before the FIRST attempt."""
    if os.path.exists(path(rid)):
        return True
    if git(cwd, 'rev-parse', '--git-dir').returncode:
        return False
    sha = git(cwd, 'stash', 'create').stdout.strip() or git(cwd, 'rev-parse', 'HEAD').stdout.strip()
    if not sha:
        return False
    os.makedirs(os.path.dirname(path(rid)), exist_ok=True)
    json.dump({'sha': sha, 'untracked': sorted(untracked(cwd))}, open(path(rid), 'w'))
    return True

def restore(cwd, rid):
    """Return the list of files reverted or removed; [] when no snapshot or nothing changed."""
    try:
        s = json.load(open(path(rid)))
    except Exception:
        return []
    done = []
    for f in [x for x in git(cwd, 'diff', '--name-only', s['sha']).stdout.split('\n') if x]:
        if git(cwd, 'cat-file', '-e', '%s:%s' % (s['sha'], f)).returncode == 0:
            git(cwd, 'checkout', s['sha'], '--', f)
        else:
            try: os.remove(os.path.join(cwd, f))
            except OSError: continue
        done.append(f)
    for f in sorted(untracked(cwd) - set(s['untracked'])):
        try: os.remove(os.path.join(cwd, f)); done.append(f)
        except OSError: pass
    return done

if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) == 2 and a[0] in ('snapshot', 'restore'):
        r = (snapshot if a[0] == 'snapshot' else restore)(os.getcwd(), a[1])
        print(r if a[0] == 'snapshot' else '\n'.join(r) or 'nothing to restore')
    else:
        print('usage: tzrollback.py snapshot|restore RUN_ID (in the work dir)', file=sys.stderr); sys.exit(2)
