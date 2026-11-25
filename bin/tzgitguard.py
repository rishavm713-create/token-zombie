#!/usr/bin/env python3
# Opt-in git guardrails (feature git_guard): the agent may not push or run history/work-destroying git commands.
# Blocked-command list adapted from mattpocock/skills skills/misc/git-guardrails-claude-code (MIT, Copyright (c) 2026
# Matt Pocock), see NOTICE; matching is done on TZ's parsed shell commands (tzshell) instead of raw-text grep.
# `tz safe` already blocks the destructive ones by default; this adds "no push at all" and stays on with TZ_SAFE=0.
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tzlib, tzshell

RULES = {'push': 'git push publishes commits',
         'reset-hard': 'git reset --hard destroys uncommitted changes',
         'clean-force': 'git clean -f deletes untracked files',
         'branch-force-delete': 'git branch -D can lose unmerged commits',
         'checkout-dot': 'git checkout . discards working-tree changes',
         'restore-dot': 'git restore . discards working-tree changes'}

_G = r'\bgit\s+(?:-[Cc]\s+\S+\s+|-\S+\s+)*'  # git plus global options, so `git stash push` does not match push
RAW = {'push': _G + r'push\b',
       'reset-hard': _G + r'reset\b[^;&|\n]*--hard\b',
       'clean-force': _G + r'clean\b[^;&|\n]*\s(-[a-zA-Z]*f|--force)',
       'branch-force-delete': _G + r'branch\b[^;&|\n]*\s-D\b',
       'checkout-dot': _G + r'checkout\s+(--\s+)?\.(\s|$)',
       'restore-dot': _G + r'restore\s+(--\s+)?\.(\s|$)'}


def _list(key):
    """A list of strings from config.json, else empty."""
    v = tzlib._conf.get(key)
    return [str(x) for x in v] if isinstance(v, list) else []


def match(args, extra=()):
    """Rule id for one git argument list (words after `git`), or None."""
    i = 0
    while i < len(args) and args[i].startswith('-'):
        i += 2 if args[i] in tzshell.GIT_ARG_OPTS else 1
    if i >= len(args):
        return None
    sub, rest = args[i], args[i + 1:]
    L, S, P, _ = tzshell._opts(rest, tzshell.GL.get(sub, set()))
    if sub in ('push', 'send-pack') or (sub == 'subtree' and 'push' in P):
        return 'push'
    if sub == 'reset' and 'hard' in L:
        return 'reset-hard'
    if sub == 'clean' and ('force' in L or 'f' in S) and not ('dry-run' in L or 'n' in S):
        return 'clean-force'
    if sub == 'branch' and ('delete' in L or S & {'d', 'D'}) and ('force' in L or S & {'f', 'D'}):
        return 'branch-force-delete'
    if sub == 'checkout' and '.' in P:
        return 'checkout-dot'
    if sub == 'restore' and '.' in P:
        staged_only = ('staged' in L or 'S' in S) and not ('worktree' in L or 'W' in S)
        return None if staged_only else 'restore-dot'
    return sub if sub in extra else None


def _walk(cmd, cwd, extra):
    """(rule ids found, complete): reuse tzshell's unwrapping (sudo, bash -c, $(), aliases) by spying on its git hook."""
    found, orig = [], tzshell._git

    def spy(args, ctx):
        rid = match(args, extra)
        if rid:
            found.append(rid)
        orig(args, ctx)  # follows -c aliases, which come back through spy
        return None  # never stop the walk: a later segment may match too

    tzshell._git = spy
    try:
        return found, tzshell.analyze_text(cmd, cwd or os.getcwd()) is None
    except tzshell.ParseError:
        return found, False
    finally:
        tzshell._git = orig


def check(cmd, cwd=None):
    """First blocked rule id in a shell command, or None. Config: git_guard_allow (drop rules), git_guard_block (add subcommands)."""
    allow, extra = set(_list('git_guard_allow')), tuple(_list('git_guard_block'))
    found, complete = _walk(cmd, cwd, extra)
    if not complete:  # unparsed, or another rule ended the walk early: fall back to the raw text (fail closed)
        pats = dict(RAW, **{s: _G + re.escape(s) + r'\b' for s in extra})
        found += [rid for rid, pat in pats.items() if re.search(pat, cmd)]
    return next((r for r in found if r not in allow), None)


def reason(rid):
    """Message shown to the agent for a blocked command."""
    return ('TOKEN ZOMBIE git guard: blocked [%s] (%s). The owner has not given this chat that authority: '
            'do not work around it; ask the owner to run it.' % (rid, RULES.get(rid, 'blocked by your git_guard_block list')))


def hook(data):
    """For tz-guard on PreToolUse: deny reason or ''. Off unless feature git_guard; a crash while on denies."""
    if not tzlib.feature('git_guard') or data.get('tool_name') != 'Bash':
        return ''
    try:
        rid = check((data.get('tool_input') or {}).get('command') or '', data.get('cwd'))
    except Exception:
        return 'TOKEN ZOMBIE git guard: check crashed (fail closed); ask the owner.'
    return reason(rid) if rid else ''


def main(argv):
    """`tz gitguard` shows state; `tz gitguard check "<command>"` exits 2 if it would be blocked."""
    if argv[:1] == ['check'] and len(argv) > 1:
        rid = check(' '.join(argv[1:]), os.getcwd())
        print(reason(rid) if rid else 'allowed')
        return 2 if rid else 0
    if argv:
        print('usage: tz gitguard [check "<command>"]')
        return 1
    allow = set(_list('git_guard_allow'))
    print('git guard: %s (enable: "features": {"git_guard": 1} in ~/.claude/token-zombie/config.json)'
          % ('ON' if tzlib.feature('git_guard') else 'off'))
    print('blocks: ' + ', '.join([r for r in RULES if r not in allow] + _list('git_guard_block')))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
