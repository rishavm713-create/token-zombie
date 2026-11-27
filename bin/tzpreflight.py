#!/usr/bin/env python3
# A/B benchmark preflight. Run it BEFORE any paid A/B run; the first real run was invalid (every arm denied edits, 0 files changed).
# `tz preflight [--evidence D]`         offline checks, free: CLI, isolation, edit permission, fixture not pre-solved, hook parity.
# `tz preflight --validate D`           read-only check of a finished run: per arm status ok, 0 permission denials, >=1 file changed.
# `tz preflight --smoke --yes [--evidence D]`  PAID (capped, shared 900k): S1 edit + command + acceptance; S2 Read, S3 WebFetch,
#   S4 local MCP: the trimmed output must reach the model (it echoes the recall id). Never runs without --yes.
import time, glob, json, os, shutil, subprocess, sys, tempfile

D = os.path.dirname(os.path.abspath(__file__))
Z = os.path.dirname(D)
AB = os.path.join(Z, 'tests', 'ab')


def _fixture_copy(dst):
    shutil.copytree(os.path.join(AB, 'fixture'), dst)
    for c in (['init', '-q'], ['add', '-A'], ['-c', 'user.email=a@a', '-c', 'user.name=pf', 'commit', '-qm', 'snapshot']):
        subprocess.run(['git', '-C', dst, *c], capture_output=True)


def offline(evidence=None):
    """[(check, ok, detail)]; ok None = warning (not a blocker)."""
    R = []
    cl = os.environ.get('TZ_AB_CLAUDE') or shutil.which('claude')
    R.append(('claude CLI found', bool(cl), cl or 'not on PATH (or set TZ_AB_CLAUDE)'))
    live = os.path.realpath(os.path.expanduser('~/.claude'))
    cfg = os.environ.get('TZ_AB_CONFIG')
    R.append(('TZ_AB_CONFIG isolated', bool(cfg and os.path.isdir(cfg) and os.path.realpath(cfg) != live),
              cfg or 'unset: needs an isolated, logged-in CLAUDE_CONFIG_DIR'))
    st = os.environ.get('TZ_AB_STATE')
    R.append(('TZ_AB_STATE isolated', bool(st and os.path.realpath(st) != os.path.realpath(os.path.expanduser('~'))), st or 'unset'))
    src = open(os.path.join(D, 'tzab.py')).read()
    R.append(('runner allows edits', "'acceptEdits'" in src, '--permission-mode acceptEdits in tzab.py'))
    R.append(('runner allows python3', "Bash(python3:*)" in src, 'tasks run python3 -m unittest'))
    T = tempfile.mkdtemp(prefix='tzpf-')
    for t in ('task1', 'task2'):
        w = os.path.join(T, t); _fixture_copy(w)
        r = subprocess.run([shutil.which('bash') or 'bash', os.path.join(AB, 'accept', f'accept_{t}.sh').replace(os.sep, '/'), w.replace(os.sep, '/')], capture_output=True, text=True)
        R.append((f'{t} not pre-solved', r.returncode != 0 and 'REJECT' in r.stdout, 'untouched fixture must REJECT'))
    hj = json.load(open(os.path.join(Z, 'hooks', 'hooks.json')))['hooks']
    rx = open(os.path.join(AB, 'run_experiment.sh')).read()
    R.append(('B arm hooks = hooks.json', "hooks/hooks.json" in rx, f'{len(hj)} events from the plugin file'))
    if evidence:
        empty = not os.path.exists(evidence) or not os.listdir(evidence)
        R.append(('evidence dir new/empty', empty, evidence + ('' if empty else ': holds an old run; use a new dir')))
    # shortcut: no busy check where pgrep is missing (Windows); add one if A/B runs overlap there
    busy = subprocess.run(['pgrep', '-f', 'tzab.py'], capture_output=True, text=True).stdout.split() if shutil.which('pgrep') else []
    busy = [p for p in busy if p != str(os.getpid())]
    R.append(('no A/B run in progress', not busy, ' '.join(busy) or 'none'))
    return R


def _result_event(stream):
    ev = None
    try:
        for l in open(stream):
            if '"type":"result"' in l.replace(' ', ''):
                try:
                    ev = json.loads(l)
                except Exception:
                    pass
    except OSError:
        pass
    return ev


def _changed(work):
    r = subprocess.run(['git', '-C', work, 'status', '--porcelain'], capture_output=True, text=True)
    return len([l for l in r.stdout.splitlines() if l.strip()]) if r.returncode == 0 else None


