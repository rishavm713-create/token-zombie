#!/usr/bin/env python3
"""tz spec: per-change spec folders (openspec/ layout), checked and merged into living specs."""
# adapted from Fission-AI/OpenSpec src/core/{parsers/requirement-blocks.ts,parsers/code-fence.ts,
# specs-apply.ts,validation/*,../utils/task-progress.ts}, schemas/spec-driven (MIT,
# Copyright (c) 2025 FISSION AI INC), see NOTICE. Ported to stdlib Python and cut down.
import datetime
import os
import re
import sys
from collections import Counter

REQ = re.compile(r'^###\s*Requirement:\s*(.+?)\s*$', re.I)
H2 = re.compile(r'^##\s+(.+?)\s*$')
H3 = re.compile(r'^###\s+\S')
SCEN = re.compile(r'^####\s+')
TASK = re.compile(r'^\s*(?:[-*+]|\d{1,9}[.)])\s*\[(?:\s*([^\]\s]?)\s*\](?![(\[])|\s+\])\s*(.*)')
NAME = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')
SEG = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]*')
OPS = ('added', 'modified', 'removed', 'renamed')
MAX_REQ, MAX_DELTAS = 500, 10

TEMPLATES = {
    'proposal': '## Why\n\n<!-- problem, and why now -->\n\n## What Changes\n\n<!-- bullets; mark **BREAKING** -->\n\n'
                '## Capabilities\n\n<!-- new or modified capability paths -->\n\n## Impact\n\n<!-- code, APIs, deps -->\n',
    'specs': '## ADDED Requirements\n\n### Requirement: <!-- name -->\n<!-- The system SHALL ... -->\n\n'
             '#### Scenario: <!-- name -->\n- **WHEN** <!-- condition -->\n- **THEN** <!-- outcome -->\n',
    'design': '## Context\n\n<!-- only for cross-cutting, risky or ambiguous changes -->\n\n## Decisions\n\n'
              '<!-- choice, and the alternative rejected -->\n\n## Risks\n\n<!-- risk -> mitigation -->\n',
    'tasks': '## 1. <!-- group -->\n\n- [ ] 1.1 <!-- task -->\n- [ ] 1.2 <!-- task -->\n',
}
# WHY: artifact order from schemas/spec-driven/schema.yaml; design is optional there.
REQUIRES = {'proposal': [], 'specs': ['proposal'], 'design': ['proposal'], 'tasks': ['specs']}


class SpecError(Exception):
    """A change or spec that must not be applied."""


# ---------- markdown ----------
def norm(text):
    """Drop BOM and CR line endings."""
    return text.lstrip('﻿').replace('\r\n', '\n').replace('\r', '\n')


def fence_mask(lines):
    """True for every line inside (or delimiting) a code fence."""
    mask, fence = [], None
    for line in lines:
        if fence is None:
            m = re.match(r'^\s*(`{3,}|~{3,})(.*)', line)
            if m and not (m[1][0] == '`' and '`' in m[2]):
                fence = m[1]
            mask.append(fence is not None)
            continue
        mask.append(True)
        m = re.match(r'^\s*(`{3,}|~{3,})\s*$', line)
        if m and m[1][0] == fence[0] and len(m[1]) >= len(fence):
            fence = None
    return mask


def visible(lines):
    """Lines as a reader sees structure: fenced code and HTML comments blanked, numbering kept."""
    # WHY: a commented-out or quoted requirement must never be applied.
    bare = '\n'.join('' if f else l for l, f in zip(lines, fence_mask(lines)))
    return re.sub(r'<!--[\s\S]*?(?:--!?>|$)', lambda m: re.sub(r'[^\n]', ' ', m[0]), bare).split('\n')


def title(text):
    """Heading text without a closing ### sequence."""
    return re.sub(r'[ \t]+#+[ \t]*$', '', text).strip()


def fold(name):
    """Name key that ignores case and spacing, to catch near misses."""
    return ' '.join(name.lower().split())


def sections(vis):
    """[(title, body_start, body_end)] for each ## heading."""
    heads = [(title(m[1]), i) for i, m in ((i, H2.match(l)) for i, l in enumerate(vis)) if m]
    ends = [i for _, i in heads[1:]] + [len(vis)]
    return [(t, i + 1, e) for (t, i), e in zip(heads, ends)]


