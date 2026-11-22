#!/usr/bin/env python3
# TZ skill finder: curated catalog search, safety preview, staged reversible install. LOCAL ONLY: no network code here.
#  tz skills find QUERY        rank catalog entries by task fit (tags/name/desc), license known, maintenance not stars
#  tz skills preview DIR       scan a LOCAL clone: SKILL.md size (tokens EST), scripts, network/shell/fs/secret flags
#  tz skills stage DIR --yes   copy a vetted skill into ~/.claude/token-zombie/skills-staged/NAME (refuses RED unless --force)
#  tz skills unstage NAME      remove it again
# The catalog is a starting list (catalog/skills-seed.json + optional ~/.claude/token-zombie/catalog.json), licences are as reported, not verified.
import json, os, re, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.expanduser('~/.claude/token-zombie')
FLAGS = {'network': r'\b(curl|wget|requests\.|urllib|fetch\(|http://|https://|socket)', 'shell': r'\b(subprocess|os\.system|exec\(|eval\(|bash -c|sh -c|child_process)',
         'filesystem': r'\b(rm -rf|shutil\.rmtree|os\.remove|unlink|chmod|chown)', 'secrets': r'(API_KEY|SECRET|TOKEN|PASSWORD|\.ssh|\.aws|credentials|\.env\b)'}
RED = ('secrets', 'filesystem')


def catalog():
    out = []
    for p in (os.path.join(HERE, '..', 'catalog', 'skills-seed.json'), os.path.join(STATE, 'catalog.json')):
        try:
            out += json.load(open(p))
        except (OSError, ValueError):
            pass
    seen, res = set(), []
    for e in out:
        if e.get('name') not in seen:
            seen.add(e.get('name')); res.append(e)
    return res


def find(query, cat=None):
    """Ranked [(score, entry)]. Score = word hits in tags (3), name (2), desc (1) + 1 if licence known. Never stars."""
    ws = [w for w in re.findall(r'[a-z0-9]+', query.lower()) if len(w) > 1]
    r = []
    for e in (cat if cat is not None else catalog()):
        sc = sum(3 * (w in e.get('tags', '').lower().split()) + 2 * (w in e.get('name', '').lower()) + (w in e.get('desc', '').lower()) for w in ws)
        if sc:
            r.append((sc + (1 if e.get('license', 'unknown') != 'unknown' else 0), e))
    return sorted(r, key=lambda x: -x[0])


def preview(d):
    """dict: name, skill_md_tokens (EST chars/4), files, flags {kind: [files]}, verdict GREEN/YELLOW/RED. Reads only; executes nothing."""
    d = os.path.abspath(d)
    if not os.path.isdir(d):
        return {'error': f'{d} is not a directory (clone it yourself first: git clone <repo> <dir>)'}
    flags, files, tok = {}, 0, 0
    for root, ds, fs in os.walk(d):
        ds[:] = [x for x in ds if x != '.git']
        for f in fs:
            p = os.path.join(root, f); files += 1
            try:
                t = open(p, encoding='utf-8', errors='ignore').read(200000)
            except OSError:
                continue
            if f.upper() == 'SKILL.MD':
                tok += len(t) // 4
            if f.endswith(('.py', '.sh', '.js', '.ts', '.mjs', '.md', '.json')):
                for k, rx in FLAGS.items():
                    if re.search(rx, t, re.I) and (k != 'network' or not f.endswith('.md')):
                        flags.setdefault(k, []).append(os.path.relpath(p, d))
    v = 'RED' if any(k in flags for k in RED) else 'YELLOW' if flags else 'GREEN'
    return {'name': os.path.basename(d), 'skill_md_tokens_est': tok, 'files': files, 'flags': flags, 'verdict': v}


def stage(d, force=False):
    pv = preview(d)
    if 'error' in pv:
        return pv
    if pv['verdict'] == 'RED' and not force:
        return {'error': f"verdict RED ({', '.join(k for k in RED if k in pv['flags'])}); read the files, then --force if you accept it", 'preview': pv}
    dst = os.path.join(STATE, 'skills-staged', pv['name'])
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(os.path.abspath(d), dst, ignore=shutil.ignore_patterns('.git'))
    json.dump(pv, open(os.path.join(dst, '.tz-manifest.json'), 'w'), indent=1)
    return {'staged': dst, 'preview': pv}


def unstage(name):
    dst = os.path.join(STATE, 'skills-staged', os.path.basename(name))
    if not os.path.isdir(dst):
        return False
    shutil.rmtree(dst)
    return True


def main(argv):
    a = argv[1:] if argv[:1] == ['skills'] else argv
    c, r = (a[0] if a else ''), a[1:]
    if c == 'find':
        res = find(' '.join(x for x in r if not x.startswith('--')))
        for sc, e in res[:8]:
            print(f"  {sc:2} {e['name']:24} {e.get('kind', ''):7} lic {e.get('license', 'unknown'):12} {e['repo']}\n     {e.get('desc') or e['tags']}")
        print(f'{len(res)} match(es); ranked by tag/name fit + known licence, not stars. Licences as reported, unverified. Next: clone it yourself, then `tz skills preview DIR`.' if res else 'no catalog entry matches; add your own to ~/.claude/token-zombie/catalog.json')
        return 0
    if c in ('preview', 'stage') and r:
        d = r[0]
        if c == 'preview':
            pv = preview(d); print(json.dumps(pv, indent=1)); return 1 if 'error' in pv else 0
        if '--yes' not in r:
            print(json.dumps(preview(d), indent=1)); print('dry run: add --yes to copy this into skills-staged (reversible: tz skills unstage NAME)'); return 0
        res = stage(d, '--force' in r); print(json.dumps(res, indent=1)); return 1 if 'error' in res else 0
    if c == 'unstage' and r:
        print('removed' if unstage(r[0]) else 'not staged'); return 0
    print(__doc__ if False else 'usage: tz skills find QUERY | preview DIR | stage DIR [--yes] [--force] | unstage NAME'); return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
