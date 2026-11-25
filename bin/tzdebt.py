#!/usr/bin/env python3
"""tz debt: list deliberate-shortcut code comments as a debt ledger; reads and reports only."""
# adapted from DietrichGebert/ponytail skills/ponytail-debt/SKILL.md (MIT, Copyright (c) 2026 DietrichGebert), see NOTICE
import argparse, os, re, subprocess, sys

MARKERS = ('shortcut', 'ponytail')
WIDTH = 200  # chars per field; WHY: one minified line must not flood the chat


def pattern(words):
    """ERE matching a marker word right after a comment prefix, so prose mentions stay out."""
    return r'(#|//|/[*]) ?(%s):' % '|'.join(words)


def grep(root, words):
    """[(file, line, text)] from git grep, which skips .git and everything .gitignore ignores."""
    r = subprocess.run(['git', 'grep', '--no-index', '--exclude-standard', '--no-color', '-I', '-z', '-n', '-E',
                        '-e', pattern(words), '--', '.'], cwd=root, capture_output=True, timeout=60)
    if r.returncode > 1:  # 1 = no match; anything else must never read as a clean ledger
        raise RuntimeError(r.stderr.decode('utf-8', 'replace').strip() or 'git grep exit %d' % r.returncode)
    # older git ends only the file name with NUL and keeps ':' after the line number
    rows = re.findall(r'([^\0]+)\0(\d+)[\0:]([^\n]*)\n', r.stdout.decode('utf-8', 'replace'))
    return [(f, int(n), t) for f, n, t in rows]


def clean(s):
    """Printable, capped field text."""
    s = ''.join(c for c in s if c.isprintable()).strip().rstrip('.')
    return s if len(s) <= WIDTH else s[:WIDTH] + '...'


def parse(text, words):
    """(ceiling, upgrade) from `<marker>: <ceiling>, <upgrade>`; None when the hit is not a comment marker."""
    # (?<!:) keeps URLs such as https://shortcut:token@host out of the ledger (and the token off screen)
    m = re.search(r'(?<!:)(?:#|//|/\*) ?(?:%s):(.*)' % '|'.join(words), text)
    if not m:
        return None
    body = re.sub(r'\s*(\*/|-->).*$', '', m.group(1))
    # ';' wins when present so a ceiling may itself contain commas
    parts = re.split(r';' if ';' in body else r',\s+', body, maxsplit=1)
    return clean(parts[0]), clean(parts[1]) if len(parts) > 1 else ''


def owner(root, f, n):
    """git blame author of one line; empty when untracked or not a repo."""
    r = subprocess.run(['git', 'blame', '--porcelain', '-L', '%d,%d' % (n, n), '--', f],
                       cwd=root, capture_output=True, timeout=30)
    m = re.search(r'^author (.*)$', r.stdout.decode('utf-8', 'replace'), re.M)
    return clean(m.group(1)) if r.returncode == 0 and m else ''


def ledger(root='.', words=MARKERS, owners=False):
    """The full report text: one row per marker in file order, then the counts."""
    rows, bare = [], 0
    for f, n, text in sorted(grep(root, words)):
        hit = parse(text, words)
        if not hit:
            continue
        ceiling, upgrade = hit
        bare += not upgrade
        row = '%s:%d, ceiling: %s. %s' % (clean(f), n, ceiling or 'none named',
                                          'upgrade: %s.' % upgrade if upgrade else 'no-trigger.')
        who = owners and owner(root, f, n)
        rows.append(row + (' owner: %s.' % who if who else ''))
    if not rows:
        return 'No shortcut debt. Clean ledger.'
    return '\n'.join(rows + ['%d markers, %d with no trigger. [actual]' % (len(rows), bare)])


def main(argv):
    """CLI: tz debt [path] [--marker WORD] [--owner]."""
    p = argparse.ArgumentParser(prog='tz debt', description='List shortcut: code comments as a debt ledger.')
    p.add_argument('path', nargs='?', default='.')
    p.add_argument('--marker', help='search this word instead of shortcut/ponytail')
    p.add_argument('--owner', action='store_true', help='add the git blame author per row')
    a = p.parse_args(argv)
    if a.marker is not None and not re.fullmatch(r'[\w-]+', a.marker):
        p.error('--marker takes one word (letters, digits, _ or -)')
    try:
        print(ledger(a.path, (a.marker,) if a.marker else MARKERS, a.owner))
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as e:
        print('tz debt: scan failed: %s' % e, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
