#!/usr/bin/env python3
# tz A/B session runner with hard token caps. Runs ONE headless Claude Code session (claude -p, stream-json), sums real usage per reply,
# and kills the process the moment the per-session cap or the remaining aggregate cap is reached. Raw stream is kept as evidence.
# Total tokens = input + output + cache_read + cache_write (cached tokens are NOT treated as free). Never reads credentials or live settings:
# the session uses only the CLAUDE_CONFIG_DIR you give it.
import json, os, subprocess, sys, time

SESSION_CAP, AGG_CAP = 1_500_000, 5_000_000
LEAKY_PREFIXES = ('ANTHROPIC_', 'CLAUDE')  # host/provider env: tokens, gateway URL, desktop session ids



def _launcher(prog):
    """Windows: find claude.cmd/.exe via PATHEXT; run a Python shebang script (fake/test claude) with this Python."""
    if os.name != 'nt':
        return [prog]
    import shutil
    p = shutil.which(prog) or prog
    try:
        with open(p, 'rb') as f:
            if b'python' in f.readline():
                return [sys.executable, p]
    except OSError:
        pass
    return [p]
def usage_total(u):
    return sum((u.get(k) or 0) for k in ('input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens'))


def agg_recorded(ev):
    try:
        return json.load(open(os.path.join(ev, 'aggregate.json')))['total']
    except Exception:
        return 0


def agg_used(ev):
    """Recorded aggregate + tokens of runs that never finished (killed runner: partial file without result file). Never undercounts."""
    try:
        n = json.load(open(os.path.join(ev, 'aggregate.json')))['total']
    except Exception:
        n = 0
    try:
        for f in os.listdir(ev):
            if f.endswith('.partial.json') and not os.path.exists(os.path.join(ev, f.replace('.partial.json', '.result.json'))):
                n += json.load(open(os.path.join(ev, f))).get('total', 0)
    except Exception:
        pass
    return n


def run_session(name, cwd, cfg, prompt, evidence, model='sonnet', cap=SESSION_CAP, agg_cap=AGG_CAP, extra=(), claude=None, allowed=None):
    """Returns dict(status, total, parts, path). status: ok | cap-session | cap-aggregate | refused-aggregate | error."""
    os.makedirs(evidence, exist_ok=True)
    used = agg_used(evidence)
    if used >= min(agg_cap, AGG_CAP):
        return dict(status='refused-aggregate', total=0, aggregate=used, path=None)
    cap, agg_cap = min(cap, SESSION_CAP), min(agg_cap, AGG_CAP)  # the hard caps cannot be raised by a flag
    limit = min(cap, agg_cap - used)
    why = 'cap-session' if cap <= agg_cap - used else 'cap-aggregate'
    claude = claude or os.environ.get('TZ_AB_CLAUDE') or 'claude'
    # inherited provider env (desktop app token, gateway URL) overrides the isolated login and caused '401 Invalid bearer token'
    env = {k: v for k, v in os.environ.items() if not k.startswith(LEAKY_PREFIXES)}
    env['CLAUDE_CONFIG_DIR'] = cfg
    path = os.path.join(evidence, f'{name}.stream.jsonl')
    parts = dict(input_tokens=0, output_tokens=0, cache_read_input_tokens=0, cache_creation_input_tokens=0)
    seen, total, status = {}, 0, 'ok'
    own_partial_old = os.path.join(evidence, f'{name}.partial.json')
    if os.path.exists(own_partial_old):  # re-run of an interrupted name: its old partial is already inside `used`; keep it as recorded spend
        json.dump({'total': agg_recorded(evidence) + json.load(open(own_partial_old)).get('total', 0)}, open(os.path.join(evidence, 'aggregate.json'), 'w'))
        os.remove(own_partial_old)
    # headless runs cannot answer permission prompts: allow edits in the fixture copy and only the commands the tasks need
    perms = ['--permission-mode', 'acceptEdits', '--allowedTools', 'Bash(python3:*)', 'Bash(python:*)', 'Bash(pytest:*)', 'Bash(git diff:*)', 'Bash(git status:*)', 'Bash(ls:*)']
    if allowed is not None:  # smoke S2-S4: only the scenario's own tool is pre-approved (no Bash)
        perms = ['--permission-mode', 'acceptEdits', '--allowedTools', *allowed]
    cmd = [*_launcher(claude), '-p', prompt, '--model', model, '--output-format', 'stream-json', '--verbose', *perms, *extra]
    pr = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    import threading
    wall = threading.Timer(int(os.environ.get('TZ_AB_WALL_SECONDS') or 3600), pr.kill)  # silent hang cannot run forever
    wall.daemon = True
    wall.start()
    partial = os.path.join(evidence, f'{name}.partial.json')
    try:
        with open(path, 'w') as raw:
            for line in pr.stdout:
                raw.write(line)
                raw.flush()
                try:
                    m = json.loads(line).get('message') or {}
                except Exception:
                    continue
                u = m.get('usage') if isinstance(m, dict) else None  # some events carry message as plain text
                if isinstance(u, dict) and m.get('id'):
                    seen[m['id']] = u  # last usage per reply id wins (streamed replies repeat)
                    total = sum(usage_total(x) for x in seen.values())
                    json.dump({'total': total}, open(partial, 'w'))  # survives a killed runner
                    if total >= limit:
                        status = why
                        pr.kill()
                        break
    except BaseException:  # Ctrl-C / SIGTERM of the runner: stop the paid child, keep the count, re-raise
        pr.kill()
        raise
    finally:
        wall.cancel()
    try:
        pr.wait(timeout=10)
    except Exception:
        pr.kill()
    for u in seen.values():
        for k in parts:
            parts[k] += u.get(k) or 0
    if status == 'ok' and pr.returncode not in (0, None):
        status = 'error'
    agg = agg_recorded(evidence) + total  # orphan partials stay counted via their own files, never folded in twice
    json.dump({'total': agg, 'last': name, 'time': time.strftime('%F %T')}, open(os.path.join(evidence, 'aggregate.json'), 'w'))
    res = dict(status=status, total=total, parts=parts, non_cache=parts['input_tokens'] + parts['output_tokens'] + parts['cache_creation_input_tokens'],
               aggregate=agg, path=path, returncode=pr.returncode)
    json.dump(res, open(os.path.join(evidence, f'{name}.result.json'), 'w'), indent=1)
    if os.path.exists(partial):
        os.remove(partial)
    return res


