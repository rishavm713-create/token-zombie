#!/usr/bin/env python3
# Token-zombie capability intelligence: inventory of skills / parked skills / plugins / MCP servers, overlap detection,
# relevance advice per prompt, security grade (GREEN/YELLOW/RED) via tz-vet.sh. Read-only: never installs, enables or edits anything.
# Startup cost is split: skill descriptions (est, chars/4) | plugin tools & MCP schemas (UNKNOWN: not in config) | hooks.
import json, os, re, subprocess, sys, shutil
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
    hidden = bool(re.search(r'^disable-model-invocation:\s*true', fm, re.M))  # not in the model's skill list: 0 tok
    return {'name': (n.group(1).strip() if n else os.path.basename(os.path.dirname(path))), 'desc': d,
            'tok': 0 if hidden else (len(d) + 20) // 4, 'path': path, 'hidden': hidden}


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


def plugin_skills(home=None):
    """Skills of ENABLED plugins (newest cached version), listed every chat as 'plugin:name'. Tokens est = chars/4."""
    cl = os.path.join(home or os.path.expanduser('~'), '.claude')
    out = []
    for k, v in (_json(os.path.join(cl, 'settings.json')).get('enabledPlugins') or {}).items():
        if not v or '@' not in k:
            continue
        plug, mkt = k.split('@', 1)
        base = os.path.join(cl, 'plugins', 'cache', mkt, plug)
        vers = [os.path.join(base, x) for x in os.listdir(base)] if os.path.isdir(base) else []
        if not vers:
            continue
        sk = os.path.join(max(vers, key=os.path.getmtime), 'skills')
        for n in sorted(os.listdir(sk)) if os.path.isdir(sk) else []:
            s = _skill(os.path.join(sk, n, 'SKILL.md')) if os.path.isfile(os.path.join(sk, n, 'SKILL.md')) else None
            if s:
                s['name'] = f"{plug}:{s['name']}"
                out.append(s)
    return out


def skill_usage(home=None, days=30):
    """Skill tool invocations per skill name in chat logs of the last `days` days (MEASURED from transcripts)."""
    import time
    root = os.path.join(home or os.path.expanduser('~'), '.claude', 'projects')
    cut, n = time.time() - days * 86400, {}
    for d, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f)
            if not f.endswith('.jsonl') or os.path.getmtime(p) < cut:
                continue
            for ln in open(p, errors='replace'):
                if '"name":"Skill"' not in ln.replace(' ', ''):
                    continue
                for m in re.finditer(r'"skill"\s*:\s*"([^"]+)"', ln):
                    n[m.group(1)] = n.get(m.group(1), 0) + 1
    return n


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


CODE_EXT = ('.py', '.js', '.ts', '.tsx', '.jsx', '.sh', '.rb', '.go', '.php', '.json', '.yml', '.yaml', '.env', '.cfg', '.ini', '.toml')
SECRET = re.compile(r'AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE[ ]KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|(?i:(password|passwd|secret|api[_-]?key|token))["\']?\s*[:=]\s*["\'][^"\'\s$%{]{8,}["\']')
RISKY = [(re.compile(r'(?<![\w.])(eval|exec)\s*\(|\bos\.system\(|shell\s*=\s*True|\bnew Function\('), 'dangerous call (eval/exec/shell=True)'),
         (re.compile(r'chmod\s+(-R\s+)?[0-7]?777|0o777|\bverify\s*=\s*False'), 'risky permission/setting (777, TLS verify off)'),
         (re.compile(r'(curl|wget)[^|;\n]*[|]\s*(sudo\s+)?(ba|z)?sh\b'), 'download piped into a shell')]


def code_risks(root):
    """Project-code scan: (hardcoded secrets, risky calls) as 'file:line: why' lines. Static patterns only."""
    sec, risk = [], []
    for d, ds, fs in os.walk(root):
        ds[:] = [x for x in ds if x not in ('.git', 'node_modules', '__pycache__', '.venv')]
        for f in fs:
            if not f.endswith(CODE_EXT) and f != '.env':
                continue
            p = os.path.join(d, f)
            try:
                lines = open(p, errors='ignore').read().splitlines()
            except OSError:
                continue
            for n, l in enumerate(lines, 1):
                if len(l) > 600 or l.lstrip().startswith(('#', '//')):
                    continue
                rel = '%s:%d' % (os.path.relpath(p, root), n)
                if SECRET.search(l):
                    sec.append(f'{rel}: hardcoded secret')
                for rx, why in RISKY:
                    if rx.search(l):
                        risk.append(f'{rel}: {why}')
    return sec, risk


