#!/usr/bin/env python3
# Plan phase gate + check-output pipe advice. Modified Python port, adapted from humanlayer/humanlayer
# .claude/hooks/block-test-output-filtering.sh and apps/riptide-rpi-claude-plugin/skills/implement-plan/SKILL.md,
# and create-plan/references/plan_template.md format (Apache-2.0, Copyright 2025-2026 QueryTale, Inc. d/b/a HumanLayer), see NOTICE.
# Changes: shell tokenizer instead of a whole-line regex, more test runners, advice only (upstream blocks);
# the phase workflow (prose upstream) is rebuilt here as a parser and exit-code gate.
"""tz planphase status|next|gate PLAN.md [--phase N] [--run] [--timeout S]
status: one line per phase. next: print only the first unfinished phase (plus the out-of-scope section).
gate: exit 0 only when every box up to phase N is ticked; 2 = not passed; 1 = usage/read error.
--run also executes phase N's automated `commands` (read the plan first: they run in your shell)."""
import os, re, shlex, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PHASE = re.compile(r'^##\s+Phase\s+(\d+)\b[:.\s-]*(.*)$', re.I)
BOX = re.compile(r'^\s*[-*]\s+\[([ xX])\]\s*(.*)$')


def parse(text):
    """(lines, phases). Headings and boxes inside ``` / ~~~ fences are ignored."""
    lines, phases, cur, kind, fence = text.splitlines(), [], None, 'auto', None
    for i, ln in enumerate(lines):
        f = re.match(r'^\s*(`{3,}|~{3,})(.*)$', ln)
        if f:
            if fence is None:
                fence = f.group(1)
            elif f.group(1).startswith(fence) and not f.group(2).strip():
                fence = None
            continue
        if fence:
            continue
        m = PHASE.match(ln)
        if m or re.match(r'^##?\s', ln):
            if cur:
                cur['end'] = i
            cur, kind = None, 'auto'
            if m:
                cur = {'n': int(m.group(1)), 'title': m.group(2).strip(), 'start': i, 'end': len(lines), 'items': []}
                phases.append(cur)
            continue
        if not cur:
            continue
        if re.match(r'^#{3,}\s|^\*\*.*\*\*:?\s*$', ln):
            kind = 'manual' if re.search(r'manual', ln, re.I) else 'auto'
        b = BOX.match(ln)
        if b:
            cur['items'].append({'done': b.group(1) != ' ', 'text': b.group(2).strip(), 'kind': kind})
    return lines, phases


def current(phases):
    return next((p for p in phases if any(not i['done'] for i in p['items'])), None)


def command(item):
    """The `backticked` command of an automated item, or None."""
    m = re.search(r'`([^`]+)`', item['text'])
    return m.group(1) if m and item['kind'] == 'auto' else None


def run_checks(phase, cwd, timeout):
    """[(cmd, ok, note)] for the phase's automated commands. Commands TZ Safe rejects are not run."""
    from tzops import safe
    out = []
    for it in phase['items']:
        c = command(it)
        if not c:
            continue
        good, why = safe(c, cwd)
        if not good:
            out.append((c, False, 'not run: ' + why))
            continue
        try:  # output is dropped so a long log never reaches the chat; rerun a failing command yourself
            r = subprocess.run(c, shell=True, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=timeout)
            out.append((c, r.returncode == 0, 'exit %d' % r.returncode))
        except subprocess.TimeoutExpired:
            out.append((c, False, 'timeout %ds' % timeout))
    return out


RUNNER = re.compile(r'^(?:(?:bun|npm|yarn|pnpm)(?: --bun)?(?: run)? (?:\S*:)?(?:test|test:ci|typecheck)'
                    r'|(?:(?:bun --bun|npx|bunx) )?turbo run (?:test|test:llm|typecheck)'
                    r'|(?:(?:npx|bunx) )?(?:oxlint|oxfmt|jest|vitest|mocha|tsc|eslint)'
                    r'|pytest|tox|ctest|rspec|mypy|ruff check|go (?:test|vet)|cargo (?:test|clippy)|make (?:test|check)'
                    r'|(?:\S*/)?python[\d.]* -m (?:pytest|unittest|mypy))(?: |$)')
FILTERS = {'head', 'tail', 'grep', 'egrep', 'fgrep', 'rg', 'sed', 'awk', 'less', 'more'}


