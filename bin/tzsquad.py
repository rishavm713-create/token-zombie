#!/usr/bin/env python3
# `tz squad list|diff|pause|resume|kill|open`: lifecycle of per-task worktrees (extends `tz worktree`, same worktrees.json).
# Rebuilt from the documented behaviour of smtg-ai/claude-squad (AGPL-3.0): no code, text or assets copied. See third_party/claude-squad/.
# Local git only: never pushes, never starts an agent or tmux (`open` prints the commands), never auto-accepts prompts.
import json, os, re, shlex, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tzmore import _slug

SECRET = re.compile(r'(^|/)(\.env(\.(?!(example|sample|template)$)[^/]*)?|[^/]*\.(pem|key|p12)|id_(rsa|ed25519)|credentials\.json|settings\.local\.json)$')
UNMERGED = {'DD', 'AU', 'UD', 'UA', 'DU', 'AA', 'UU'}


def git(cwd, *a):
    """(returncode, stdout, stderr) of git in cwd; a missing git is a failure, not a crash."""
    try:
        r = subprocess.run(['git', '-C', cwd, *a], capture_output=True, text=True, encoding='utf-8', errors='replace')
    except OSError as e:
        return 127, '', str(e)
    return r.returncode, r.stdout, r.stderr.strip()[:300]


def trees(repo):
    """[(path, branch or None)] from git; the first row is the main checkout."""
    out = []
    for line in git(repo, 'worktree', 'list', '--porcelain')[1].splitlines():
        if line.startswith('worktree '):
            out.append((line[9:], None))
        elif line.startswith('branch refs/heads/') and out:
            out[-1] = (out[-1][0], line[18:])
    return out


def _same(a, b):
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def _live(v):
    """True if the session's worktree is really on disk (a directory without .git is an orphan)."""
    return bool(v.get('path')) and os.path.exists(os.path.join(v['path'], '.git'))


def _entry(m, slug, repo):
    """Registry entry, else one discovered from git (e.g. made by `tz agent --worktree`); discovered branches are never deleted."""
    old = m.get(slug) or {}
    if old.get('branch'):
        return dict(old)
    br, repo = f'tz/{slug}', os.path.abspath(old.get('repo') or repo)
    found = [p for p, b in trees(repo)[1:] if b == br]
    if not found and git(repo, 'rev-parse', '--verify', '-q', f'refs/heads/{br}')[0]:
        return None
    return dict(path=found[0] if found else None, branch=br, repo=repo, files=old.get('files', []), owns_branch=False)


def _locked(state, fn):
    """fn(map) under the `tz worktree` lock. Unlike tzmore._own it does not drop vanished worktrees: orphans stay resumable."""
    from tzlive import xlock
    os.makedirs(state, exist_ok=True)
    p = os.path.join(state, 'worktrees.json')
    with open(p + '.lock', 'w') as lk:
        xlock(lk)
        m = {}
        if os.path.exists(p):
            try:
                m = json.load(open(p))
            except ValueError:
                return False, f'{p} is not valid JSON; fix or move it first (nothing changed)'
        before = json.dumps(m, sort_keys=True)
        r = fn(m)
        if json.dumps(m, sort_keys=True) != before:
            tmp = p + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(m, f, indent=1)
            os.replace(tmp, p)
        return r


def _with(state, task, repo, fn):
    """Look up one session and its main checkout under the lock, then run fn(map, slug, entry, main)."""
    slug = _slug(task)

    def go(m):
        v = _entry(m, slug, repo)
        if not v:
            return False, f'no session {slug} (no live task and no branch tz/{slug}); run: tz worktree add {slug}'
        t = trees(v['repo'])
        if not t:
            return False, f'{v["repo"]} is not a usable git repository'
        return fn(m, slug, v, t[0][0])
    return _locked(state, go)


def changes(path):
    """[(XY, file)] including untracked ('??') and ignored ('!!') entries; None if git cannot tell."""
    rc, out, _ = git(path, 'status', '--porcelain', '-z', '--no-renames', '--untracked-files=all', '--ignored=matching')
    return None if rc else [(x[:2], x[3:]) for x in out.split('\0') if x]


def _guard(v, main):
    """(error or None, changes): a live worktree may only be touched if it is linked and still on its session branch."""
    p = v['path']
    if _same(p, main):
        return f'{p} is the main checkout; refused', []
    rc, head, _ = git(p, 'symbolic-ref', '-q', '--short', 'HEAD')
    if rc or head.strip() != v['branch']:
        return f'{p} is on {head.strip() or "a detached HEAD"}, not {v["branch"]}; switch back first', []
    st = changes(p)
    return (None, st) if st is not None else (f'git status failed in {p}', [])


