#!/usr/bin/env python3
# Zero-orphaned-work layer: durable handoff docs, context-threshold checkpoints, integrity check. Never commits, pushes or discards.
# save -> docs/HANDOFF.md, DEVELOPMENT-STATE.md, NEXT-SESSION.md (overwritten atomically); DECISIONS.md, BUILD-LOG.md (append-only).
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tzhandoff as H

MARKS = (70, 80, 90, 95, 98, 99)
FIELDS = ('objective', 'phase', 'done', 'partial', 'notstarted', 'blockers', 'errors', 'cmds', 'tests', 'roadmap')
LISTS = ('done', 'partial', 'notstarted', 'blockers', 'errors', 'cmds', 'tests', 'roadmap')


def _p(cwd, n):
    return os.path.join(cwd, 'docs', n)


def _sp(cwd):
    return os.path.join(H.hdir(cwd), 'integrity.json')


def _load(cwd):
    try:
        return json.load(open(_sp(cwd)))
    except (OSError, ValueError):
        return {}


def _atomic(p, text):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p + '.tmp', 'w', encoding='utf-8').write(text)
    os.replace(p + '.tmp', p)


def _append(p, text):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'a', encoding='utf-8').write(text)


def git_state(cwd):
    snap = H.snapshot(cwd)
    st = H.git(cwd, 'status', '--porcelain', '-uall') or ''
    staged = [l[3:] for l in st.splitlines() if l[:1] not in (' ', '?', '')]
    snap['staged'] = staged
    snap['last_commit'] = (H.git(cwd, 'log', '-1', '--format=%h %s') or '').strip()
    return snap


def save(cwd, reason='manual', nxt='', decisions=(), **kw):
    """Write the durable handoff files. Lists given replace the old value; omitted fields carry over. Returns the state dict."""
    old = _load(cwd)
    s = {k: old.get(k) for k in FIELDS}
    for k in FIELDS:
        v = kw.get(k)
        if v:
            s[k] = v
        elif s[k] is None:
            s[k] = [] if k in LISTS else ''
    s['next'] = nxt or old.get('next', '')
    g = git_state(cwd)
    s.update(git=g, time=time.strftime('%Y-%m-%d %H:%M'), reason=reason)
    _atomic(_sp(cwd), json.dumps(s, indent=1))
    L = lambda t: '\n'.join('- ' + x for x in t) or '- none'
    ch = g['changed']
    _atomic(_p(cwd, 'HANDOFF.md'), f"""# HANDOFF (authoritative, {s['time']}, reason: {reason})
Objective: {s['objective'] or 'not set'}
Phase: {s['phase'] or 'not set'}
Git: {g['branch']}@{g['head']} ({g['last_commit']}); {len(ch)} uncommitted, {len(g['staged'])} staged
## Done
{L(s['done'])}
## Partial (NOT complete)
{L(s['partial'])}
## Not started
{L(s['notstarted'])}
## Uncommitted files
{L([f'{f} ({h})' for f, h in ch.items()])}
## Blockers / unresolved
{L(s['blockers'])}
## Errors and findings
{L(s['errors'])}
## Commands run (actual results)
{L(s['cmds'])}
## Tests (run / not run)
{L(s['tests'])}
## Roadmap
{L(s['roadmap'])}
NEXT ACTION: {s['next'] or 'NOT SET'}
Decisions: docs/DECISIONS.md. Log: docs/BUILD-LOG.md. Resume: tz handoff resume
""")
    _atomic(_p(cwd, 'DEVELOPMENT-STATE.md'), f"# Development state ({s['time']})\n| state | item |\n|---|---|\n" +
            ''.join(f'| done | {x} |\n' for x in s['done']) + ''.join(f'| PARTIAL | {x} |\n' for x in s['partial']) +
            ''.join(f'| not started | {x} |\n' for x in s['notstarted']))
    _atomic(_p(cwd, 'NEXT-SESSION.md'), f"""# Next session
1. Read docs/HANDOFF.md and docs/DEVELOPMENT-STATE.md.
2. Run `git status` and `git log -1`; compare with Git line in HANDOFF.md (saved at {g['head']}).
3. Open the uncommitted files listed there; reconcile with source.
4. Do not repeat Done items. Finish PARTIAL items before starting new ones.
5. NEXT ACTION: {s['next'] or 'NOT SET'}
Nothing was committed or pushed by tz.
""")
    for d in decisions:
        _append(_p(cwd, 'DECISIONS.md'), f"- {s['time']} {d}\n")
    _append(_p(cwd, 'BUILD-LOG.md'), f"- {s['time']} [{reason}] {g['branch']}@{g['head']}: done {len(s['done'])}, partial {len(s['partial'])}, not started {len(s['notstarted'])}, uncommitted {len(ch)}\n")
    return s


