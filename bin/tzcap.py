#!/usr/bin/env python3
# Token-zombie capability intelligence: inventory of skills / parked skills / plugins / MCP servers, overlap detection,
# relevance advice per prompt, security grade (GREEN/YELLOW/RED) via tz-vet.sh. Read-only: never installs, enables or edits anything.
# Startup cost is split: skill descriptions (est, chars/4) | plugin tools & MCP schemas (UNKNOWN: not in config) | hooks.
import json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

VET = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tz-vet.sh')
STOP = set('the a an and or of to for in on with is it this that use when user you your are be as by from at not'.split())


def _json(p):
    try:
        return json.load(open(p))
    except Exception:
        return {}


def _skill(path):
    try:
        head = open(path, encoding='utf-8', errors='ignore').read(3000)
    except OSError:
        return None
    fm = head.split('---')[1] if head.startswith('---') else ''
    m = re.search(r'^description:\s*(.*)$', fm, re.M)
    n = re.search(r'^name:\s*(.*)$', fm, re.M)
    d = (m.group(1) if m else '').strip()
    return {'name': (n.group(1).strip() if n else os.path.basename(os.path.dirname(path))), 'desc': d, 'tok': (len(d) + 20) // 4, 'path': path}


def inventory(home=None):
    home = home or os.path.expanduser('~')
    cl = os.path.join(home, '.claude')
    inv = {'skills': [], 'parked': [], 'plugins': [], 'mcp': [], 'hooks': 0}
    for root, key in ((os.path.join(cl, 'skills'), 'skills'), (os.path.join(cl, 'skills-off'), 'parked')):
        for d, _, fs in os.walk(root):
            if 'SKILL.md' in fs:
                s = _skill(os.path.join(d, 'SKILL.md'))
                if s:
                    if key == 'parked':
                        s['pack'] = os.path.relpath(d, root).split(os.sep)[0]
                    inv[key].append(s)
    st = _json(os.path.join(cl, 'settings.json'))
    inv['plugins'] = sorted(k for k, v in (st.get('enabledPlugins') or {}).items() if v)
    inv['mcp'] = sorted(set((st.get('mcpServers') or {}).keys()) | set((_json(os.path.join(home, '.claude.json')).get('mcpServers') or {}).keys()))
    inv['hooks'] = sum(len(g.get('hooks', [])) for gs in (st.get('hooks') or {}).values() for g in gs)
    return inv


def words(s):
    return {w for w in re.findall(r'[a-z]{3,}', s.lower()) if w not in STOP}


def duplicates(skills, thr=0.6):
    """Same name, or description word overlap (Jaccard) >= thr. Heuristic: review before removing anything."""
    out, seen = [], {}
    ws = [(s, words(s['desc'] + ' ' + s['name'])) for s in skills]
    for s in skills:
        if s['name'] in seen:
            out.append((s['name'], seen[s['name']]['path'], 'same name'))
        seen.setdefault(s['name'], s)
    for i, (a, wa) in enumerate(ws):
        for b, wb in ws[i + 1:]:
            if a['name'] != b['name'] and wa and wb and len(wa & wb) / len(wa | wb) >= thr:
                out.append((a['name'], b['name'], 'similar description'))
    return out


def advise(inv, prompt, n=5):
    """Rank installed + parked skills by word overlap with the prompt. Heuristic. Parked ones need a pack on first."""
    pw = words(prompt)
    sc = []
    for kind in ('skills', 'parked'):
        for s in inv[kind]:
            k = len(pw & words(s['desc'] + ' ' + s['name'].replace('-', ' ')))
            if k >= 2:
                sc.append((k, kind, s))
    sc.sort(key=lambda x: -x[0])
    return [(s['name'], 'installed (already loaded)' if kind == 'skills' else f"parked in pack '{s.get('pack')}': ~/.claude/skillpack on {s.get('pack')} (ask first)", k) for k, kind, s in sc[:n]]


def grade(path):
    """(GREEN|YELLOW|RED, evidence lines) from tz-vet.sh. Static scan only: cannot prove safety."""
    try:
        r = subprocess.run(['bash', VET, path], capture_output=True, text=True, timeout=120)
    except Exception as e:
        return 'YELLOW', [f'scan failed: {e}']
    ev = [l for l in r.stdout.splitlines() if l.startswith('[')]
    if r.returncode == 1 or any(l.startswith('[HIGH]') for l in ev):
        return 'RED', ev
    if any(l.startswith('[REVIEW]') or re.search(r'minified|Claude config|MCP server|hooks file', l) for l in ev):
        return 'YELLOW', ev
    return 'GREEN', ev


def instructions(cwd, home=None):
    """Instruction files loaded every chat (global + project CLAUDE.md): size, est tokens, duplicate lines across files. Read-only."""
    home = home or os.path.expanduser('~')
    fs = [p for p in (os.path.join(home, '.claude', 'CLAUDE.md'), os.path.join(cwd, 'CLAUDE.md'), os.path.join(cwd, '.claude', 'CLAUDE.md')) if os.path.isfile(p)]
    rows, seen, dup = [], {}, []
    for p in fs:
        t = open(p, encoding='utf-8', errors='ignore').read()
        rows.append((p, len(t) // 4, t.count('\n') + 1))
        for l in {x.strip() for x in t.splitlines() if len(x.strip()) > 40}:
            if l in seen and seen[l] != p:
                dup.append(l[:70])
            seen.setdefault(l, p)
    return rows, dup


def profile(prompt, inv, home, apply=False):
    """Plan which parked packs a prompt needs (on) and which enabled packs it does not (off). apply=True runs the user's own skillpack tool."""
    sp = os.path.join(home, '.claude', 'skillpack')
    want = []
    for name, how, k in advise(inv, prompt):
        m = re.search(r"pack '([^']+)'", how)
        if m and m.group(1) not in want:
            want.append(m.group(1))
    out = [f'on  {w}' for w in want] or ['no pack needed: keep everything parked']
    if apply:
        if not os.path.isfile(sp):
            return out + ['skillpack tool not found: nothing applied']
        for w in want:
            r = subprocess.run([sp, 'on', w], capture_output=True, text=True, timeout=30)
            out.append(f'applied on {w}: exit {r.returncode}')
    else:
        out.append('plan only. Nothing changed. Apply with --yes (runs your skillpack; a running chat does not reload skills: open a new chat). Turn off when done: skillpack off <pack>')
    return out


def _pf(home, name):
    d = os.path.join(home, '.claude', 'token-zombie', 'profiles')
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, name + '.json')


def profile_mgr(sub, name, prompt, inv, home, yes):
    """save: record enabled skill names + wanted packs. apply: dry-run unless --yes; backs up current state first. rollback: undo packs applied.
    MCP/plugins are advisory only (host owns them). Per-capability overhead = est tokens of descriptions."""
    if not re.fullmatch(r'[\w.-]+', name or ''):
        return ['usage: tz profile save|apply|rollback <name> [prompt words] [--yes]']
    p = _pf(home, name)
    now = sorted(s['name'] for s in inv['skills'])
    if sub == 'save':
        want = [l[4:] for l in profile(prompt, inv, home)[:-1] if l.startswith('on  ')]
        json.dump(dict(packs=want, enabled=now, saved=int(__import__('time').time())), open(p, 'w'), indent=1)
        return [f'saved profile {name}: packs {want or "none"}, {len(now)} skills enabled now (backup of current state)']
    if not os.path.isfile(p):
        return [f'no profile {name}']
    j = json.load(open(p))
    if sub == 'apply':
        sp = os.path.join(home, '.claude', 'skillpack')
        out = [f"overhead est: {sum(s['tok'] for s in inv['skills'])} tok now (skill descriptions)"] + [f"{'APPLY' if yes else 'DRY-RUN'} skillpack on {w}" for w in j['packs']]
        if yes and os.path.isfile(sp):
            j['backup'] = now
            j['applied'] = []
            for w in j['packs']:
                r = subprocess.run([sp, 'on', w], capture_output=True, text=True, timeout=30)
                out.append(f'on {w}: exit {r.returncode}')
                if r.returncode == 0:
                    j['applied'].append(w)
            json.dump(j, open(p, 'w'), indent=1)
        elif yes:
            out.append('skillpack tool not found: nothing applied')
        else:
            out.append('dry-run: nothing changed. Re-run with --yes. MCP/plugin changes are advisory: do them in the host.')
        return out
    out = [f"{'ROLLBACK' if yes else 'DRY-RUN'} skillpack off {w}" for w in j.get('applied', [])] or ['nothing applied to roll back']
    sp = os.path.join(home, '.claude', 'skillpack')
    if yes and os.path.isfile(sp):
        for w in j.get('applied', []):
            out.append(f'off {w}: exit {subprocess.run([sp, "off", w], capture_output=True, timeout=30).returncode}')
        j['applied'] = []
        json.dump(j, open(p, 'w'), indent=1)
    return out


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='tz skills|capabilities|security|audit')
    ap.add_argument('cmd', choices=['skills', 'capabilities', 'security', 'audit', 'instructions', 'profile'])
    ap.add_argument('arg', nargs='*')
    ap.add_argument('--yes', action='store_true')
    ap.add_argument('--home', default=os.path.expanduser('~'))
    a = ap.parse_args(argv)
    if a.cmd == 'security':
        if not a.arg or not os.path.isdir(a.arg[0]):
            print('tz security <dir>: give a skill/plugin/repo directory', file=sys.stderr)
            return 2
        g, ev = grade(a.arg[0])
        print(f'{g}  {a.arg[0]}')
        for l in ev[:15]:
            print('  ' + l)
        print('Static scan only: GREEN = no concerning indicators found, not proof of safety. Installing needs your approval.')
        return {'GREEN': 0, 'YELLOW': 0, 'RED': 1}[g]
    if a.cmd == 'instructions':
        rows, dup = instructions(os.getcwd(), a.home)
        for p, t, n in rows:
            print(f'{p}: ~{t} tok est, {n} lines' + ('  <- large: trim or move detail to on-demand files' if t > 2000 else ''))
        print(f'duplicate long lines across files: {len(dup)}' + ''.join(f'\n  {d}' for d in dup[:5]))
        print('Loaded every chat; estimate = chars/4.')
        return 0
    inv = inventory(a.home)
    if a.cmd == 'profile' and a.arg and a.arg[0] in ('save', 'apply', 'rollback') and len(a.arg) > 1:
        print('\n'.join(profile_mgr(a.arg[0], a.arg[1], ' '.join(a.arg[2:]), inv, a.home, a.yes)))
        return 0
    if a.cmd == 'profile':
        print('\n'.join(profile(' '.join(a.arg), inv, a.home, a.yes)))
        return 0
    if a.cmd == 'skills':
        if a.arg:
            for name, how, k in advise(inv, ' '.join(a.arg)) or [('none', 'no installed/parked skill clearly matches; use none', 0)]:
                print(f'{name}: {how} (match {k})')
        else:
            tok = sum(s['tok'] for s in inv['skills'])
            print(f"skills loaded at startup: {len(inv['skills'])} (~{tok} tok est, descriptions only) | parked: {len(inv['parked'])} (~{sum(s['tok'] for s in inv['parked'])} tok est NOT loaded)")
    elif a.cmd == 'capabilities':
        tok = sum(s['tok'] for s in inv['skills'])
        print(f"skills {len(inv['skills'])} (~{tok} tok est) | parked {len(inv['parked'])} | plugins enabled {len(inv['plugins'])} | MCP servers {len(inv['mcp'])} | hooks {inv['hooks']}")
        print('plugin tool schemas / MCP tool schemas: UNKNOWN (not visible in config; MCP ~130 tok per tool each chat start, est by tz-vet)')
        for p in inv['plugins'][:10]:
            print('  plugin ' + p)
        for m in inv['mcp'][:10]:
            print('  mcp ' + m)
        d = duplicates(inv['skills'])
        print(f'overlaps: {len(d)} (heuristic)' + ''.join(f'\n  {x} ~ {y} ({why})' for x, y, why in d[:8]))
        big = sorted(inv['skills'], key=lambda s: -s['tok'])[:3]
        if big:
            print('largest descriptions: ' + ', '.join(f"{s['name']} {s['tok']}t" for s in big))
    else:  # audit: security-grade every installed skill dir (cap 60)
        root = os.path.join(a.home, '.claude', 'skills')
        dirs = sorted(d for d in (os.path.join(root, x) for x in os.listdir(root) if os.path.isdir(os.path.join(root, x)))) if os.path.isdir(root) else []
        cnt = {'GREEN': 0, 'YELLOW': 0, 'RED': 0}
        for d in dirs[:60]:
            g, _ = grade(d)
            cnt[g] += 1
            if g != 'GREEN':
                print(f'{g} {os.path.basename(d)}')
        print(f"audited {min(len(dirs), 60)} of {len(dirs)} skill dirs: {cnt}. Static scan; YELLOW/RED need a human read.")
        return 1 if cnt['RED'] else 0
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