def blocks(lines, vis, start, end):
    """[(name, raw)] requirement blocks between two line numbers."""
    marks = [(i, title(m[1])) for i, m in ((i, REQ.match(vis[i])) for i in range(start, end)) if m]
    stops = [i for i, _ in marks[1:]] + [end]
    return [(n, '\n'.join(lines[i:e]).rstrip()) for (i, n), e in zip(marks, stops)]


# ---------- delta ----------
def parse_delta(text):
    """Operations in one delta spec, plus content that would be silently ignored."""
    lines = norm(text).split('\n')
    vis = visible(lines)
    plan = {'added': [], 'modified': [], 'removed': [], 'renamed': [], 'errors': [], 'warnings': [], 'purpose': ''}
    inside = set()
    for head, start, end in sections(vis):
        m = re.fullmatch(r'(added|modified|removed|renamed) requirements', head, re.I)
        if head.lower() == 'purpose':
            plan['purpose'] = '\n'.join(vis[start:end]).strip()
        if not m:
            continue
        inside.update(range(start, end))
        op = m[1].lower()
        if op == 'removed':
            for line in vis[start:end]:
                r = REQ.match(line) or re.match(r'^\s*[-*+]\s*`?###\s*Requirement:\s*(.+?)`?\s*$', line)
                if r:
                    plan['removed'].append(title(r[1]))
        elif op == 'renamed':
            renames(vis[start:end], plan)
        else:
            plan[op] += blocks(lines, vis, start, end)
            plan['warnings'] += [f'"{vis[i].strip()}" is not a "### Requirement:" header'
                                 for i in range(start, end) if H3.match(vis[i]) and not REQ.match(vis[i])]
    plan['errors'] += [f'"{vis[i].strip()}" is outside a delta section, so it would be ignored'
                       for i in range(len(vis)) if i not in inside and REQ.match(vis[i])]
    return plan


def renames(body, plan):
    """Collect FROM:/TO: pairs; an unpaired side is an error."""
    pending = None
    for line in body:
        m = re.match(r'^\s*[-*+]?\s*(FROM|TO):\s*`?###\s*Requirement:\s*(.+?)`?\s*$', line)
        if not m:
            continue
        side, name = m[1], title(m[2])
        if side == 'FROM':
            if pending:
                plan['errors'].append(f'RENAMED FROM "{pending}" has no TO:')
            pending = name
        elif pending:
            plan['renamed'].append((pending, name))
            pending = None
        else:
            plan['errors'].append(f'RENAMED TO "{name}" has no FROM:')
    if pending:
        plan['errors'].append(f'RENAMED FROM "{pending}" has no TO:')


def conflicts(plan):
    """Duplicate names and names claimed by two operations."""
    names = {'ADDED': [n for n, _ in plan['added']], 'MODIFIED': [n for n, _ in plan['modified']],
             'REMOVED': plan['removed'], 'RENAMED FROM': [f for f, _ in plan['renamed']],
             'RENAMED TO': [t for _, t in plan['renamed']]}
    out = [f'duplicate requirement in {k}: "{n}"' for k, v in names.items()
           for n in sorted({n for n in v if v.count(n) > 1})]
    for a, b in (('MODIFIED', 'REMOVED'), ('MODIFIED', 'ADDED'), ('ADDED', 'REMOVED'),
                 ('RENAMED TO', 'ADDED'), ('RENAMED FROM', 'MODIFIED')):
        out += [f'"{n}" is in both {a} and {b}' for n in sorted(set(names[a]) & set(names[b]))]
    gone = {fold(n) for n in plan['removed']}
    out += [f'"{n}" is in both RENAMED and REMOVED' for n in names['RENAMED FROM'] if fold(n) in gone]
    return out


def scenarios(raw):
    """[(name, visible_body)] for each #### block of a requirement."""
    vis = visible(raw.split('\n'))
    marks = [i for i, l in enumerate(vis) if SCEN.match(l)]
    return [(re.sub(r'^Scenario:\s*', '', title(SCEN.sub('', vis[i])), flags=re.I),
             '\n'.join(vis[i + 1:e])) for i, e in zip(marks, marks[1:] + [len(vis)])]