def validate(evdir):
    """Per arm: dict(status, denials, changed, valid). An arm is valid only if every session ran ok, had 0 permission denials
    and its work dir changed >=1 file. A run is valid only if every arm is."""
    arms = {}
    for rf in sorted(glob.glob(os.path.join(evdir, '*.result.json'))):
        name = os.path.basename(rf)[:-12]
        arm = name.rstrip('0123456789').removesuffix('p') if name[-2:-1] == 'p' else name
        res = json.load(open(rf))
        ev = _result_event(os.path.join(evdir, f'{name}.stream.jsonl')) or {}
        a = arms.setdefault(arm, dict(sessions=[], denials=0, status_ok=True))
        a['sessions'].append(name)
        a['denials'] += len(ev.get('permission_denials') or [])
        a['status_ok'] &= res.get('status') == 'ok' and not ev.get('is_error')
    for arm, a in arms.items():
        a['changed'] = _changed(os.path.join(evdir, 'work', arm))
        a['valid'] = bool(a['status_ok'] and a['denials'] == 0 and a['changed'])
    return arms


SMOKE_AGG = 900_000  # shared by S1-S4 (one evidence dir); env TZ_PF_AGG can only LOWER it
SCEN_CAP = 200_000
WEB_URL = 'https://www.rfc-editor.org/rfc/rfc9110.txt'


def agg_cap():
    try:
        return min(SMOKE_AGG, int(os.environ.get('TZ_PF_AGG') or SMOKE_AGG))
    except ValueError:
        return SMOKE_AGG


def live_sum():
    """sha256 over the live config the smoke must never touch: ~/.claude/settings.json + the installed TZ copy.
    env TZ_PF_LIVE (':'-separated paths) replaces the list in tests."""
    import hashlib
    paths = (os.environ.get('TZ_PF_LIVE') or '').split(':') if os.environ.get('TZ_PF_LIVE') else \
        [os.path.expanduser('~/.claude/settings.json'), os.path.expanduser('~/.claude/skills/token-zombie')]
    h = hashlib.sha256()
    for p in paths:
        fs = [p] if os.path.isfile(p) else sorted(os.path.join(r, f) for r, ds, n in os.walk(p) for f in n if '__pycache__' not in r)
        h.update(p.encode() + (b'' if os.path.exists(p) else b'MISSING'))
        for f in fs:
            try:
                h.update(f.encode() + open(f, 'rb').read())
            except OSError:
                h.update(f.encode() + b'UNREADABLE')
    return h.hexdigest()


def _git_snapshot(w):
    for c in (['init', '-q'], ['add', '-A'], ['-c', 'user.email=a@a', '-c', 'user.name=pf', 'commit', '-qm', 'snapshot']):
        subprocess.run(['git', '-C', w, *c], capture_output=True)


def _hooks(st, env=''):
    """TZ hooks from the plugin's hooks.json, state redirected to st (a temp HOME). Returns the settings file path."""
    import shlex
    d = json.load(open(os.path.join(Z, 'hooks', 'hooks.json')))['hooks']
    for gs in d.values():
        for g in gs:
            for x in g['hooks']:
                x['command'] = f'HOME={shlex.quote(st)} {env}' + x['command'].replace('${CLAUDE_PLUGIN_ROOT}', Z)
    p = os.path.join(st, 'settings.json')
    json.dump({'hooks': d}, open(p, 'w'))
    return p


def _stream(ev, name):
    p = os.path.join(ev, f'{name}.stream.jsonl')
    uses, final = [], ''
    try:
        for l in open(p):
            try:
                d = json.loads(l)
            except Exception:
                continue
            m = d.get('message') if isinstance(d.get('message'), dict) else {}
            for c in m.get('content') or []:
                if isinstance(c, dict) and c.get('type') == 'tool_use':
                    uses.append((c.get('name', ''), json.dumps(c.get('input') or {})))
            if d.get('type') == 'result':
                final = str(d.get('result') or '')
    except OSError:
        pass
    return uses, final