def grade(path):
    """(GREEN|YELLOW|RED, evidence lines) from tz-vet.sh. Static scan only: cannot prove safety."""
    try:
        r = subprocess.run([shutil.which('bash') or 'bash', VET, path], capture_output=True, text=True, timeout=120)
    except Exception as e:
        return 'YELLOW', [f'scan failed: {e}']
    ev = [l for l in r.stdout.splitlines() if l.startswith('[')]
    if r.returncode == 1 or any(l.startswith('[HIGH]') for l in ev):
        return 'RED', ev
    if any(l.startswith('[REVIEW]') or re.search(r'minified|Claude config|MCP server|hooks file', l) for l in ev):
        return 'YELLOW', ev
    return 'GREEN', ev


def _claude_files(cwd, home):
    """CLAUDE.md files Claude Code loads: global (+@imports), cwd and parents, .claude/CLAUDE.md. Read-only."""
    out = []
    def add(p, depth=0):
        p = os.path.abspath(os.path.expanduser(p))
        if p in out or not os.path.isfile(p):
            return
        out.append(p)
        if depth < 4:
            for m in re.finditer(r'^\s*@(\S+)', open(p, encoding='utf-8', errors='ignore').read(), re.M):
                q = m.group(1)
                add(q if q.startswith(('/', '~')) else os.path.join(os.path.dirname(p), q), depth + 1)
    add(os.path.join(home, '.claude', 'CLAUDE.md'))
    d, chain = os.path.abspath(cwd), []
    while True:
        chain.append(d)
        if os.path.dirname(d) == d:
            break
        d = os.path.dirname(d)
    for d in reversed(chain):
        add(os.path.join(d, 'CLAUDE.md'))
        add(os.path.join(d, '.claude', 'CLAUDE.md'))
    return out