def block_issues(op, name, raw):
    """(errors, warnings) for one ADDED or MODIFIED requirement."""
    vis = visible(raw.split('\n'))[1:]
    cut = next((i for i, l in enumerate(vis) if l.startswith('###')), len(vis))
    body = '\n'.join(vis[:cut]).strip()
    tag, errors, warnings = f'{op} "{name}"', [], []
    if not re.search(r'\b(SHALL|MUST)\b', body):
        errors.append(f'{tag}: requirement text needs SHALL or MUST')
    if len(body) > MAX_REQ:
        warnings.append(f'{tag}: text over {MAX_REQ} chars; move detail into scenarios')
    found = scenarios(raw)
    if not found:
        errors.append(f'{tag}: needs at least one "#### Scenario:"')
    for s, text in found:
        if not (re.search(r'\b(WHEN|GIVEN)\b', text) and re.search(r'\bTHEN\b', text)):
            warnings.append(f'{tag}: scenario "{s}" needs a WHEN/GIVEN and a THEN')
    return errors, warnings


# ---------- merge ----------
def split_spec(text):
    """Main spec -> (before, preamble, blocks, after) around '## Requirements'."""
    lines = norm(text).split('\n')
    vis = visible(lines)
    secs = sections(vis)
    if any(re.fullmatch(r'(added|modified|removed|renamed) requirements', t, re.I) for t, _, _ in secs):
        raise SpecError('main spec contains delta headers; fix it first')
    hit = next(((s, e) for t, s, e in secs if t.lower() == 'requirements'), None)
    start, end = hit or (len(lines), len(lines))
    if any(REQ.match(l) and not start <= i < end for i, l in enumerate(vis)):
        raise SpecError('main spec has a requirement outside "## Requirements"; fix it first')
    found = blocks(lines, vis, start, end)
    if len({n for n, _ in found}) != len(found):
        raise SpecError('main spec has duplicate requirement names; fix it first')
    first = next((i for i in range(start, end) if REQ.match(vis[i])), end)
    before = '\n'.join(lines[:start - 1] if hit else lines).rstrip()
    return before, '\n'.join(lines[start:first]).strip('\n'), found, '\n'.join(lines[end:]).strip('\n')


def foreign_tail(raw):
    """A non-requirement ### section hiding inside a block, or ''."""
    lines = raw.split('\n')
    vis = visible(lines)
    at = next((i for i in range(1, len(vis)) if H3.match(vis[i])), None)
    return '' if at is None else '\n'.join(lines[at:]).rstrip()


def replaceable(reqs, name, new_raw=''):
    """Refuse to drop content the merge cannot name."""
    tail = foreign_tail(reqs[name])
    if tail and tail not in new_raw:
        raise SpecError(f'"{name}" holds another ### section that would be lost; move it first')


def lookup(reqs, name, op):
    """Existing key for name; a case-only near miss is an error."""
    if name in reqs:
        return name
    near = next((k for k in reqs if fold(k) == fold(name)), None)
    if near:
        raise SpecError(f'{op} "{name}": spec spells it "{near}"')
    return None


