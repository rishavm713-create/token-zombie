#!/usr/bin/env python3
# Model routing ADVISOR. Honest: tz cannot switch the main model of a running chat; it advises the model for the next task / subagents,
# honours override (--model or env TZ_MODEL), and logs every decision to ~/.claude/token-zombie/routing.jsonl.
import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tzopt
# EST relative cost per 1M output tokens (USD, list-price ballpark, labelled EST, edit as prices change)
COST = {'haiku': 1.0, 'sonnet': 3.0, 'opus': 15.0}
SIG = [(r'architect|race condition|security|migrat|design system|refactor', 3), (r'debug|implement|build|test|integrat', 2), (r'multi|several|all |across|entire', 2),
       (r'typo|rename|one line|list|count|show', -2)]


def complexity(prompt):
    p = prompt.lower()
    sc = 1 + sum(w for rx, w in SIG if re.search(rx, p)) + (2 if len(p) > 600 else 1 if len(p) > 200 else 0)
    return max(1, min(5, sc))


def route(prompt, override=None):
    override = override or os.environ.get('TZ_MODEL')
    mode, advice, sub = tzopt.classify(prompt)
    c = complexity(prompt)
    model = 'haiku' if c <= 1 else 'sonnet' if c <= 4 else 'opus'
    src = 'rule'
    if override:
        model, src = override.lower(), 'override'
    r = dict(ts=int(time.time()), mode=mode, complexity=c, model=model, source=src, subagent_model='haiku' if sub else None,
             cost_per_mtok_est=COST.get(model), basis='EST keyword heuristic; cannot switch the running chat model', advice=advice)
    try:
        d = os.path.expanduser('~/.claude/token-zombie')
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, 'routing.jsonl'), 'a').write(json.dumps(r) + '\n')
    except OSError:
        pass
    return r


def main(argv):
    model = None
    if '--model' in argv:
        i = argv.index('--model')
        model = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    r = route(' '.join(argv), model)
    print(f"route: model {r['model']} ({r['source']}) mode {r['mode']} complexity {r['complexity']}/5 [EST]"
          f"{', subagents: ' + r['subagent_model'] if r['subagent_model'] else ''}; ~${r['cost_per_mtok_est']}/Mtok out [EST]")
    print('note: advice only; switch with /model yourself, tz cannot change the running chat model')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