def verify(cwd):
    """(score 0-100, problems). Compares saved handoff with git and with itself. Read-only."""
    s = _load(cwd)
    if not s:
        return 0, ['no saved handoff: run tz handoff save']
    pr, pts = [], 100
    now = git_state(cwd)
    old = s.get('git', {})
    saved_files = set(old.get('changed', {}))
    miss = [f for f in now['changed'] if f not in saved_files and not f.startswith('docs/')]
    if miss:
        pr.append('modified files missing from handoff: ' + ', '.join(miss[:6])); pts -= 20
    edited = [f for f in now['changed'] if f in saved_files and now['changed'][f] != old['changed'][f]]
    if edited:
        pr.append('files edited since handoff: ' + ', '.join(edited[:6])); pts -= 10
    if now['head'] != old.get('head'):
        pr.append(f"stale: HEAD {old.get('head')} -> {now['head']}"); pts -= 25
    if now['branch'] != old.get('branch'):
        pr.append(f"branch changed {old.get('branch')} -> {now['branch']}"); pts -= 15
    if not s.get('next'):
        pr.append('no next action'); pts -= 25
    lt = {x.lower() for x in s.get('partial', []) + s.get('notstarted', [])}
    both = [x for x in s.get('done', []) if x.lower() in lt]
    if both:
        pr.append('marked done but also partial/not started: ' + '; '.join(both[:3])); pts -= 20
    if s.get('done') and not s.get('tests'):
        pr.append('done items with no test record (UNVERIFIED)'); pts -= 10
    if s.get('partial') and not s.get('next'):
        pts -= 0
    if now['changed'] and not s.get('partial') and not s.get('done'):
        pr.append('uncommitted work but nothing recorded'); pts -= 10
    for n in ('HANDOFF.md', 'DEVELOPMENT-STATE.md', 'NEXT-SESSION.md'):
        if not os.path.isfile(_p(cwd, n)):
            pr.append(f'docs/{n} missing'); pts -= 10
    return max(pts, 0), pr


def ctx_mark(cwd, pct):
    """Call with the host-reported context % (never invent one). Returns the mark crossed this call or None.
    >=70/80/90/95/98: cheap checkpoint. 99: emergency save of all handoff files. Marks reset when context drops below 70 (after /compact)."""
    if pct is None:
        return None
    mp = os.path.join(H.hdir(cwd), '.ctx-marks.json')
    try:
        done = set(json.load(open(mp)))
    except (OSError, ValueError):
        done = set()
    if pct < MARKS[0]:
        done = set()
    hit = [m for m in MARKS if pct >= m and m not in done]
    if not hit:
        if not done and os.path.exists(mp):
            os.remove(mp)
        return None
    top = hit[-1]
    if top >= 99:
        save(cwd, reason='EMERGENCY 99%')
    elif not H.checkpoint(cwd) and _load(cwd):
        save(cwd, reason=f'ctx {top}%')
    os.makedirs(H.hdir(cwd), exist_ok=True)
    json.dump(sorted(done | set(hit)), open(mp, 'w'))
    return top


def status(cwd):
    s = _load(cwd)
    sc, pr = verify(cwd)
    return f"handoff {'saved ' + s['time'] if s else 'NONE'}; resume-readiness {sc}/100" + ''.join('\n  - ' + p for p in pr)


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='tz handoff save|status|verify|resume')
    ap.add_argument('cmd', choices=['save', 'status', 'verify', 'resume', 'ctx'])
    ap.add_argument('--cwd', default=os.getcwd())
    ap.add_argument('--next', dest='nxt', default='')
    ap.add_argument('--decision', action='append', default=[])
    ap.add_argument('--objective', default='')
    ap.add_argument('--phase', default='')
    ap.add_argument('--reason', default='manual')
    ap.add_argument('--pct', type=float, default=None, help='ctx: host-reported context percent')
    for k in LISTS:
        ap.add_argument('--' + k, action='append', default=[])
    a = ap.parse_args(argv)
    cwd = os.path.abspath(a.cwd)
    if a.cmd == 'save':
        s = save(cwd, a.reason, a.nxt, a.decision, **{k: getattr(a, k) for k in FIELDS})
        print(f"saved docs/HANDOFF.md, DEVELOPMENT-STATE.md, NEXT-SESSION.md ({len(s['git']['changed'])} uncommitted preserved; nothing committed)")
        print(status(cwd)); return 0
    if a.cmd == 'status':
        print(status(cwd)); return 0
    if a.cmd == 'verify':
        sc, pr = verify(cwd); print(f'resume-readiness {sc}/100'); [print('  - ' + p) for p in pr]; return 0 if sc >= 80 else 1
    if a.cmd == 'ctx':
        m = ctx_mark(cwd, a.pct); print(f'context mark {m}% handled' if m else 'no new mark'); return 0
    t, d = H.resume(cwd); print(t)
    n = _p(cwd, 'NEXT-SESSION.md')
    if os.path.isfile(n):
        print('see docs/NEXT-SESSION.md')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