def merge(text, plan, cap='spec', change='change'):
    """Apply RENAMED, REMOVED, MODIFIED, ADDED to a spec (None = new). Returns (text, warnings)."""
    bad = plan['errors'] + conflicts(plan)
    if bad:
        raise SpecError('; '.join(bad))
    warnings = []
    if text is None:
        if plan['modified'] or plan['renamed']:
            raise SpecError(f'{cap}: no spec yet, so only ADDED is allowed')
        purpose = plan['purpose'] or f'TBD - created by archiving change {change}. Update Purpose after archive.'
        text = f'# {cap} Specification\n\n## Purpose\n\n{purpose}\n\n## Requirements\n'
    before, preamble, found, after = split_spec(text)
    reqs, order = dict(found), [n for n, _ in found]
    for old, new in plan['renamed']:
        if not lookup(reqs, old, 'RENAMED'):
            if new in reqs:
                continue  # already applied
            raise SpecError(f'RENAMED "{old}": source not found')
        if any(k != old and fold(k) == fold(new) for k in reqs):
            raise SpecError(f'RENAMED "{new}": target already exists')
        raw = reqs.pop(old).split('\n')
        reqs[new] = '\n'.join([f'### Requirement: {new}'] + raw[1:])
        order[order.index(old)] = new
    for name in plan['removed']:
        if lookup(reqs, name, 'REMOVED'):
            replaceable(reqs, name)
            del reqs[name]
        else:
            warnings.append(f'{cap}: REMOVED "{name}" is not in the spec')
    for name, raw in plan['modified']:
        if not lookup(reqs, name, 'MODIFIED'):
            raise SpecError(f'MODIFIED "{name}": not found')
        # WHY: MODIFIED replaces the whole block, so an omitted scenario would vanish silently.
        lost = Counter(s for s, _ in scenarios(reqs[name])) - Counter(s for s, _ in scenarios(raw))
        if lost:
            raise SpecError(f'MODIFIED "{name}" drops scenario(s): {", ".join(lost)}')
        replaceable(reqs, name, raw)
        reqs[name] = raw
    for name, raw in plan['added']:
        if lookup(reqs, name, 'ADDED'):
            if reqs[name].strip() != raw.strip():
                raise SpecError(f'ADDED "{name}": already exists')
            continue
        reqs[name] = raw
    keys = [k for k in order if k in reqs] + [k for k in reqs if k not in order]
    parts = [before, '## Requirements', preamble] + [reqs[k] for k in dict.fromkeys(keys)] + [after]
    return '\n\n'.join(p for p in parts if p) + '\n', warnings


# ---------- files ----------
def read(path):
    """File text, or None when absent."""
    try:
        with open(path, encoding='utf-8') as f:  # strict: never rewrite mangled bytes
            return f.read()
    except FileNotFoundError:
        return None