def instructions(cwd, home=None):
    """Instruction files loaded every chat: size, est tokens, duplicate lines across files. Read-only."""
    home = home or os.path.expanduser('~')
    rows, seen, dup = [], {}, []
    for p in _claude_files(cwd, home):
        t = open(p, encoding='utf-8', errors='ignore').read()
        rows.append((p, len(t) // 4, t.count('\n') + 1))
        for l in {x.strip() for x in t.splitlines() if len(x.strip()) > 40}:
            if l in seen and seen[l] != p:
                dup.append(l[:70])
            seen.setdefault(l, p)
    return rows, dup


_OPP = [
    (r'\balways\b', r'\bnever\b'),
    (r'\buse\b', r"\bavoid\b|\b(?:don't|do not|never) use\b"),
    (r'\bon\b', r'\boff\b'),
    (r'\bcommit\b', r"\b(?:no|don't|do not|never) commit"),
    (r'\bsonnet\b', r'\bopus\b'),
    (r'\benglish\b', r'\bhindi\b'),
    (r'\b(?:terse|short|brief|concise)\b', r'\b(?:detailed|verbose|thorough|long)\b'),
]
_STOP = set('that this with from your have will when only each every then than them they into over also should must keep make sure rule rules file files chat chats'.split())


def _rules(cwd, home):
    out = []
    for p in _claude_files(cwd, home):
        for i, l in enumerate(open(p, encoding='utf-8', errors='ignore').read().splitlines(), 1):
            t = l.strip().lstrip('-*0123456789.) ').strip()
            if len(t) < 15 or l.lstrip().startswith(('#', '@')):
                continue
            out.append((p, i, t, re.sub(r'\W+', ' ', t.lower()).strip()))
    return out


def conflicts(cwd, home=None):
    """Likely opposite rules + duplicate rule lines across CLAUDE.md files. Keyword heuristic (EST), read-only."""
    home = home or os.path.expanduser('~')
    rs = _rules(cwd, home)
    conf, dups, seen = [], [], {}
    for i, (p, n, t, norm) in enumerate(rs):
        if len(norm) > 25 and norm in seen and seen[norm][0] != p:
            dups.append((seen[norm], (p, n), t[:70]))
        seen.setdefault(norm, (p, n))
        wi = {w for w in norm.split() if len(w) >= 4 and w not in _STOP}
        for q, m, u, nu in rs[i + 1:]:
            if nu == norm:
                continue
            common = wi & {w for w in nu.split() if len(w) >= 4 and w not in _STOP}
            for a, b in _OPP:
                if (re.search(a, norm) and re.search(b, nu) and not re.search(b, norm) and not re.search(a, nu)) or \
                   (re.search(b, norm) and re.search(a, nu) and not re.search(a, norm) and not re.search(b, nu)):
                    kw = {w for pat in (a, b) for w in re.findall(r'[a-z]+', pat) if len(w) > 2}
                    if len(common - kw) >= 2:
                        conf.append(((p, n, t), (q, m, u), a))
                        break
    return conf, dups


def _sh(path):
    """argv for the user's skillpack script: Windows cannot exec a shebang script, so run it through bash there."""
    return [shutil.which('bash') or 'bash', path.replace(os.sep, '/')] if os.name == 'nt' else [path]


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
            r = subprocess.run(_sh(sp) + ['on', w], capture_output=True, text=True, timeout=30)
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
                r = subprocess.run(_sh(sp) + ['on', w], capture_output=True, text=True, timeout=30)
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
            out.append(f'off {w}: exit {subprocess.run(_sh(sp) + ["off", w], capture_output=True, timeout=30).returncode}')
        j['applied'] = []
        json.dump(j, open(p, 'w'), indent=1)
    return out


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='tz skills|capabilities|security|audit')
    ap.add_argument('cmd', choices=['skills', 'capabilities', 'security', 'audit', 'instructions', 'profile'])
    ap.add_argument('arg', nargs='*')
    ap.add_argument('--yes', action='store_true')
    ap.add_argument('--effect', action='store_true', help='skills: per-skill uses, tokens after, tests passing (30 d local logs, EST)')
    ap.add_argument('--home', default=os.path.expanduser('~'))
    a = ap.parse_args(argv)
    if a.cmd == 'security':
        if not a.arg or not os.path.isdir(a.arg[0]):
            print('tz security <dir>: give a skill/plugin/repo directory', file=sys.stderr)
            return 2
        g, ev = grade(a.arg[0])
        sec, risk = code_risks(a.arg[0])
        if sec:
            g = 'RED'
        elif risk and g == 'GREEN':
            g = 'YELLOW'
        ev = ev + ['[HIGH] ' + x for x in sec[:10]] + ['[REVIEW] ' + x for x in risk[:10]]
        print(f'{g}  {a.arg[0]}')
        for l in ev[:30]:
            print('  ' + l)
        print('Static scan only: GREEN = no concerning indicators found, not proof of safety. Installing needs your approval.')
        return {'GREEN': 0, 'YELLOW': 0, 'RED': 1}[g]
    if a.cmd == 'instructions':
        rows, dup = instructions(os.getcwd(), a.home)
        for p, t, n in rows:
            print(f'{p}: ~{t} tok est, {n} lines' + ('  <- large: trim or move detail to on-demand files' if t > 2000 else ''))
        print(f'duplicate long lines across files: {len(dup)}' + ''.join(f'\n  {d}' for d in dup[:5]))
        print('Loaded every chat; estimate = chars/4.')
        conf, dups = conflicts(os.getcwd(), a.home)
        for x, y, t in dups[:10]:
            print(f'duplicate: {x[0]}:{x[1]} = {y[0]}:{y[1]}  "{t}"')
        for x, y, k in conf[:10]:
            print(f'[EST keyword heuristic] possible conflict:\n  {x[0]}:{x[1]} {x[2][:80]}\n  {y[0]}:{y[1]} {y[2][:80]}')
        if not conf:
            print('no likely conflicts found [EST keyword heuristic]')
        return 0
    inv = inventory(a.home)
    if a.cmd == 'profile' and a.arg and a.arg[0] in ('save', 'apply', 'rollback') and len(a.arg) > 1:
        print('\n'.join(profile_mgr(a.arg[0], a.arg[1], ' '.join(a.arg[2:]), inv, a.home, a.yes)))
        return 0
    if a.cmd == 'profile':
        print('\n'.join(profile(' '.join(a.arg), inv, a.home, a.yes)))
        return 0
    if a.cmd == 'skills' and a.effect:
        import tzcont
        print('\n'.join(tzcont.skill_effect_lines(tzcont.skill_effect(os.path.join(a.home, '.claude', 'projects')))))
        return 0
    if a.cmd == 'skills':
        if a.arg:
            for name, how, k in advise(inv, ' '.join(a.arg)) or [('none', 'no installed/parked skill clearly matches; use none', 0)]:
                print(f'{name}: {how} (match {k})')
        else:
            tok = sum(s['tok'] for s in inv['skills'])
            print(f"skills loaded at startup: {len(inv['skills'])} (~{tok} tok est, descriptions only) | parked: {len(inv['parked'])} (~{sum(s['tok'] for s in inv['parked'])} tok est NOT loaded)")
            ps = plugin_skills(a.home)
            print(f"plugin skills listed every chat: {len(ps)} (~{sum(s['tok'] for s in ps)} tok est)")
            use = skill_usage(a.home)
            idle = [s for s in inv['skills'] + ps if not s.get('hidden') and not use.get(s['name']) and not use.get(s['name'].split(':')[-1])]
            print(f"invoked in last 30 days [measured, chat logs]: {sum(use.values())} calls, {len(use)} skills"
                  + ''.join(f"\n  {k} {v}x" for k, v in sorted(use.items(), key=lambda x: -x[1])[:8]))
            print(f"listed but not invoked in 30 days: {len(idle)} (~{sum(s['tok'] for s in idle)} tok est per chat, re-read on every call)"
                  + ''.join(f"\n  {s['name']} {s['tok']}t" for s in sorted(idle, key=lambda s: -s['tok'])[:10]))
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
