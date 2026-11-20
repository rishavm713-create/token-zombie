# tz-status.py --startup [N] [--save] [--compare]: what a new chat loads before any work. Advice only.
# Labels: MEASURED = read from chat logs (first-reply usage, chars of each logged part).
#         EST      = chars/4 of a logged part (a rule of thumb, not a count).
#         UNKNOWN  = measured total minus all itemised parts (tool-schema JSON overhead, untracked text).
# No AI calls. Reads each log only up to the first reply (+ a 3 MB tail for tool-use names).
import datetime as dt, glob, json, os, re, statistics
from tzlib import cfg

LONG = 250  # chars: skill description longer than this is flagged
STATE = os.path.expanduser('~/.claude/token-zombie')


def _first(path, parts_wanted):
    """(tokens before first reply, parts{name: chars}, skill_listing, instr[(name,file)], hooks[(out,cmd)], mcp names)."""
    parts, skills, instr, hooks, mcp = {}, '', [], [], set()
    for raw in open(path, encoding='utf-8', errors='ignore'):
        try:
            d = json.loads(raw)
        except Exception:
            continue
        t, m = d.get('type'), d.get('message') or {}
        if m.get('role') == 'assistant' and m.get('usage') and m.get('model') != '<synthetic>':
            u = m['usage']
            tok = sum(u.get(k) or 0 for k in ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens'))
            if tok:
                _first.ts = d.get('timestamp') or ''
                return tok, parts, skills, instr, hooks, mcp
        a = d.get('attachment') or {}
        k = a.get('type')
        if t == 'attachment' and k == 'instructions':
            instr = [(os.path.basename(f.get('path') or '?'), f) for f in a.get('files') or []]
        if not parts_wanted:
            continue
        if t == 'api-request-shape' and 'sys' not in parts:
            s = d.get('shape') or {}
            parts['system prompt'] = len(json.dumps(s.get('system')))
            for tl in s.get('tools') or []:
                n = tl.get('name', '')
                key = 'tools: ' + (n.split('__')[1] if n.startswith('mcp__') else 'built-in')
                parts[key] = parts.get(key, 0) + len(json.dumps(tl))
            parts['sys'] = 1
        elif t == 'attachment':
            if k == 'skill_listing' and not skills:
                skills = a.get('content') or ''
            elif k == 'hook_success' and a.get('hookEvent') == 'SessionStart':
                hooks.append((a.get('stdout') or '', a.get('command') or ''))
            elif k == 'deferred_tools_delta':
                nm = a.get('addedNames') or a.get('addedLines') or []
                parts['deferred tool names'] = parts.get('deferred tool names', 0) + len(json.dumps(nm))
                mcp |= {n.split('__')[1] for n in nm if isinstance(n, str) and n.startswith('mcp__')}
            elif k == 'agent_listing_delta':
                parts['agent list'] = parts.get('agent list', 0) + len(json.dumps(a.get('addedLines')))
            elif k == 'mcp_instructions_delta':
                parts['MCP server instructions'] = parts.get('MCP server instructions', 0) + len(json.dumps(a.get('addedBlocks')))
    return 0, parts, skills, instr, hooks, mcp


def _usage_by_project(logs):
    """{project: {'mcp': {server: n}, 'skill': {name: n}}} from tool-use names in each log's last 3 MB."""
    use = {}
    for f in logs:
        proj = os.path.basename(os.path.dirname(f))
        try:
            sz = os.path.getsize(f)
            with open(f, 'rb') as fh:
                fh.seek(max(0, sz - 3_000_000))
                txt = fh.read().decode('utf-8', 'ignore')
        except Exception:
            continue
        u = use.setdefault(proj, {'mcp': {}, 'skill': {}})
        for s in re.findall(r'"name":\s*"mcp__([^"]+?)__', txt):
            u['mcp'][s] = u['mcp'].get(s, 0) + 1
        for s in re.findall(r'"skill":\s*"([^"]+)"', txt):
            u['skill'][s] = u['skill'].get(s, 0) + 1
    return use


def median_startup(root, n=12):
    """MEASURED median first-reply tokens of the n newest chats (0 if none)."""
    fs = sorted(glob.glob(os.path.join(root, 'projects', '*', '*.jsonl')), key=os.path.getmtime, reverse=True)[:n]
    t = [x for x in (_first(f, False)[0] for f in fs) if x]
    return int(statistics.median(t)) if t else 0


def _short(p):
    return p.replace('-Users-mac', '~').strip('-')[-24:] or '~'


def startup(n=12, save=False, compare=False):
    root = os.path.expanduser((os.environ.get('CLAUDE_CONFIG_DIR') or '~/.claude').split(',')[0])
    logs = sorted(glob.glob(os.path.join(root, 'projects', '*', '*.jsonl')), key=os.path.getmtime, reverse=True)[:n]
    rows, newest = [], None
    for f in logs:
        tok, parts, skills, instr, hooks, mcp = _first(f, newest is None)
        if not tok:
            continue
        rows.append((os.path.basename(os.path.dirname(f)), os.path.basename(f)[:8], tok, sum(len(x.get('content') or '') for _, x in instr), _first.ts))
        if parts.get('sys') and newest is None:
            newest = (tok, parts, skills, instr, hooks, mcp)
    print('STARTUP audit (advice only; no AI calls; nothing is changed)')
    med = 0
    if not rows:
        print('  no chat logs with a first reply: nothing measured')
    else:
        toks = [r[2] for r in rows]
        med = int(statistics.median(toks))
        print(f'MEASURED first-reply size (input+cache before any work), {len(rows)} newest chats:')
        for r in rows:
            d = r[2] - med
            print(f'  {_short(r[0]):24} {r[1]}  {r[2] // 1000}k  CLAUDE+memory {r[3] // 1000}k chars' + (f'  {d // 1000:+d}k vs median' if abs(d) >= 3000 else ''))
        byp = {}
        for r in rows:
            byp.setdefault(r[0], []).append(r[2])
        if len(byp) > 1:
            print('  per project median (MEASURED): ' + '; '.join(f'{_short(p)} {int(statistics.median(v)) // 1000}k (n={len(v)})' for p, v in byp.items()))
        warn = cfg('startup_warn')
        print(f'  median {med // 1000}k, min {min(toks) // 1000}k, max {max(toks) // 1000}k; startup_warn {warn // 1000}k' + ('  WARN: above startup_warn' if med > warn else ''))
    adv, snap = [], {'date': dt.date.today().isoformat(), 'median': med, 'chats': len(rows), 'parts': {}}
    if newest:
        tok, parts, skills, instr, hooks, mcp = newest
        comps = []  # (name, chars, load, who)
        for k, v in parts.items():
            if k != 'sys':
                who = 'platform' if k in ('system prompt', 'tools: built-in', 'agent list', 'deferred tool names', 'MCP server instructions') else 'app/MCP'
                comps.append((k, v, 'names only' if k.startswith('deferred') else 'always', who))
        by = {}
        for ln in skills.splitlines():
            m = re.match(r'- ([\w:.-]+):', ln)
            if m:
                by.setdefault(m.group(1).split(':')[0] if ':' in m.group(1) else 'user/built-in skills', []).append((len(ln), m.group(1)))
        for k, v in by.items():
            comps.append((f'skill list: {k} ({len(v)})', sum(x for x, _ in v), 'always', 'platform' if k == 'anthropic-skills' else 'yours'))
        for nm, f in instr:
            comps.append((f'instructions: {nm}', len(f.get('content') or ''), 'always', 'yours'))
        for out, cmd in hooks:
            comps.append((f'SessionStart hook: {cmd[:30]}', len(out), 'always', 'yours'))
        est = {c[0]: c[1] // 4 for c in comps}
        unknown = max(tok - sum(est.values()), 0)
        print(f'\nCOMPONENTS of the newest chat with a logged request shape. Chars MEASURED; tokens EST (chars/4); share of the measured {tok // 1000}k:')
        print(f"  {'component':44} {'load':10} {'tok(EST)':>8} {'share':>5}  owner")
        for nm, ch, ld, who in sorted(comps, key=lambda c: -c[1]):
            print(f'  {nm[:44]:44} {ld:10} {ch // 4:>8} {100 * (ch // 4) // tok:>4}%  {who}')
        print(f"  {'UNKNOWN (not itemised in logs)':44} {'':10} {unknown:>8} {100 * unknown // tok:>4}%  unknown")
        tot = {w: sum(c[1] // 4 for c in comps if c[3] == w) for w in ('platform', 'app/MCP', 'yours')}
        print(f"  TOTALS: platform-managed ~{tot['platform']} EST, app/MCP schemas ~{tot['app/MCP']} EST (changeable only in app/MCP settings), yours ~{tot['yours']} EST (controllable), unknown ~{unknown}, measured {tok}")
        snap.update(parts={c[0]: c[1] // 4 for c in comps}, totals=dict(tot, unknown=unknown, measured=tok))
        use = _usage_by_project(logs)
        projs = {p for p in use}
        for s in sorted(mcp):
            users = [p for p in projs if use[p]['mcp'].get(s)]
            if not users:
                adv.append((parts.get('deferred tool names', 0) // 4 // max(len(mcp), 1), 'low', f'MCP "{s}" loaded but never used in the {len(logs)} newest chats: disable at user level, enable per project'))
            elif len(users) == 1 and len(projs) > 1:
                adv.append((parts.get('deferred tool names', 0) // 4 // max(len(mcp), 1), 'low', f'MCP "{s}" used only in {_short(users[0])}: enable it only there'))
        sk_disk = {os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(root, 'skills', '*', 'SKILL.md'))}
        used = {k for u in use.values() for k in u['skill']}
        for ln_len, nm in sorted((x for v in by.values() for x in v), reverse=True):
            own = nm in sk_disk  # only skills on disk are the user's to shorten
            if own and ln_len > LONG + len(nm) + 4:
                adv.append(((ln_len - LONG) // 4, 'safe', f'shorten description of skill {nm} ({ln_len} chars > {LONG})'))
            if nm in sk_disk and nm not in used and nm not in ('token-zombie',):
                adv.append((ln_len // 4, 'low', f'skill {nm}: not invoked in the {len(logs)} newest chats: move to skills-off or the one project that uses it'))
        for out, cmd in hooks:
            adv.append((len(out) // 4, 'review', f'SessionStart hook "{cmd[:30]}" injects {len(out)} chars every chat: keep only if wanted in every chat'))
        seen = {}
        for nm, f in instr:
            for ln in set((f.get('content') or '').split('\n')):
                ln = ln.strip(' -*#"')
                if len(ln) >= 40:
                    seen.setdefault(ln.lower(), set()).add(nm)
        for k, v in [x for x in seen.items() if len(x[1]) > 1][:5]:
            adv.append((len(k) // 4, 'safe', f'duplicate line in {", ".join(sorted(v))}: "{k[:50]}..."'))
        newp = {}
        for r in sorted(rows, key=lambda r: r[4], reverse=True):  # by chat start, not log mtime
            newp.setdefault(r[0], r)  # newest chat per project
        big = [(r[3], r[0]) for r in newp.values() if r[3] > 12000]
        if big:
            c, p = max(big)
            adv.append((int((c - 6000) / 4), 'safe', f'CLAUDE.md/memory is {c // 1000}k chars in {_short(p)} (typical {statistics.median([r[3] for r in rows]) // 1000:.0f}k): trim or split with @imports on demand'))
    print('\nHIGHEST-IMPACT RECOMMENDATIONS (EST tokens saved per new chat; safe = no capability lost, low/review = you lose something unless used rarely):')
    for t, risk, s in sorted(adv, reverse=True)[:10] or [(0, '-', 'none found')]:
        print(f'  ~{t:>5} [{risk:6}] {s}')
    print('NOT REACHABLE FROM FILES: system prompt, built-in tools, app tool schemas. To turn off app MCPs see the research note; this tool never edits config.')
    if save:
        os.makedirs(STATE, exist_ok=True)
        p = os.path.join(STATE, f"startup-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
        json.dump(snap, open(p, 'w'))
        print(f'saved snapshot {p}')
    if compare:
        olds = sorted(glob.glob(os.path.join(STATE, 'startup-*.json')))
        olds = [o for o in olds if not save or o != p]
        if not olds:
            print('compare: no earlier snapshot (run --startup --save first)')
        else:
            o = json.load(open(olds[-1]))
            print(f"BEFORE/AFTER vs {os.path.basename(olds[-1])}: median {o.get('median', 0) // 1000}k -> {med // 1000}k ({(med - o.get('median', 0)):+d}); measured per-part changes (EST tokens):")
            for k in sorted(set(o.get('parts', {})) | set(snap['parts'])):
                d = snap['parts'].get(k, 0) - o.get('parts', {}).get(k, 0)
                if abs(d) >= 100:
                    print(f'  {k[:50]:50} {o.get("parts", {}).get(k, 0):>6} -> {snap["parts"].get(k, 0):>6} ({d:+d})')