def plan(argv):
    """Free dry run of a paid A/B: trial matrix + worst-case token bill (runs nothing, no model call). The owner OKs the cost before any tzab run."""
    import argparse
    ap = argparse.ArgumentParser(prog='tzab plan')
    ap.add_argument('--tasks', type=int, default=1); ap.add_argument('--trials', type=int, default=5)
    ap.add_argument('--cap', type=int, default=SESSION_CAP); ap.add_argument('--agg-cap', type=int, default=AGG_CAP)
    ap.add_argument('--usd-per-mtok', type=float, default=None, help='your blended $/1M tokens (EST; none given = tokens only)')
    a = ap.parse_args(argv)
    runs = a.tasks * a.trials * 2  # control + treatment, alternating order
    worst = min(runs * a.cap, a.agg_cap)
    order = [('control' if (i % 2 == 0) else 'tz') for i in range(a.trials * 2)]
    r = dict(sessions=runs, arms=['control (no tz)', 'treatment (tz, separate CLAUDE_CONFIG_DIR)'], order_per_task=order, per_session_cap=a.cap,
             aggregate_cap=a.agg_cap, worst_case_tokens=worst, label='worst case = hard caps, NOT a prediction; real use is usually far below',
             worst_case_usd=round(worst / 1e6 * a.usd_per_mtok, 2) if a.usd_per_mtok else None,
             runs_enough=runs >= 10 * a.tasks, needs_owner_ok=True,
             next='tz bench quality TRIALS.json after the runs (verdict PROVEN needs 5+ trials per arm, no pass-rate drop)')
    print(json.dumps(r, indent=1))
    return 0


def main(argv):
    import argparse
    if argv[:1] == ['plan']:
        return plan(argv[1:])
    ap = argparse.ArgumentParser(prog='tzab')
    ap.add_argument('--name', required=True); ap.add_argument('--cwd', required=True); ap.add_argument('--config', required=True)
    ap.add_argument('--prompt-file', required=True); ap.add_argument('--evidence', required=True)
    ap.add_argument('--extra-settings'); ap.add_argument('--resume'); ap.add_argument('--model', default='sonnet'); ap.add_argument('--cap', type=int, default=SESSION_CAP); ap.add_argument('--agg-cap', type=int, default=AGG_CAP)
    a = ap.parse_args(argv)
    extra = (['--settings', a.extra_settings] if a.extra_settings else []) + (['--resume', a.resume] if a.resume else [])
    r = run_session(a.name, a.cwd, a.config, open(a.prompt_file).read(), a.evidence, a.model, a.cap, a.agg_cap, extra)
    print(json.dumps(r))
    return 0 if r['status'] == 'ok' else 3


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