def write(path, text):
    """Atomic write, creating parents."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    part = path + '.tzpart'
    if os.path.lexists(part):
        os.remove(part)
    with open(part, 'x', encoding='utf-8', newline='') as f:  # 'x' never follows a planted link
        f.write(text)
    os.replace(part, path)


def inside(root, path):
    """path, refused when a symlink or .. takes it out of root."""
    real, base = os.path.realpath(path), os.path.realpath(root)
    if os.path.islink(path) or not real.startswith(base + os.sep):
        raise SpecError(f'path leaves {root}: {path}')
    return path


def change_dir(root, name, must=True):
    """Folder of one active change."""
    if not NAME.fullmatch(name) or name == 'archive':
        raise SpecError(f'change name must be kebab-case: {name!r}')
    path = os.path.join(root, 'changes', name)
    if os.path.exists(path) or os.path.islink(path):
        inside(root, path)
    elif must:
        raise SpecError(f'no change named {name}')
    return path


def spec_files(base):
    """(capability, path) for each spec.md under base, plus stray .md files."""
    specs, stray = [], []
    for d, dirs, files in os.walk(base):
        dirs.sort()
        for f in sorted(files):
            path = os.path.join(d, f)
            cap = os.path.relpath(d, base).replace(os.sep, '/')
            if f == 'spec.md' and cap != '.':
                specs.append((cap, path))
            elif f.endswith('.md'):
                stray.append(os.path.relpath(path, base))
    return specs, stray


def tasks(text):
    """[(done, description, line_no)] for every checkbox line."""
    vis = visible(norm(text or '').split('\n'))
    return [(m[1] in ('x', 'X'), m[2].strip(), i + 1) for i, m in
            ((i, TASK.match(l)) for i, l in enumerate(vis)) if m]


def filled(text):
    """True once a file says something beyond headings and the blank template."""
    for line in visible(norm(text or '').split('\n')):
        if line.startswith('#'):
            continue
        line = re.sub(r'^\s*[-*+]|\[[ xX]?\]|\*\*\w+\*\*|Requirement:|Scenario:|\b\d+(\.\d+)*\.?(?=\s|$)', '', line)
        if line.strip(' #-*'):
            return True
    return False


def skip_specs(cdir):
    """True when the change opts out of spec deltas."""
    return bool(re.search(r'(?m)^skip_specs:\s*true\b', read(os.path.join(cdir, '.openspec.yaml')) or ''))


def check(root, name):
    """(errors, warnings) for one change, including a dry-run merge."""
    cdir = change_dir(root, name)
    errors, warnings, total = [], [], 0
    if not filled(read(os.path.join(cdir, 'proposal.md'))):
        warnings.append('proposal.md is missing or empty')
    specs, stray = spec_files(os.path.join(cdir, 'specs'))
    errors += [f'specs/{s}: ignored; put deltas in specs/<capability>/spec.md' for s in stray]
    for cap, path in specs:
        plan = parse_delta(read(inside(root, path)))
        count = sum(len(plan[o]) for o in OPS)
        total += count
        mine = plan['errors'] + conflicts(plan)
        for op in ('added', 'modified'):
            for req, raw in plan[op]:
                e, w = block_issues(op.upper(), req, raw)
                mine += e
                warnings += [f'{cap}: {x}' for x in w]
        warnings += [f'{cap}: {x}' for x in plan['warnings']]
        if not count:
            mine.append('no delta requirements found (use "## ADDED Requirements" etc.)')
        if not mine:
            try:
                target = inside(root, os.path.join(root, 'specs', cap, 'spec.md'))
                warnings += merge(read(target), plan, cap, name)[1]
            except SpecError as e:
                mine.append(str(e))
        errors += [f'{cap}: {x}' for x in mine]
    if skip_specs(cdir) and specs:
        errors.append('skip_specs is true but the change has spec deltas')
    elif not specs and not skip_specs(cdir):
        errors.append('no spec deltas; add them, or set "skip_specs: true" in .openspec.yaml')
    if total > MAX_DELTAS:
        warnings.append(f'{total} [actual] deltas; consider splitting (over {MAX_DELTAS})')
    todo = read(os.path.join(cdir, 'tasks.md'))
    if todo is not None and not tasks(todo):
        warnings.append('tasks.md has no "- [ ] 1.1 ..." checkbox, so it counts as 0 tasks')
    return errors, warnings


def add(root, name, artifact, cap=''):
    """Write one artifact template; never overwrites."""
    cdir = change_dir(root, name, must=artifact != 'proposal')
    if artifact not in TEMPLATES:
        raise SpecError('artifact must be one of: ' + ', '.join(TEMPLATES))
    if artifact == 'specs':
        if not cap or not all(SEG.fullmatch(s) for s in cap.split('/')):
            raise SpecError('specs needs a capability path, e.g. user-auth')
        path = os.path.join(cdir, 'specs', cap, 'spec.md')
    else:
        path = os.path.join(cdir, artifact + '.md')
    if os.path.exists(path) or os.path.islink(path):
        raise SpecError(f'already exists: {path}')
    write(inside(root, path), TEMPLATES[artifact])
    return path


def written(path):
    """True once a delta file names at least one requirement."""
    plan = parse_delta(read(path))
    return any(x if isinstance(x, str) else x[0] for op in OPS for x in plan[op])


def status(root, name):
    """Short state of one change: artifacts, progress, only the next thing to do."""
    cdir = change_dir(root, name)
    have = {a: filled(read(os.path.join(cdir, a + '.md'))) for a in ('proposal', 'design', 'tasks')}
    specs = spec_files(os.path.join(cdir, 'specs'))[0]
    have['specs'] = skip_specs(cdir) or bool(specs) and all(written(p) for _, p in specs)
    state = {a: 'done' if have[a] else 'ready' if all(have[r] for r in REQUIRES[a]) else 'blocked'
             for a in REQUIRES}
    if not have['design']:
        state['design'] = 'optional'
    out = [f'{name}: ' + ' | '.join(f'{a} {s}' for a, s in state.items())]
    todo = tasks(read(os.path.join(cdir, 'tasks.md'))) if have['tasks'] else []
    if todo:
        out.append(f'tasks {sum(t[0] for t in todo)}/{len(todo)} [actual]')
    waiting = next((a for a, s in state.items() if s == 'ready'), None)
    open_task = next((t for t in todo if not t[0]), None)
    if waiting:
        out.append(f'next: write {waiting} (tz spec add {name} {waiting})')
    elif open_task:
        out.append(f'next: {open_task[1]} (tasks.md:{open_task[2]})')
    elif todo:
        out.append(f'next: tz spec archive {name}')
    return '\n'.join(out)


def listing(root, specs=False):
    """Active changes with progress, or capabilities with requirement names only."""
    out = []
    if specs:
        for cap, path in spec_files(os.path.join(root, 'specs'))[0]:
            vis = visible(norm(read(path)).split('\n'))
            out.append(cap)
            out += [f'  - {title(m[1])}' for m in map(REQ.match, vis) if m]
        return '\n'.join(out) or 'no specs'
    base = os.path.join(root, 'changes')
    for n in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        if n != 'archive' and os.path.isdir(os.path.join(base, n)):
            todo = tasks(read(os.path.join(base, n, 'tasks.md')))
            out.append(f'{n}  tasks {sum(t[0] for t in todo)}/{len(todo)} [actual]')
    return '\n'.join(out) or 'no active changes'


def archive(root, name, allow_incomplete=False, today=None):
    """Merge deltas into specs, then move the change to changes/archive/."""
    cdir = change_dir(root, name)
    errors, warnings = check(root, name)
    if errors:
        raise SpecError('not archived:\n  ' + '\n  '.join(errors))
    left = [t for t in tasks(read(os.path.join(cdir, 'tasks.md'))) if not t[0]]
    if left and not allow_incomplete:
        raise SpecError(f'not archived: {len(left)} [actual] open task(s); finish them or pass --allow-incomplete')
    stamp = today or datetime.date.today().isoformat()
    dest = os.path.join(root, 'changes', 'archive', f'{stamp}-{name}')
    if os.path.lexists(dest):
        raise SpecError(f'not archived: {dest} exists')
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    inside(root, os.path.dirname(dest))
    updates = []  # WHY: every merge is computed before the first write.
    for cap, path in spec_files(os.path.join(cdir, 'specs'))[0]:
        target = inside(root, os.path.join(root, 'specs', cap, 'spec.md'))
        updates.append((target, merge(read(target), parse_delta(read(path)), cap, name)[0]))
    for target, text in updates:
        write(target, text)
    os.rename(cdir, dest)
    return [os.path.relpath(t, root) for t, _ in updates], dest, warnings


USAGE = """usage: tz spec <command> [--dir PROJECT]
  new <change>                       start a change (writes proposal.md)
  add <change> specs <cap>|design|tasks
  status <change>                    artifacts, progress, next step only
  check <change> [--strict]          validate deltas and tasks
  list [--specs]                     changes, or capability + requirement names
  archive <change> [--allow-incomplete]"""


def run(root, cmd, args, flags):
    """Execute one subcommand; returns the exit code."""
    if cmd == 'list' and not args:
        print(listing(root, '--specs' in flags))
    elif cmd == 'new' and len(args) == 1:
        if os.path.lexists(change_dir(root, args[0], must=False)):
            raise SpecError(f'change {args[0]} already exists')
        print(add(root, args[0], 'proposal'))
    elif cmd == 'add' and len(args) in (2, 3):
        print(add(root, *args))
    elif cmd == 'status' and len(args) == 1:
        print(status(root, args[0]))
    elif cmd == 'check' and len(args) == 1:
        errors, warnings = check(root, args[0])
        for kind, items in (('ERROR', errors), ('WARN', warnings)):
            for item in items:
                print(f'{kind}: {item}')
        bad = bool(errors) or ('--strict' in flags and bool(warnings))
        print(f"{'FAIL' if bad else 'PASS'}: {len(errors)} errors, {len(warnings)} warnings [actual]")
        return int(bad)
    elif cmd == 'archive' and len(args) == 1:
        done_specs, dest, warnings = archive(root, args[0], '--allow-incomplete' in flags)
        for w in warnings:
            print(f'WARN: {w}')
        print('updated: ' + (', '.join(done_specs) or 'no specs'))
        print('moved to: ' + dest)
    else:
        print(USAGE)
        return 2
    return 0


def main(argv=None):
    """CLI entry for `tz spec`."""
    argv = list(sys.argv[1:] if argv is None else argv)
    base = os.getcwd()
    if '--dir' in argv:
        i = argv.index('--dir')
        if i + 1 >= len(argv):
            print(USAGE)
            return 2
        base = argv[i + 1]
        del argv[i:i + 2]
    flags = {a for a in argv if a.startswith('--')}
    words = [a for a in argv if not a.startswith('--')]
    if not words or flags - {'--specs', '--strict', '--allow-incomplete'}:
        print(USAGE)
        return 2
    try:
        return run(os.path.join(os.path.abspath(base), 'openspec'), words[0], words[1:], flags)
    except (SpecError, OSError, UnicodeError) as e:
        print(f'tz spec: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
