#!/usr/bin/env python3
"""tz clihelp: list a Python CLI's Click commands from source, one line each; parses only, never runs the target."""
# adapted from HKUDS/CLI-Anything cli-anything-plugin/skill_generator.py (Apache-2.0, Copyright 2026 HKUDS CLI-Anything Team), see NOTICE
# Modified for TOKEN ZOMBIE: command extraction only (no SKILL.md files), first docstring line, no filler text,
# commands without a local group are kept, directory scan and CLI added.
import argparse, ast, json, os, sys

WIDTH = 120  # chars per output line; WHY: one long docstring must not flood the chat
LIMIT = 200  # output lines before truncating
MAX_BYTES = 1_000_000  # larger sources are generated or vendored, not a hand-written CLI
SKIP = {'node_modules', 'venv', '__pycache__', 'site-packages', 'build', 'dist'}
FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)


def display(name):
    """Turn remote-access or remote_access into Remote Access."""
    return name.replace('_', ' ').replace('-', ' ').title()


def decorator_info(function, kind):
    """(owner, declared name) of a @owner.<kind> Click decorator, else None."""
    for decorator in function.decorator_list:
        call = isinstance(decorator, ast.Call)
        target = decorator.func if call else decorator
        if not (isinstance(target, ast.Attribute) and target.attr == kind and isinstance(target.value, ast.Name)):
            continue
        values = decorator.args[:1] + [k.value for k in decorator.keywords if k.arg == 'name'] if call else []
        names = [v.value for v in values if isinstance(v, ast.Constant) and isinstance(v.value, str)]
        return target.value.id, names[0] if names else function.name.replace('_', '-')
    return None


def summary(function):
    """First docstring line, or empty; WHY: invented filler text costs tokens and says nothing."""
    return (ast.get_docstring(function) or '').strip().split('\n')[0].strip()


def collect_groups(functions):
    """Groups in source order, keyed by function name, with nested names such as Alerts Configs."""
    found = [(f, i) for f in functions if (i := decorator_info(f, 'group'))]
    roots = {f.name.lower() for f, (owner, _) in found if owner.lower() == 'click'}
    groups, paths = {}, {}
    for function, (owner, declared) in found:
        parent, local = owner.lower(), display(declared)
        if parent == 'click' or parent in roots:
            path = [local]
        else:
            path = paths.get(parent, [display(owner)]) + [local]
        key = function.name.lower()
        paths[key] = path
        groups[key] = {'name': ' '.join(path), 'description': summary(function), 'commands': []}
    return groups


def extract(source):
    """Command groups declared in one Python source text; raises SyntaxError/ValueError on bad input."""
    nodes = (n for n in ast.walk(ast.parse(source)) if isinstance(n, FUNCS))
    functions = sorted(nodes, key=lambda n: (n.lineno, n.col_offset))
    groups = collect_groups(functions)
    local, loose = bool(groups), {}
    for function in functions:
        info = decorator_info(function, 'command')
        if not info:
            continue
        owner, declared = info
        group = groups.get(owner.lower())
        if not group:  # WHY: upstream drops these; a silently missing command sends the agent back to the source
            name = display(owner) if local and owner.lower() != 'click' else 'General'
            group = loose.setdefault(name, {'name': name, 'description': '', 'commands': []})
        group['commands'].append({'name': declared, 'description': summary(function)})
    return list(groups.values()) + list(loose.values())


def sources(path):
    """The file itself, or every .py under a directory (hidden and vendored folders skipped)."""
    if not os.path.isdir(path):
        yield path
        return
    for root, dirs, files in os.walk(path):
        dirs[:] = sorted(d for d in dirs if d not in SKIP and not d.startswith('.'))
        for name in sorted(files):
            if name.endswith('.py'):
                yield os.path.join(root, name)


def scan(path):
    """([(file, groups)], [skip reasons]) for a file or directory."""
    found, skipped = [], []
    for file in sources(path):
        try:
            if os.path.getsize(file) > MAX_BYTES:
                skipped.append(f'{file}: over {MAX_BYTES} bytes')
                continue
            with open(file, encoding='utf-8-sig') as handle:
                text = handle.read()
            # WHY: the cheap substring test spares parsing files that cannot declare a Click command
            groups = extract(text) if 'click' in text else []
        except (OSError, SyntaxError, ValueError, RecursionError) as error:
            skipped.append(f'{file}: {type(error).__name__}')
            continue
        if groups:
            found.append((file, groups))
    return found, skipped


def line(text):
    """One clipped output line."""
    return text if len(text) <= WIDTH else text[:WIDTH - 3] + '...'


def row(indent, name, description):
    """Indented 'name - description' with inner newlines collapsed."""
    body = ' '.join(name.split()) + (f' - {description}' if description else '')
    return line(indent + body)


def render(found, limit=LIMIT):
    """Compact catalogue; says how many lines were cut."""
    out = []
    for file, groups in found:
        out.append(file)  # never clipped: a cut path cannot be opened
        for group in groups:
            out.append(row('  ', group['name'], group['description']))
            out += [row('    ', c['name'], c['description']) for c in group['commands']]
    if limit and len(out) > limit:
        out = out[:limit] + [f'+{len(out) - limit} more lines (use --limit 0 or a narrower path)']
    return '\n'.join(out)


def main(argv=None):
    """CLI: tz clihelp <file or dir> [--json] [--limit N]; exit 1 when nothing was found."""
    parser = argparse.ArgumentParser(prog='tz clihelp', description=__doc__)
    parser.add_argument('path', help='Python file or directory')
    parser.add_argument('--json', action='store_true', help='machine-readable output')
    parser.add_argument('--limit', type=int, default=LIMIT, help='max text lines, 0 = all')
    args = parser.parse_args(argv)
    if not os.path.exists(args.path):
        print(f'tz clihelp: no such path: {args.path}', file=sys.stderr)
        return 1
    found, skipped = scan(args.path)
    for reason in skipped[:5]:
        print(f'skipped {reason}', file=sys.stderr)
    if len(skipped) > 5:
        print(f'skipped {len(skipped) - 5} more files', file=sys.stderr)
    if args.json:
        print(json.dumps([{'file': f, 'groups': g} for f, g in found]))
    else:
        print(render(found, max(args.limit, 0)) if found else 'no Click commands found')
    return 0 if found else 1


if __name__ == '__main__':
    sys.exit(main())
