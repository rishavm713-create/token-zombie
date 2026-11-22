#!/usr/bin/env python3
# `tz rework [TRANSCRIPT] [--json]`: rework / loop signals counted from a chat log. All MEASURED counts, no token claims, no network.
# Signals: tool calls that errored; the same call (tool+input) repeated; the same failing call repeated (retry loop); files edited 3+ times;
# test-like Bash commands that failed and later passed (fail->pass cycles). Counts show where work was repeated, not that it was wasted.
import json, os, re, sys, collections

TEST = re.compile(r'\b(pytest|unittest|npm (run )?test|yarn test|go test|cargo test|make test|bash tests/|jest|vitest)\b')


def score(calls, errored, repeated, fail_sig, edits):
    """Rework score 0-100 (0 = none), a transparent weighted ratio of MEASURED counts, not a quality or saving claim:
    errored 40%, identical repeats 30%, retry-loop calls 20%, calls spent re-editing files 3+ times 10%."""
    if not calls:
        return 0
    loops = sum(v for v in fail_sig.values() if v >= 3)
    reedit = sum(v for v in edits.values() if v >= 3)
    return round(100 * min(1, 0.4 * errored / calls + 0.3 * repeated / calls + 0.2 * loops / calls + 0.1 * reedit / calls))


def analyse(path):
    calls, res = {}, {}
    order = []
    try:
        for ln in open(path, errors='replace'):
            try:
                d = json.loads(ln)
            except Exception:
                continue  # partial / bad line
            c = (d.get('message') or {}).get('content')
            if not isinstance(c, list):
                continue
            for b in c:
                if not isinstance(b, dict):
                    continue
                if b.get('type') == 'tool_use':
                    calls[b.get('id')] = (b.get('name', ''), json.dumps(b.get('input', {}), sort_keys=True)[:400], b.get('input', {}))
                    order.append(b.get('id'))
                elif b.get('type') == 'tool_result':
                    res[b.get('tool_use_id')] = bool(b.get('is_error'))
    except OSError:
        return None
    sig, fail_sig, edits, tests = collections.Counter(), collections.Counter(), collections.Counter(), []
    errors = 0
    for i in order:
        name, key, inp = calls[i]
        err = res.get(i, False)
        sig[(name, key)] += 1
        if err:
            errors += 1
            fail_sig[(name, key)] += 1
        if name in ('Edit', 'Write', 'MultiEdit') and inp.get('file_path'):
            edits[inp['file_path']] += 1
        if name == 'Bash' and TEST.search(str(inp.get('command', ''))) and i in res:
            tests.append(not err)
    cycles = sum(1 for a, b in zip(tests, tests[1:]) if (not a) and b)
    top = lambda c, n=1: [(k[0] if isinstance(k, tuple) else k, v) for k, v in c.most_common() if v > n][:5]
    return dict(calls=len(order), errored=errors, repeated_calls=sum(v - 1 for v in sig.values() if v > 1),
                retry_loops=[(k[0], v) for k, v in fail_sig.most_common() if v >= 3][:5],
                files_edited_3plus=[(os.path.basename(k), v) for k, v in edits.most_common() if v >= 3][:5],
                test_runs=len(tests), test_fail_then_pass=cycles, basis='MEASURED counts from the chat log',
                rework_score=score(len(order), errors, sum(v - 1 for v in sig.values() if v > 1), fail_sig, edits))


def main(argv):
    js = '--json' in argv
    a = [x for x in argv if not x.startswith('--')]
    p = a[0] if a else None
    if not p:
        import tzusage
        p = tzusage.find_transcript(os.getcwd())
    r = analyse(p) if p else None
    if r is None:
        print('tz rework: no chat log found (UNAVAILABLE)'); return 1
    if js:
        print(json.dumps(r, indent=1)); return 0
    print(f"rework signals [MEASURED] {os.path.basename(p)}: {r['calls']} calls, {r['errored']} errored, {r['repeated_calls']} repeated identical calls")
    print(f"  retry loops (same failing call 3+): {r['retry_loops'] or 'none'}")
    print(f"  files edited 3+ times: {r['files_edited_3plus'] or 'none'}")
    print(f"  rework score {r['rework_score']}/100 (weighted ratio of the counts above; 0 = none; not a quality claim)")
    print(f"  test runs {r['test_runs']}, fail->pass cycles {r['test_fail_then_pass']}")
    if r['rework_score'] >= 30 or r['retry_loops']:
        print('  ADVICE: churn is high; save state now (tz checkpoint) and consider a fresh chat for the next task. Advice only.')
    print('  these are repeat counts, not proven waste; quality-adjusted savings need an A/B run (tz bench compare).')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