def _commit(path, slug):
    """Commit everything in the worktree; on failure restore the index so staging is as before. Returns error text or ''."""
    idx = os.path.join(path, git(path, 'rev-parse', '--git-path', 'index')[1].strip())
    old = open(idx, 'rb').read() if os.path.isfile(idx) else None
    rc, _, err = git(path, 'add', '-A')
    if not rc:
        rc, out, err = git(path, 'commit', '-q', '-m', f'tz squad: paused {slug} on {time.strftime("%Y-%m-%d %H:%M")}')
        err = err or out.strip()[:300]
    if rc and old is not None:
        with open(idx, 'wb') as f:
            f.write(old)
    return (err or 'git commit failed') if rc else ''


def pause(state, task, repo='.', drop_ignored=False):
    """(ok, msg). Commit dirty work on the tz/ branch, remove the worktree, keep the branch and file claims."""
    def go(m, slug, v, main):
        if v.get('paused'):
            return False, f'{slug} is already paused'
        notes = []
        if _live(v):
            err, st = _guard(v, main)
            if err:
                return False, err
            if any(x in UNMERGED for x, _ in st) or not git(v['path'], 'rev-parse', '-q', '--verify', 'MERGE_HEAD')[0]:
                return False, f'{slug}: merge in progress; finish or abort it, then pause (nothing changed)'
            dirty = [(x, f) for x, f in st if x != '!!']
            ignored = [f for x, f in st if x == '!!']
            bad = [f for x, f in dirty if 'D' not in x and SECRET.search(f)]
            if bad:
                return False, f'refused: would commit likely secret file(s) {", ".join(bad[:5])}; ignore or move them (nothing changed)'
            lost = [f for f in ignored if SECRET.search(f)]
            if lost and not drop_ignored:
                return False, f'refused: removing the worktree deletes ignored {", ".join(lost[:5])}; copy out, or --drop-ignored'
            if dirty:
                err = _commit(v['path'], slug)
                if err:
                    return False, f'{slug}: commit failed, worktree kept: {err}'
                notes.append(f'committed {len(dirty)} changed path(s) locally')
            rc, _, err = git(main, 'worktree', 'remove', v['path'])
            if rc:
                return False, f'{slug}: worktree kept: {err}'
            if ignored:
                notes.append(f'{len(ignored)} ignored path(s) removed with the worktree')
        else:
            notes.append('worktree was already missing or broken; any leftover directory is untouched')
        git(main, 'worktree', 'prune')
        v.update(paused=True, last=v.get('path') or v.get('last'), path=None, repo=main)
        m[slug] = v
        return True, '; '.join([f'paused {slug}: branch {v["branch"]} kept (not pushed)', *notes, f'resume: tz squad resume {slug}'])
    return _with(state, task, repo, go)


def resume(state, task, repo='.'):
    """(ok, msg). Re-create the worktree for the kept (or already existing) tz/ branch; never overwrites a directory."""
    def go(m, slug, v, main):
        if _live(v) and not v.get('paused'):
            return False, f'{slug} is already active at {v["path"]}'
        git(main, 'worktree', 'prune')
        path = v.get('last') or v.get('path') or os.path.join(os.path.dirname(main), slug)
        if os.path.exists(path):
            path = f'{path}-{time.time_ns():x}'
        rc, _, err = git(main, 'worktree', 'add', path, v['branch'])
        if rc:
            return False, f'{slug}: not resumed: {err}'
        v.update(path=path, paused=False, repo=main)
        m[slug] = v
        return True, f'resumed {slug} at {path} on {v["branch"]}'
    return _with(state, task, repo, go)


def kill(state, task, repo='.', force=False):
    """(ok, msg). Delete a session. Without force: clean worktree only, and only a merged TZ-created branch is deleted."""
    def go(m, slug, v, main):
        if _live(v):
            err, st = _guard(v, main)
            if err and not force:
                return False, err
            if _same(v['path'], main):
                return False, err
            risk = [f for x, f in st if x != '!!' or SECRET.search(f)]
            if risk and not force:
                return False, f'kept {slug}: {len(risk)} uncommitted or secret path(s), e.g. {risk[0]}; pause it, or --force'
            rc, _, err = git(main, 'worktree', 'remove', *(['--force'] if force else []), v['path'])
            if rc:
                return False, f'kept {slug}: {err}'
        git(main, 'worktree', 'prune')
        br = v['branch']
        note = f'branch {br} kept (TZ did not create it)'
        if v.get('owns_branch', True) and br.startswith('tz/'):
            rc = git(main, 'branch', '-D' if force else '-d', br)[0]
            note = f'branch {br} kept (not merged, or checked out; --force deletes unmerged work)' if rc else f'branch {br} deleted'
        m.pop(slug, None)
        return True, f'killed {slug}; {note}; released {len(v.get("files", []))} file(s)'
    return _with(state, task, repo, go)