def _pipelines(cmd):
    """[[stage words, ...], ...]; quoted text stays one word. Unparsable commands give []."""
    cmd = cmd.replace('\\\n', ' ')
    if '<<' in cmd:
        cmd = cmd[:cmd.index('<<')].rsplit('\n', 1)[0] if '\n' in cmd[:cmd.index('<<')] else cmd.split('\n', 1)[0]
    lx = shlex.shlex(cmd, posix=True, punctuation_chars='();<>|&\n')
    lx.whitespace, lx.whitespace_split = ' \t\r', True
    try:
        toks = list(lx)
    except ValueError:
        return []
    pipes = [[[]]]
    for t in toks:
        if t in ('|', '|&'):
            pipes[-1].append([])
        elif t and set(t) <= set('();&|\n') and not (t == '&' and pipes[-1][-1][-1:] == ['>']):
            pipes.append([[]])
        else:
            pipes[-1][-1].append(t)
    return pipes


def filtered_check(cmd):
    """(check command, filter name) when a test/typecheck/lint run is piped into a filter, else None."""
    for stages in _pipelines(cmd or ''):
        found = None
        for words in stages:
            w = list(words)
            while w and (re.match(r'^\w+=', w[0]) or w[0] in ('env', 'time', 'timeout', 'nice') or w[0].isdigit()):
                w.pop(0)
            if not w:
                continue
            if found and w[0] == 'tee':  # full output is saved to a file
                break
            if found and w[0] in FILTERS:
                return found, w[0]
            if RUNNER.match(' '.join(w)):
                found = ' '.join(x for x in w[:3] if not x.isdigit() and x not in ('>', '>&'))
    return None


def check_pipe_advice(data):
    """PreToolUse payload -> advice string or None. Pure; the caller applies feature('check_pipe')."""
    if data.get('tool_name') != 'Bash':
        return None
    hit = filtered_check((data.get('tool_input') or {}).get('command'))
    if not hit:
        return None
    return ('TOKEN ZOMBIE: `%s` piped to %s: lines get hidden and, without pipefail, a failure exits 0. '
            'Use `> log 2>&1; echo $?`, then search the log.' % hit)


def main(argv):
    a, opt = list(argv), {'phase': None, 'timeout': 600}
    run = '--run' in a
    a = [x for x in a if x != '--run']
    try:
        for k in opt:
            if '--' + k in a:
                i = a.index('--' + k)
                opt[k] = int(a[i + 1])
                del a[i:i + 2]
        verb, path = a
        if verb not in ('status', 'next', 'gate'):
            raise ValueError
        with open(path, encoding='utf-8', errors='replace') as h:
            lines, phases = parse(h.read())
    except (ValueError, IndexError):
        print(__doc__)
        return 1
    except OSError as e:
        print('cannot read plan: %s' % e)
        return 1
    if not any(p['items'] for p in phases):
        print('no "## Phase N" section with checkboxes in %s' % path)
        return 1
    cur = current(phases)
    if verb == 'status':
        for p in phases:
            n = len(p['items'])
            d = sum(i['done'] for i in p['items'])
            print('%s Phase %d: %s (%d/%d)%s' % ('>' if p is cur else ' ', p['n'], p['title'], d, n,
                                                 '' if n else ' no checkboxes, not gated'))
        return 0
    if verb == 'next':
        if not cur:
            print('all phases ticked')
            return 0
        skip = None  # "What We're NOT Doing" travels with every phase so scope stays visible
        for i, ln in enumerate(lines[:phases[0]['start']]):
            if re.match(r'^##\s+.*\bNOT Doing\b', ln, re.I):
                skip = i
            elif skip is not None and ln.startswith('## '):
                print('\n'.join(lines[skip:i]))
                skip = None
        if skip is not None:
            print('\n'.join(lines[skip:phases[0]['start']]))
        print('\n'.join(lines[cur['start']:cur['end']]))
        return 0
    want = opt['phase']
    p = next((x for x in phases if x['n'] == want), None) if want is not None else cur
    if want is not None and p is None:
        print('no phase %d' % want)
        return 1
    if p is None:
        if not run:
            print('PASS: all phases ticked')
            return 0
        p = [x for x in phases if x['items']][-1]
    bad = []
    for q in phases[:phases.index(p) + 1]:
        bad += ['Phase %d %s unticked: %s' % (q['n'], i['kind'], i['text']) for i in q['items'] if not i['done']]
    if not p['items']:
        bad.append('Phase %d has no checkboxes: nothing proves it' % p['n'])
    if run:
        res = run_checks(p, os.getcwd(), opt['timeout'])
        for c, good, note in res:
            print('%s %s (%s)' % ('ok  ' if good else 'FAIL', c, note))
        bad += ['Phase %d command failed: %s' % (p['n'], c) for c, good, _ in res if not good]
        if not res:
            print('no automated commands found in Phase %d' % p['n'])
    if bad:
        print('\n'.join(bad))
        print('GATE CLOSED at Phase %d. Manual boxes are for the human to confirm.' % p['n'])
        return 2
    print('PASS: gate open after Phase %d' % p['n'])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