def _recall_check(ev, name, r, st, tools, forbid=None):
    """PASS only if: run ok, 0 denials, ONLY the scenario's tool was used, no call touched the recall store or state dir,
    and the model's answer holds a recall id that exists in st's recall store (the id exists only in the replaced output;
    fixtures are salted, and no shell/hash tool is available). INCONCLUSIVE = clean run but no trim happened."""
    import re
    res = _result_event(os.path.join(ev, f'{name}.stream.jsonl')) or {}
    denials = len(res.get('permission_denials') or [])
    uses, final = _stream(ev, name)
    rd = os.path.join(st, '.claude', 'token-zombie', 'recall')
    ids = {f[:-4] for f in os.listdir(rd) if f.endswith('.txt')} if os.path.isdir(rd) else set()
    other = sorted({n for n, _ in uses if n not in tools})
    leak = any('recall' in i or st in i for _, i in uses)
    said = set(re.findall(r'\b[0-9a-f]{10}\b', final)) & ids
    used = any(n in tools for n, _ in uses)
    d = (f"status {r['status']}, tokens {r['total']} [MEASURED], denials {denials}, tools {sorted({n for n, _ in uses}) or 'none'}, "
         f"trims {len(ids)}, model echoed recall id {bool(said)}" + (f", forbidden text seen {forbid in final}" if forbid else ''))
    if r['status'] != 'ok' or denials or other or leak or not used or (forbid and forbid in final):
        return 'FAIL', d + (f', other tools {other}' if other else '') + (', touched recall/state' if leak else '')
    if not ids:
        return 'INCONCLUSIVE', d + ', output was not trimmed'
    return ('PASS' if said else 'FAIL'), d


def _s1(ev, cfg, tmp, salt):
    import tzab
    w = tempfile.mkdtemp(prefix='tzsmoke-'); tmp.append(w)
    open(os.path.join(w, 'calc.py'), 'w').write('def add(a, b):\n    return a - b\n')
    open(os.path.join(w, 'test_calc.py'), 'w').write('import unittest\nfrom calc import add\n\n\nclass T(unittest.TestCase):\n'
                                                     '    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n')
    _git_snapshot(w)
    prompt = 'Fix add() in calc.py so it returns a + b. Do not edit test_calc.py. Then run: python3 -m unittest -q'
    r = tzab.run_session('S1', w, cfg, prompt, ev, model='haiku', cap=SCEN_CAP + 50_000, agg_cap=agg_cap())
    res = _result_event(os.path.join(ev, 'S1.stream.jsonl')) or {}
    denials = len(res.get('permission_denials') or [])
    ran = any('unittest' in i for n, i in _stream(ev, 'S1')[0])
    t = subprocess.run([sys.executable, '-m', 'unittest', '-q'], cwd=w, capture_output=True, text=True)
    untouched = subprocess.run(['git', '-C', w, 'diff', '--quiet', '--', 'test_calc.py']).returncode == 0
    ok = r['status'] == 'ok' and denials == 0 and (_changed(w) or 0) >= 1 and ran and t.returncode == 0 and untouched
    return ('PASS' if ok else 'FAIL'), (f"status {r['status']}, tokens {r['total']} [MEASURED], denials {denials}, files changed {_changed(w)}, "
                                        f"ran tests {ran}, acceptance {'PASS' if t.returncode == 0 else 'FAIL'}, test file untouched {untouched}")


def _s_recall(name, ev, cfg, tmp, salt, prompt, tools, allowed, extra=(), env='', setup=None, forbid=None):
    import tzab
    w = tempfile.mkdtemp(prefix='tzsmoke-'); st = tempfile.mkdtemp(prefix='tzsmoke-st-'); tmp += [w, st]
    os.makedirs(os.path.join(st, '.claude'))
    if setup:
        setup(w)
    extra = ['--settings', _hooks(st, env), '--tools', tools, *extra]
    r = tzab.run_session(name, w, cfg, prompt, ev, model='haiku', cap=SCEN_CAP, agg_cap=agg_cap(), extra=extra, allowed=allowed)
    return _recall_check(ev, name, r, st, allowed, forbid)


def _s2(ev, cfg, tmp, salt):
    big = lambda w: open(os.path.join(w, 'big.txt'), 'w').write(''.join(f'{i:05d} {salt} smoke fixture line\n' for i in range(2000)))
    return _s_recall('S2', ev, cfg, tmp, salt, 'Use the Read tool once on big.txt (whole file, no offset or limit). If the result ends '
                     'with a TOKEN ZOMBIE note that contains "tz recall <id>", reply with only that 10-character id. Otherwise reply NONE.',
                     'Read', ['Read'], setup=big)


def _s3(ev, cfg, tmp, salt):
    return _s_recall('S3', ev, cfg, tmp, salt, f'Use the WebFetch tool once on {WEB_URL} with the prompt "Return the first 3000 characters '
                     'verbatim". If the result contains a TOKEN ZOMBIE note with "tz recall <id>", reply with only that 10-character id. '
                     'Otherwise reply NONE.', 'WebFetch', ['WebFetch'], env='TZ_OUT_MAX=500 ')


