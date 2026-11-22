#!/usr/bin/env python3
# Model routing ADVISOR. Honest: tz cannot switch the main model of a running chat; it advises the model for the next task / subagents,
# honours override (--model or env TZ_MODEL), and logs every decision to ~/.claude/token-zombie/routing.jsonl.
import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tzopt
# EST relative cost per 1M output tokens (USD, list-price ballpark, labelled EST, edit as prices change)
COST = {'haiku': 1.0, 'sonnet': 3.0, 'opus': 15.0}
# per-mode work limits (advice): reads before acting, subagents worth starting
WORK = {'QUICK': 'reads <=2, no subagents', 'STANDARD': 'reads <=5 (grep/line ranges), no subagents',
        'RESEARCH': 'subagent haiku for bulk reading, main reads summaries only', 'ENGINEERING': 'read the touched files first, <=2 subagents (sonnet)',
        'AUDIT': '1 reviewer subagent (sonnet) + tz security', 'CREATIVE': 'reads <=3, no subagents'}
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


RULES = '''<!-- TZ-MODEL-RULES -->
# Model choice per task (written by `tz route --write`, advice for Claude, edit freely)
- Pick the cheapest model that can do the task; say which one you use and why in one line.
- haiku: bulk reading, grep/summaries, lists, renames, one-line fixes (use as a subagent: Agent tool `model: "haiku"`).
- sonnet: normal implementation, debugging, tests, reviews, multi-file edits. Default for the main chat.
- opus: architecture, security-sensitive work, hard bugs after sonnet failed twice, large refactors.
- Do not start a subagent when a few direct reads answer it. Never change the model of the running chat yourself: if the task needs a different model, tell the user to run `/model <name>` and wait.
- One task per chat; when a task is done say so and suggest a fresh chat (tz compact / tz handoff first).
<!-- /TZ-MODEL-RULES -->
'''


def write_rules(path):
    """Insert or replace the marked block in path (created if missing). Nothing outside the markers is touched."""
    old = open(path, encoding='utf-8').read() if os.path.exists(path) else ''
    a, b = old.find('<!-- TZ-MODEL-RULES -->'), old.find('<!-- /TZ-MODEL-RULES -->')
    new = (old[:a] + RULES.rstrip('\n') + old[b + len('<!-- /TZ-MODEL-RULES -->'):]) if a >= 0 and b > a else (old.rstrip('\n') + ('\n\n' if old else '') + RULES)
    open(path, 'w', encoding='utf-8').write(new)


def main(argv):
    if '--write' in argv:
        i = argv.index('--write'); tgt = argv[i + 1] if len(argv) > i + 1 and not argv[i + 1].startswith('--') else 'CLAUDE.md'
        if '--yes' not in argv:
            print(RULES + f'\nDry run. Add --yes to write this block into {os.path.abspath(tgt)} (only between its markers).'); return 0
        write_rules(tgt); print(f'wrote model rules block into {os.path.abspath(tgt)}'); return 0
    model = None
    if '--model' in argv:
        i = argv.index('--model')
        model = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    r = route(' '.join(argv), model)
    print(f"route: model {r['model']} ({r['source']}) mode {r['mode']} complexity {r['complexity']}/5 [EST]"
          f"{', subagents: ' + r['subagent_model'] if r['subagent_model'] else ''}; ~${r['cost_per_mtok_est']}/Mtok out [EST]")
    from tzlib import PACKS
    packs = [p for p, rx in PACKS.items() if re.search(rx, ' '.join(argv).lower())]
    print(f"work: {WORK.get(r['mode'], '-')}; skills: " + (', '.join(f'skillpack on {p}' for p in packs) + ' (off when done)' if packs else 'none needed (specialist skills on demand)'))
    from tzusage import find_transcript
    import tzcont
    m = tzcont.measure(find_transcript(os.getcwd()))
    if m:
        e = tzcont.econ(m, time.time() - m['t'])
        print(f"session: next 10 turns {' | '.join(f'{x} ${e[10][x][1]:.2f}' for x in ('continue', 'compact', 'fresh'))} -> {tzcont.best(e)} "
              '[EST API-equivalent; details: tz stats]')
    print(f"PRESS/TYPE: /model {r['model']}   (switch the main chat yourself; tz cannot). Subagents: model {r['subagent_model'] or r['model']}.")
    print('note: advice only; switch with /model yourself, tz cannot change the running chat model')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