def base_of(main, branch):
    """Commit the branch started from: git's own creation record, else the merge-base with the main checkout."""
    rows = git(main, 'log', '-g', '--format=%H%x09%gs', f'refs/heads/{branch}', '--')[1].strip().splitlines()
    if rows and '\tbranch: Created from' in rows[-1]:
        return rows[-1].split('\t')[0]
    return git(main, 'merge-base', 'HEAD', branch)[1].strip() or 'HEAD'


def diff(state, task, repo='.', patch=False):
    """(ok, text). Everything the session changed since its base, for review before merging."""
    def go(m, slug, v, main):
        base, live = base_of(main, v['branch']), _live(v)
        args = ['diff', '--no-ext-diff', *([] if patch else ['--stat']), base, *([] if live else [v['branch']]), '--']
        rc, out, err = git(v['path'] if live else main, *args)
        if rc:
            return False, f'diff failed: {err}'
        new = [f for x, f in (changes(v['path']) or []) if x == '??'] if live else []
        head = f'{slug}: {v["branch"]} since {base[:10]}' + ('' if live else ' (committed work only; no worktree)')
        return True, '\n'.join([head, out.rstrip() or '(no tracked changes)', *[f'untracked: {f}' for f in new]])
    return _with(state, task, repo, go)


def sessions(state, repo='.'):
    """Rows for registry entries plus unregistered tz/ worktrees of this repo."""
    def go(m):
        found = {b[3:]: None for _, b in trees(repo)[1:] if b and b.startswith('tz/')}
        rows = []
        for slug in sorted(set(m) | set(found)):
            v = _entry(m, slug, repo)
            if not v:
                continue
            status = 'paused' if v.get('paused') else 'active' if _live(v) else 'orphaned'
            main = (trees(v['repo']) or [(None, None)])[0][0]
            ahead = git(main, 'rev-list', '--count', f'{base_of(main, v["branch"])}..{v["branch"]}', '--')[1].strip() if main else ''
            dirty = sum(x != '!!' for x, _ in (changes(v['path']) or [])) if status == 'active' else 0
            rows.append(dict(task=slug, status=status, branch=v['branch'], path=v.get('path'), dirty=dirty, ahead=int(ahead) if ahead else None))
        return True, rows
    return _locked(state, go)


def open_cmd(state, task, repo='.', program='claude'):
    """(ok, text). The tmux commands that run an agent in the background in this session's worktree (printed, never run)."""
    def go(m, slug, v, main):
        if not _live(v):
            return False, f'{slug} has no worktree; run: tz squad resume {slug}'
        name = f'tz-{slug}'
        return True, (f'run these yourself (TZ starts nothing; needs tmux):\n'
                      f'  tmux new-session -d -s {name} -c {shlex.quote(v["path"])} {shlex.quote(program)}\n'
                      f'  tmux attach -t {name}    # detach again with ctrl-b d')
    return _with(state, task, repo, go)


USAGE = ('usage: tz squad list [--json] | diff TASK [--patch] | pause TASK [--drop-ignored] | resume TASK | '
         'kill TASK [--force] | open TASK [--program CMD]')


def main(argv):
    from tzbus import sdir
    c, a = (argv[0], argv[1:]) if argv else ('list', [])
    state = sdir()
    if c == 'list':
        ok, rows = sessions(state)
        if not ok or '--json' in a:
            print(json.dumps(rows, indent=1) if ok else rows)
            return 0 if ok else 1
        for r in rows:
            print(f'  {r["task"]}  {r["status"]}  {r["branch"]}  dirty {r["dirty"]}  ahead {"?" if r["ahead"] is None else r["ahead"]}  {r["path"] or "-"}')
        print(f'{len(rows)} session(s) [actual, from local git]')
        return 0
    if c not in ('diff', 'pause', 'resume', 'kill', 'open') or not a or a[0].startswith('--'):
        print(USAGE)
        return 2
    t = a[0]
    if c == 'diff':
        ok, msg = diff(state, t, patch='--patch' in a)
    elif c == 'pause':
        ok, msg = pause(state, t, drop_ignored='--drop-ignored' in a)
    elif c == 'resume':
        ok, msg = resume(state, t)
    elif c == 'kill':
        ok, msg = kill(state, t, force='--force' in a)
    else:
        i = a.index('--program') + 1 if '--program' in a else len(a)
        ok, msg = open_cmd(state, t, program=a[i] if i < len(a) else 'claude')
    print(msg)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