def _s4(ev, cfg, tmp, salt):
    st_cfg = tempfile.mkdtemp(prefix='tzsmoke-'); tmp.append(st_cfg)
    mc = os.path.join(st_cfg, 'mcp.json')
    json.dump({'mcpServers': {'tzsmoke': {'command': sys.executable, 'args': [os.path.join(D, 'tzmcpfake.py')],
                                          'env': {'TZ_SMOKE_SALT': salt}}}}, open(mc, 'w'))
    return _s_recall('S4', ev, cfg, tmp, salt, 'Call the MCP tool mcp__tzsmoke__bigtext once. If its result contains a TOKEN ZOMBIE note with '
                     '"tz recall <id>", reply with that 10-character id. Then, if you can see a line starting with MIDDLE-CODEWORD, copy that '
                     'whole line; otherwise write NOCODE.', '', ['mcp__tzsmoke__bigtext'],
                     extra=['--mcp-config', mc, '--strict-mcp-config'], forbid=f'MIDDLE-CODEWORD-{salt}')


def smoke(evidence, yes=False):
    """Paid, capped S1-S4 through the real runner. Returns (ok, detail). S3 INCONCLUSIVE does not fail the run."""
    if not yes:
        return False, f'not run: spends real tokens (shared cap {agg_cap()}). Re-run with --yes after owner approval.'
    cfg = os.environ.get('TZ_AB_CONFIG')
    if not cfg:
        return False, 'TZ_AB_CONFIG unset'
    sys.path.insert(0, D)
    import secrets, tzab
    ev = os.path.join(evidence, 'smoke')
    os.makedirs(ev, exist_ok=True)
    salt, tmp, rows = secrets.token_hex(6), [], []
    before = live_sum()
    try:
        for name, fn in (('S1', _s1), ('S2', _s2), ('S3', _s3), ('S4', _s4)):
            if tzab.agg_used(ev) >= agg_cap():
                rows.append((name, 'FAIL', f'not started: shared cap {agg_cap()} reached')); break
            st, d = fn(ev, cfg, tmp, salt)
            rows.append((name, st, d))
            if st == 'FAIL':
                break
    except BaseException as e:  # Ctrl-C or a crash: still clean up and check live config below
        rows.append(('error', 'FAIL', f'{type(e).__name__}: {str(e)[:160]}'))
    finally:
        for d in tmp:  # retry: a just-killed child can still hold or recreate files for a moment (macOS/Windows runners)
            for _ in range(8):
                shutil.rmtree(d, ignore_errors=True)
                if not os.path.exists(d):
                    break
                time.sleep(0.25)
        live_ok = live_sum() == before
    used = tzab.agg_used(ev)
    st = {n: s for n, s, _ in rows}
    ok = live_ok and [n for n, _, _ in rows] == ['S1', 'S2', 'S3', 'S4'] and all(st[n] == 'PASS' for n in ('S1', 'S2', 'S4')) \
        and st['S3'] in ('PASS', 'INCONCLUSIVE')
    json.dump({'ok': ok, 'tokens': used, 'cap': agg_cap(), 'live_config_unchanged': live_ok, 'temp_removed': not any(os.path.exists(d) for d in tmp),
               'scenarios': [dict(name=n, status=s, detail=d) for n, s, d in rows]}, open(os.path.join(ev, 'smoke-summary.json'), 'w'), indent=1)
    lines = [f'{n} {s}: {d}' for n, s, d in rows] + [f'shared tokens {used} / cap {agg_cap()} [MEASURED]', f'live config unchanged {live_ok}']
    return ok, '\n    '.join(lines)


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='tz preflight')
    ap.add_argument('--evidence')
    ap.add_argument('--validate')
    ap.add_argument('--smoke', action='store_true')
    ap.add_argument('--yes', action='store_true')
    a = ap.parse_args(argv)
    if a.validate:
        arms = validate(a.validate)
        for arm, x in arms.items():
            print(f"  {arm:8} {'VALID' if x['valid'] else 'INVALID'}: status ok {x['status_ok']}, permission denials {x['denials']}, files changed {x['changed']}")
        ok = bool(arms) and all(x['valid'] for x in arms.values())
        print(f"run {'VALID' if ok else 'INVALID'}: {a.validate}" + ('' if arms else ' (no result files)'))
        return 0 if ok else 1
    R = offline(a.evidence)
    for n, ok, d in R:
        print(f"  {'PASS' if ok else 'FAIL'} {n}: {d}")
    ready = all(ok for _, ok, _ in R)
    if a.smoke:
        ok, d = smoke(a.evidence or tempfile.mkdtemp(prefix='tzpf-ev-'), a.yes)
        print(f"  {'PASS' if ok else 'FAIL'} smoke run: {d}")
        ready = ready and ok
    else:
        print('  TODO smoke run: `tz preflight --smoke --yes` (paid, capped) must PASS before a paid A/B run')
        ready = False
    print('READY for paid A/B' if ready else 'NOT READY for paid A/B')
    return 0 if ready else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
