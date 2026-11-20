#!/usr/bin/env python3
# GitHub registry (local). Inspects a LOCAL cloned dir only; no network. `--net` is accepted only with --yes and only stores
# URL metadata (nothing fetched: fetching is intentionally not implemented, so no network code exists here).
# registry.json in ~/.claude/token-zombie: key = repo (owner/name or dir name).
import json, os, re, subprocess, sys, time
VET = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tz-vet.sh')
LIC = [('MIT', r'MIT License|Permission is hereby granted, free of charge'), ('Apache-2.0', r'Apache License,? Version 2\.0'),
       ('GPL', r'GNU GENERAL PUBLIC LICENSE'), ('BSD', r'Redistribution and use in source and binary forms'), ('ISC', r'ISC License')]


def path():
    d = os.path.expanduser('~/.claude/token-zombie')
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, 'registry.json')


def load():
    try:
        return json.load(open(path()))
    except Exception:
        return {}


def license_of(d):
    for f in sorted(os.listdir(d)):
        if f.upper().startswith(('LICENSE', 'COPYING')):
            t = open(os.path.join(d, f), errors='ignore').read(4000)
            return next((n for n, rx in LIC if re.search(rx, t)), 'UNKNOWN-license-text')
    return 'NONE'


def deps(d):
    out = []
    p = os.path.join(d, 'package.json')
    if os.path.isfile(p):
        try:
            j = json.load(open(p))
            for sec in ('dependencies', 'devDependencies'):
                for k, v in (j.get(sec) or {}).items():
                    if re.match(r'^[\^~*>]|latest|^$', v) or v.startswith('git'):
                        out.append(f'unpinned {k}@{v}')
        except Exception:
            out.append('package.json unreadable')
    p = os.path.join(d, 'requirements.txt')
    if os.path.isfile(p):
        out += [f'unpinned {l.strip()}' for l in open(p, errors='ignore') if l.strip() and not l.startswith('#') and '==' not in l]
    return out


def commit(d):
    r = subprocess.run(['git', '-C', d, 'rev-parse', 'HEAD'], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else 'UNKNOWN (not a git clone)'


def add(src, name=None):
    if not os.path.isdir(src):
        raise SystemExit('tz reg add: give a LOCAL cloned directory (no network fetch)')
    src = os.path.abspath(src)
    key = name or os.path.basename(src.rstrip('/'))
    reg = load()
    dup = key in reg
    v = subprocess.run(['bash', VET, src], capture_output=True, text=True, timeout=120)
    grade = 'RED' if v.returncode else ('YELLOW' if re.search(r'\[(REVIEW|INFO)\]', v.stdout) else 'GREEN')
    pats = sorted({n for n in ('SKILL.md', 'hooks', 'package.json', 'pyproject.toml', 'Dockerfile', 'AGENTS.md') if os.path.exists(os.path.join(src, n))})
    reg[key] = dict(repo=key, dir=src, commit=commit(src), license=license_of(src), grade=grade, findings=v.stdout.strip().splitlines()[:20],
                    deps=deps(src), patterns=pats, added=time.strftime('%Y-%m-%d'), duplicate_of_prior=dup)
    json.dump(reg, open(path(), 'w'), indent=1)
    return reg[key]


def main(argv):
    if not argv or argv[0] == 'list':
        for k, r in load().items():
            print(f"{k}  {r['grade']}  {r['license']}  {r['commit'][:8]}  {len(r['findings'])} findings")
        return 0
    if argv[0] == 'add' and len(argv) > 1:
        if argv[1].startswith(('http://', 'https://', 'git@')):
            if '--net' in argv and '--yes' in argv:
                print('url metadata only: fetching is not implemented; clone it yourself, then `tz reg add <dir>`')
            else:
                print('tz reg: URLs need --net --yes, and even then nothing is fetched. Clone locally and pass the dir.', file=sys.stderr)
            return 2
        r = add(argv[1], argv[2] if len(argv) > 2 else None)
        print(f"{r['repo']}: {r['grade']} license {r['license']} commit {r['commit'][:8]} deps-flagged {len(r['deps'])}"
              + (' DUPLICATE: already researched, updated entry' if r['duplicate_of_prior'] else ''))
        return 0
    if argv[0] == 'show' and len(argv) > 1:
        r = load().get(argv[1])
        print(json.dumps(r, indent=1) if r else 'not in registry')
        return 0 if r else 1
    print('usage: tz reg [list | add <localdir> [name] | show <name>]', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
