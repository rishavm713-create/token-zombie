#!/usr/bin/env python3
# tz bench: reproducible before/after on a synthetic project in a temp fake HOME. Real bytes are MEASURED; anything that depends on
# the model obeying advice is EST; what the platform controls (startup system prompt, provider cache) is UNKNOWN. tok = chars/4 (est conversion).
import json, os, subprocess, sys, tempfile, time
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import tzhandoff, tzopt

ET = lambda c: c // 4


def hook_ms(script, payload, env):
    t = time.perf_counter()
    r = subprocess.run([sys.executable, os.path.join(D, script)], input=json.dumps(payload), capture_output=True, text=True, env=env, timeout=10)
    return (time.perf_counter() - t) * 1000, len(r.stdout)


def run(reads=5, size=20000, noise_lines=500, chat_tokens=100000):
    T = tempfile.mkdtemp(prefix='tzbench-')
    H = os.path.join(T, 'home'); P = os.path.join(T, 'proj'); os.makedirs(H + '/.claude'); os.makedirs(P)
    env = dict(os.environ, HOME=H)
    os.environ['HOME'] = H
    tzopt.STATE = os.path.join(H, '.claude/token-zombie')
    f = os.path.join(P, 'big.py'); open(f, 'w').write(('x = 1  # filler line\n' * (size // 21 + 1))[:size])
    subprocess.run(['git', '-C', P, 'init', '-q'], capture_output=True)
    R = {}
    # A. repeated reads of an unchanged file. baseline: all reads return the file. tz: advice text added; saving only if the model obeys.
    adv = [tzopt.read_advice('b', f) for _ in range(reads)]
    advice_chars = sum(len(a) for a in adv)
    R['dup_read'] = dict(baseline=reads * size, flagged=sum(bool(a) for a in adv), advice_chars=advice_chars,
                         saving_if_obeyed=(reads - 1) * size - advice_chars, basis='EST (needs model to skip re-reads); advice size MEASURED')
    # B. noisy command output through the filter: bytes really removed
    noisy = '\n'.join(['compiling module ok'] * (noise_lines - 10) + [f'step {i}' for i in range(9)] + ['ERROR boom'])
    out, b, a = tzopt.filter_output(noisy, 40)
    R['filter'] = dict(before=b, after=a, saved=b - a, kept_error='ERROR boom' in out, basis='MEASURED bytes (applies only when output is routed through tz filter/rtk)')
    # C. continuity: resume text vs carrying the chat. chat size is a PARAMETER (tokens), not measured.
    tzhandoff.handoff(P, 'bench', ['a'], ['b'], 'do b', facts=['stable fact'])
    txt, _ = tzhandoff.resume(P)
    R['resume'] = dict(resume_chars=len(txt), resume_tok=ET(len(txt)), carried_chat_tok=chat_tokens, saved_tok=chat_tokens - ET(len(txt)),
                       basis='resume size MEASURED; carried_chat_tok is an ASSUMED input (--chat-tokens), and quality of resumed work is UNKNOWN')
    # D. overhead + hook latency (measured): run guard/start hooks the way Claude would
    ms, ch = [], 0
    for s, pl in (('tz-guard.py', {'hook_event_name': 'PreToolUse', 'session_id': 'b2', 'tool_input': {'file_path': f}}),
                  ('tz-guard.py', {'hook_event_name': 'UserPromptSubmit', 'session_id': 'b2', 'prompt': 'hello'}),
                  ('tz-start.py', {'cwd': P})):
        m, c = hook_ms(s, pl, env); ms.append(m); ch += c
    R['overhead'] = dict(hook_chars=ch, hook_tok=ET(ch), advice_tok=ET(advice_chars), resume_tok=R['resume']['resume_tok'],
                         hook_ms_max=round(max(ms)), basis='MEASURED')
    R['unknown'] = ['platform startup context (system prompt/tools): not changeable by tz', 'provider cache read/write effect', 'answer quality after resume']
    gross = R['filter']['saved'] // 4 + R['resume']['saved_tok']
    R['net'] = dict(measured_only_tok=ET(R['filter']['saved']) - R['overhead']['hook_tok'],
                    with_estimates_tok=gross + ET(R['dup_read']['saving_if_obeyed']) - R['overhead']['hook_tok'] - R['overhead']['advice_tok'] * 0)
    return R


def trial(path):
    """Real numbers from one chat log (MEASURED): tokens by kind, tool calls, repeated reads/commands."""
    import tzusage
    t = tzusage.totals(path)
    calls = sum(l.count('"type":"tool_use"') + l.count('"type": "tool_use"') for l in open(path, errors='ignore')) if os.path.isfile(path) else 0
    a = tzopt.analyze(path)
    return dict(inp=t['inp'], out=t['out'], cr=t['cr'], cw=t['cw'], turns=t['turns'], calls=calls,
                dup_reads=len(a['dup_reads']), dup_cmds=len(a['dup_cmds']), work=t['inp'] + t['out'] + t['cw'], all=t['inp'] + t['out'] + t['cw'] + t['cr'])


def compare(base, opt, base_ok, opt_ok, overhead_tok=None):
    """Net savings from real A/B logs (lists = repeated trials, mean used). Savings count only if BOTH runs passed the same quality check."""
    B, O = [trial(p) for p in base], [trial(p) for p in opt]
    mean = lambda L, k: sum(x[k] for x in L) / len(L)
    ov = overhead_tok or 0  # ONLY cost that never appears in a transcript (e.g. extra tokens spent outside the chat). Hook text, handoff, resume and startup context are already inside the optimized log's totals: subtracting the ledger too would count them twice.
    r = dict(trials=(len(B), len(O)), comparable=bool(base_ok and opt_ok), overhead_tok=ov, rows={})
    for k in ('work', 'all', 'out', 'calls', 'dup_reads', 'dup_cmds'):
        b, o = mean(B, k), mean(O, k)
        net = b - (o + (ov if k in ('work', 'all') else 0))
        r['rows'][k] = dict(baseline=b, optimized=o, net=net, pct=round(100 * net / b, 1) if b else None)
    return r


def main(argv):
    if argv and argv[0] == 'results':
        import tzdash
        rs = tzdash.bench_results(argv[1] if len(argv) > 1 else None)
        for f, t, st in rs:
            print(f'{f}: total {t} tokens status {st} [MEASURED]')
        print(f'{len(rs)} evidence files' if rs else 'no A/B evidence found: UNKNOWN (experiment not run)')
        return 0
    if argv and argv[0] == 'compare':
        import argparse
        ap = argparse.ArgumentParser(prog='tz bench compare')
        ap.add_argument('cmd')
        ap.add_argument('--baseline', action='append', required=True, help='chat log of a run WITHOUT tz (repeat for trials)')
        ap.add_argument('--optimized', action='append', required=True, help='chat log of the same task WITH tz')
        ap.add_argument('--both-passed', action='store_true', help='you verified both runs pass the same acceptance test')
        ap.add_argument('--overhead-tok', type=int, help='tokens spent by tz OUTSIDE the transcripts (default 0)')
        a = ap.parse_args(argv)
        for p in a.baseline + a.optimized:
            if not os.path.isfile(p):
                print(f'tz bench compare: no such log {p}', file=sys.stderr); return 2
        r = compare(a.baseline, a.optimized, a.both_passed, a.both_passed, a.overhead_tok)
        print(f"trials baseline {r['trials'][0]} / optimized {r['trials'][1]} | extra overhead outside transcripts {r['overhead_tok']} tok (hook/handoff/resume/startup text is already INSIDE the optimized log totals, not subtracted again)")
        for k, v in r['rows'].items():
            print(f"  {k:9} baseline {v['baseline']:.0f} optimized {v['optimized']:.0f} net {v['net']:.0f}" + (f" ({v['pct']}%)" if v['pct'] is not None else '') + ' [MEASURED]')
        if not r['comparable']:
            print('NOT COMPARABLE: quality of both runs not confirmed (--both-passed). Lower tokens may just mean less work; no savings claimed.')
        else:
            print(f"VERDICT: net {'POSITIVE' if r['rows']['work']['net'] > 0 else 'NOT positive'} on work tokens (input+output+cache_write); 'all' adds cache reads. Few trials = anecdote, not proof.")
        return 0

    return main_synth(argv)


def main_synth(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='tz bench')
    ap.add_argument('--chat-tokens', type=int, default=100000, help='assumed size of the chat a handoff replaces')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    R = run(chat_tokens=a.chat_tokens)
    if a.json:
        print(json.dumps(R, indent=1)); return 0
    d, f, r, o, n = R['dup_read'], R['filter'], R['resume'], R['overhead'], R['net']
    print(f"A dup reads   baseline {d['baseline']} chars -> if obeyed saves {d['saving_if_obeyed']} chars (~{ET(d['saving_if_obeyed'])} tok) [EST]; advice cost {d['advice_chars']} chars [MEASURED]")
    print(f"B filter      {f['before']} -> {f['after']} chars = -{100 * f['saved'] // max(1, f['before'])}% [MEASURED], error line kept: {f['kept_error']}")
    print(f"C resume      {r['resume_tok']} tok vs carrying {r['carried_chat_tok']} tok [assumed chat size] -> saves {r['saved_tok']} tok [EST: depends on assumption]")
    print(f"D overhead    hooks {o['hook_tok']} tok emitted, resume {o['resume_tok']} tok, slowest hook {o['hook_ms_max']} ms [MEASURED]")
    print(f"NET           measured-only {n['measured_only_tok']} tok | incl. estimates {n['with_estimates_tok']} tok")
    print('UNKNOWN       ' + '; '.join(R['unknown']))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
