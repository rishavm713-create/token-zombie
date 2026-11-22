"""tz systems [--json] [--session S]: one view per intelligence system from state files only (no transcript scan, no model call).
Each system: happening / did / impact / evidence / status (MEASURED, EST, UNKNOWN, UNSUPPORTED). Writes systems.json for the panel."""
import collections, glob, json, os, sys, time
from tzopt import STATE, _load


def _j(n, d):
    v = _load(os.path.join(STATE, n), d)
    return v if isinstance(v, type(d)) else d


def build(sid=None, now=None):
    now = now or time.time()
    ch = sorted(glob.glob(os.path.join(STATE, 'churn-*.json')), key=os.path.getmtime)
    sid = sid or (os.path.basename(ch[-1])[6:-5] if ch else '')
    c = _load(os.path.join(STATE, f'churn-{sid}.json'), {}) if sid else {}
    c = c if isinstance(c, dict) else {}
    L = [e for e in _j('ledger.json', []) if isinstance(e, dict)]
    kt = collections.defaultdict(lambda: [0, 0])
    for e in L:
        k = kt[e.get('kind', '?')]
        k[0] += 1
        k[1] += e.get('tok', 0)
    ov = sum(v[1] for k, v in kt.items() if k.startswith('overhead'))
    sv = sum(v[1] for k, v in kt.items() if not k.startswith('overhead'))
    fr, st, ag = _j('fresh.json', {}), _j('status.json', {}), _j('agents.json', {})
    ec = _j('econ.json', {}).get('now')
    caps = collections.Counter()
    try:
        for l in open(os.path.join(STATE, 'caps.jsonl')).read().splitlines()[-500:]:
            caps[json.loads(l).get('act', '?')] += 1
    except (OSError, ValueError):
        pass
    roi, cmp_ = [], {}
    try:  # agent ROI + last compaction verdict (live ledger, subagent transcripts)
        import tzlive
        roi = tzlive.roi(sid) if sid else []
        cmp_ = ((tzlive._load(tzlive.path(sid)).get('compact') or [{}])[-1]) if sid else {}
    except Exception:
        pass
    code, fails = c.get('code') or {}, c.get('fails') or {}
    S = lambda **k: k
    sy = {
        'resource': S(happening=f"saved {sv:,} tok, TZ overhead {ov:,} tok" + (f"; net {sv - ov:,}" if sv else ''),
                      did='trimmed tool output, rtk cuts; overhead logged per hook', impact=f"net {sv - ov:,} tok",
                      evidence='ledger.json (kind, tok, src per entry)', status='MEASURED',
                      est=(f"fresh-chat saving ~{fr.get('tok', 0):,} tok (EST, never added to net)" if fr else 'no fresh-chat estimate'),
                      projection=(f"10 turns: stay ${ec['continue']} compact ${ec['compact']} fresh ${ec['fresh']} -> {ec['best']} (EST)" if ec else 'UNKNOWN: run tz stats')),
        'context': S(happening=f"{kt['output-trim'][0]} outputs trimmed, {len(glob.glob(os.path.join(STATE, 'recall', '*.txt')))} recoverable",
                     did='trim big outputs, spill original', impact=f"{kt['output-trim'][1]:,} tok", evidence='ledger.json output-trim; recall/ spill files',
                     status='MEASURED', action='tz recall <id> | tz recall --search "<words>"'),
        'zombie': S(happening=f"{sum(fails.values()) if all(isinstance(x, int) for x in fails.values()) else len(fails)} failing-call counters, {len(c.get('said') or {})} signals raised",
                    did='circuit breaker, file guard, churn advice (advice only)', impact='UNKNOWN: advice not tied to a measured saving',
                    evidence=f'churn-{sid[:8]}.json fails/said; claims.json', status='MEASURED counts'),
        'infection': S(happening=f"{sum(caps.values())} capability events: " + ', '.join(f'{k} {v}' for k, v in caps.most_common(4)),
                       did='optional packs off by default, on for a task, off at end', impact='UNKNOWN: not priced',
                       evidence='caps.jsonl; tz capabilities', status='MEASURED counts; loaded files via InstructionsLoaded hook (live ledger instr)',
                       action='tz capabilities'),
        'agents': S(happening=f"{ag.get('running', '?')} running of {ag.get('total', '?')}", did='reads host agent list; per-agent cost vs outcome (tz live roi)',
                    impact=(f"{len(roi)} agents ~${sum(x['usd'] or 0 for x in roi):.2f} EST, flagged {sum(1 for x in roi if x['flags'])}" if roi else 'UNKNOWN: no agent cost this session'),
                    evidence=f"agents.json ({ag.get('src', 'none')})", status='MEASURED snapshot; agents tracked by exact agent_id via SubagentStart/Stop',
                    action='tz live agents'),
        'survival': S(happening=f"ctx {st.get('ctx_pct', '?')}%, level {st.get('level', '?')}, risk {st.get('risk', '?')}",
                      did='warns, compares stay/compact/fresh by projected cost; checks the compaction summary against the continuation note',
                      impact=(f"last compaction: {cmp_['verdict']}" + (f" ({cmp_['hit']}/{cmp_['of']} key facts kept)" if cmp_.get('of') else '') if cmp_.get('verdict') else 'UNKNOWN: no compaction seen'), evidence='status.json; econ.json', status='MEASURED ctx, EST cost',
                      action='tz status'),
        'continuity': S(happening=f"{st.get('open_tasks', '?')} open tasks; STATE.md " + ('present' if os.path.exists(os.path.join(st.get('cwd', ''), 'handoffs', 'STATE.md')) else 'absent'),
                        did='STATE.md, task pack, verified checkpoint', impact='UNKNOWN', evidence='status.json; handoffs/STATE.md', status='MEASURED',
                        action='tz state | tz resume'),
        'quality': S(happening=(f"{code.get('edits', 0)} code edits, {code.get('runs', 0)} test runs, last {code.get('last', 'none')}, {code.get('unt', 0)} untested"),
                     did='untested-edit advice at Stop', impact='UNKNOWN', evidence=f'churn-{sid[:8]}.json code; pass/fail read from output text',
                     status='MEASURED counts, heuristic result'),
    }
    out = {'ts': int(now), 'session': sid, 'systems': sy}
    try:
        os.makedirs(STATE, exist_ok=True)
        open(os.path.join(STATE, 'systems.json.tmp'), 'w').write(json.dumps(out))
        os.replace(os.path.join(STATE, 'systems.json.tmp'), os.path.join(STATE, 'systems.json'))
    except OSError:
        pass
    return out


def main(argv):
    sid = argv[argv.index('--session') + 1] if '--session' in argv else None
    o = build(sid)
    if '--json' in argv:
        print(json.dumps(o, indent=1))
        return 0
    for k, v in o['systems'].items():
        print(f"{k.upper():11} {v['happening']} [{v['status']}]")
        for f in ('est', 'projection', 'action'):
            if v.get(f):
                print(f"{'':11}   {f}: {v[f]}")
    return 0
