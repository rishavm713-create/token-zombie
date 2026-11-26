#!/usr/bin/env python3
# Token-zombie guard: task limit, not number limit. Big chat never stops a task; it moves the rest to a fresh session.
# UserPromptSubmit: from LIMIT growth, each new prompt gets "finish task, then handoff + fresh session for a new task".
# PostToolUse: from HARD growth, once per 25k step, "write handoff and move the rest of this task to a fresh session now".
import json, os, sys, time
T0 = time.perf_counter()
FAILED = [False]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tzlib import chat_tokens, cfg, LIMIT, HARD, advice

# prompt words -> skill pack (~/.claude/skillpack). Hint printed once per pack per chat, so it costs ~30 tokens only when matched.
from tzlib import PACKS  # skill pack keyword map, shared with tz route


def pack_hint(data):
    import re
    if not os.path.exists(os.path.expanduser('~/.claude/skillpack')):
        return ''
    text = (data.get('prompt') or '').lower()
    state = os.path.expanduser(f"~/.claude/token-zombie/packs-{data.get('session_id', 'x')}")
    seen = set(open(state).read().split()) if os.path.exists(state) else set()
    off = os.path.expanduser('~/.claude/skills-off')
    # suggest only packs that are off (have parked skills), not yet suggested in this chat
    hit = [p for p, rx in PACKS.items() if p not in seen and re.search(rx, text)
           and os.path.isdir(f'{off}/{p}') and os.listdir(f'{off}/{p}')]
    if not hit:
        return ''
    os.makedirs(os.path.dirname(state), exist_ok=True)
    open(state, 'a').write(' '.join(hit) + ' ')
    try:
        import tzlive
        tzlive.discovered(data.get('session_id', 'x'), hit)
    except Exception:
        pass
    return ('TOKEN ZOMBIE (suggestion): skill pack(s) that match words in this prompt: ' + ', '.join(hit)
            + '. Turn one on (~/.claude/skillpack on <pack>) only if the task really needs it and installed skills do not cover it; off when done.')

def _diag(where, ev=''):
    """Append one local diagnostic line to ~/.claude/token-zombie/errors.log; never raises, never blocks the hook.
    Logs only exception type, a short message and file:line:function frames: no locals, no stdin, no transcript text."""
    try:
        import time, traceback
        et, e, tb = sys.exc_info()
        frames = ' < '.join(f'{os.path.basename(f.filename)}:{f.lineno}:{f.name}' for f in reversed(traceback.extract_tb(tb)))
        d = os.path.expanduser('~/.claude/token-zombie')
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, 'errors.log')
        if os.path.exists(p) and os.path.getsize(p) > 65536:  # keep the log small: drop the older half
            keep = open(p, encoding='utf-8', errors='replace').read()[-32768:]
            open(p, 'w', encoding='utf-8').write(keep[keep.find('\n') + 1:])
        import re  # messages can echo data: blank quoted text and long key/token-like runs
        msg = re.sub(r"'[^']*'|\"[^\"]*\"", "'<redacted>'", ' '.join(str(e).split()))
        msg = re.sub(r'[A-Za-z0-9_\-+/=.]{20,}', '<redacted>', msg)[:200]
        with open(p, 'a', encoding='utf-8') as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {where} ev={ev or '?'} {et.__name__}: {msg} @ {frames}\n")
    except Exception:
        pass


ev = ''
data = {}
OUT = [0]  # chars TZ injects this event (its own token overhead)
CTX = [0]  # of those, chars that enter the model's context (advice text; a trimmed output replaces, it adds nothing)
LIVE = ['']  # live-ledger advice (dedupe, old agents), merged into this event's additionalContext


def tzbus_mood(kind):
    """Mascot mood on an event that already fired (no extra reads); never raises."""
    try:
        import tzbus
        tzbus.mood(kind)
    except Exception:
        pass


def emit(obj):
    hs = obj.get('hookSpecificOutput') or {}
    if LIVE[0] and 'permissionDecision' not in hs:
        hs['additionalContext'] = (hs.get('additionalContext', '') + '\n' + LIVE[0]).strip()
    if hs.get('additionalContext'):  # v2.1: never exceed the hook output cap (head+tail kept)
        try:
            import tzfit
            hs['additionalContext'] = tzfit.fit(hs['additionalContext'])
        except Exception:
            pass
    LIVE[0] = ''  # one JSON object per hook run: pending advice goes out here or not at all
    try:  # alert evidence -> later outcome (acted/ignored), in the SQLite ledger
        m = (hs.get('additionalContext') or '') + (obj.get('systemMessage') or '')
        if m.strip() and 'TOKEN ZOMBIE' in m:
            import tzdb
            tzdb.alert_open(data.get('session_id', 'x'), data.get('hook_event_name') or '', m.strip(), _tsize())
    except Exception:
        pass
    for holder, k_ in ((obj, 'reason'), (hs, 'permissionDecisionReason')):  # deny/block text obeys the same cap
        if holder.get(k_):
            try:
                import tzfit
                holder[k_] = tzfit.fit(holder[k_])
            except Exception:
                pass
    t = json.dumps(obj); OUT[0] += len(t); print(t)
    CTX[0] += len(hs.get('additionalContext') or '') + len(hs.get('permissionDecisionReason') or '')


def _pflush():
    if LIVE[0]:
        emit({'hookSpecificOutput': {'hookEventName': 'PreToolUse'}})
    sys.exit(0)


def _tsize():
    try:
        return os.path.getsize(data.get('transcript_path') or '')
    except OSError:
        return 0


def used_tokens(data):
    """Tokens past the chat start. First-reply size never changes: cached per session so only the log tail is parsed."""
    st = os.path.expanduser(f"~/.claude/token-zombie/base-{data.get('session_id', 'x')}")
    try:
        base = int(open(st).read())
    except (OSError, ValueError):
        base = None
    b, last = chat_tokens(data.get('transcript_path'), base)
    if base is None and b:
        os.makedirs(os.path.dirname(st), exist_ok=True); open(st, 'w').write(str(b))
    return max(0, last - b)


try:
    _raw = sys.stdin.read()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import tzlib as _tzl
    if _tzl.dup_hook(os.path.basename(__file__), _raw):
        sys.exit(0)  # same event already handled by the other registered copy
    data = json.loads(_raw)
    ev = data.get('hook_event_name') or 'UserPromptSubmit'
    try:  # supervisor: full tick only on prompt/compact/stop; tool events just record activity (no heavy imports on every call)
        if ev in ('UserPromptSubmit', 'PreCompact', 'Stop', 'SessionEnd'):
            import tzsup
            tzsup.on_event(data)
        elif os.environ.get('TZ_SUP') != '0':
            import tzbus
            tzbus.record_event(ev, data.get('session_id', ''))
    except Exception:
        _diag('supervisor', ev)
    if ev == 'UserPromptSubmit':  # a user message resets the stuck-pattern window (OpenHands parity)
        try:
            import tzstuck
            tzstuck.check(data)
        except Exception:
            _diag('stuck', ev)
    try:  # SQLite ledger: one row per event; resolve open alerts
        import tzdb
        sid_ = data.get('session_id', 'x')
        if ev not in ('PreToolUse', 'PostToolUse'):
            tzdb.record(ev, sid_, tool=data.get('tool_name') or '', agent=data.get('agent_id') or '')
        tzdb.alert_resolve(sid_, ev, _tsize())
    except Exception:
        _diag('ledger', ev)
    try:  # live ledger: skill states, agent lifecycle, conservative dedupe (advice only)
        import tzlive
        if ev in ('PreModelSwitch', 'PostModelSwitch'):  # context size at the switch: a model change re-reads it uncached (EST)
            try:
                data['tz_ctx_tokens'] = used_tokens(data)
            except Exception:
                pass
        LIVE[0] = tzlive.on_event(data) or ''
        if LIVE[0] and ev == 'PreToolUse' and not advice('dup_advice'):
            LIVE[0] = ''
    except Exception:
        _diag('live', ev)
    if ev == 'UserPromptSubmit':  # v2.1 tips: opt-in hard size cap first, then one-line advice merged into this event's output
        try:
            import tztips
            why = tztips.cap_block(data) or tztips.paste_block(data)
        except Exception:
            why = ''
            _diag('sizecap', ev)
        if why:
            emit({'decision': 'block', 'reason': why})
            sys.exit(0)
        try:
            import tztips
            LIVE[0] = (LIVE[0] + '\n' + tztips.prompt_tips(data)).strip()
        except Exception:
            _diag('tips', ev)
    claim = ''
    if ev == 'Stop':  # opt-in (unverified_claim): success claimed with no passing check; advice only
        try:
            import tzclaim
            claim = tzclaim.stop_advice(data)
        except Exception:
            _diag('claim', ev)
    if ev == 'Stop' and claim and not advice('next_task'):
        emit({'systemMessage': claim})
    if ev == 'UserPromptSubmit':  # v2.1 spend budget: opt-in hard stop, then one warning line per level
        try:
            import tzbudget
            why = tzbudget.block_reason(data)
        except Exception:
            why = ''
            _diag('budget', ev)
        if why:
            emit({'decision': 'block', 'reason': why})
            sys.exit(0)
        try:
            import tzbudget
            LIVE[0] = (LIVE[0] + '\n' + tzbudget.prompt_advice(data)).strip()
        except Exception:
            _diag('budget', ev)
    if ev in ('UserPromptSubmit', 'PreToolUse', 'PostToolUse', 'PostToolUseFailure') and any(
            _tzl.feature(f) for f in ('obs_record', 'obs_file_context')):  # v2.1 observation memory (opt-in)
        try:
            import tzobs
            LIVE[0] = (LIVE[0] + '\n' + tzobs.hook(data)).strip()
        except Exception:
            _diag('obs', ev)
    if ev == 'Stop' and advice('next_task'):  # turn closed past the limit: tell the user to /compact (advice, once per 25k)
        try:
            import tzcont
            _u = used_tokens(data)
            tzcont.newchat_flag(data, _u)  # bar: "start a new chat" past the limit
            m = tzcont.compact_hint(data, _u)
            pc = tzcont.pack_cleanup(data)
            m = '\n'.join(x for x in (m, pc, tzcont.untested_advice(data), claim) if x)
            if m:
                if m != claim:
                    tzbus_mood('compact')
                emit({'systemMessage': m, **({'hookSpecificOutput': {'hookEventName': ev}} if LIVE[0] else {})})
        except Exception:
            _diag('compact', ev)
            if claim:
                emit({'systemMessage': claim})
    if ev == 'Stop':  # keep the fresh-chat saving in TOKENS SAVED current (scan of recent logs, at most every 5 min)
        try:
            import tzopt
            fj = os.path.join(tzopt.STATE, 'fresh.json')
            if not os.path.exists(fj) or time.time() - os.path.getmtime(fj) > 300:
                tzopt.fresh_file()
        except Exception:
            _diag('fresh', ev)
    if ev == 'SessionEnd':  # opt-in (micro_skills): learn facts from the finished transcript
        try:
            import tzfacts
            tzfacts.session_end(data)
        except Exception:
            _diag('facts', ev)
    if ev == 'SessionEnd':  # on-demand: turn off what this chat turned on (verified, logged)
        try:
            import tzondemand
            tzondemand.session_end(data.get('session_id', ''))
            import tzcont
            tzcont.release_claims(data.get('session_id', ''))
        except Exception:
            _diag('ondemand', ev)
    if ev == 'SubagentStart' and advice('pack_hints'):  # subagent report is re-sent every later call: cap it (advice, fail open)
        emit({'hookSpecificOutput': {'hookEventName': ev, 'additionalContext': 'TOKEN ZOMBIE: final report <= 300 words: verdict, evidence as file:line paths, no pasted file contents or history.'}})
        sys.exit(0)
    if ev in ('PreCompact', 'PostCompact'):  # earlier reads leave the context: forget their snapshots
        try:
            import tztokopt
            tztokopt.reset(data.get('session_id', 'x'))
        except Exception:
            _diag('delta', ev)
    if ev in ('Stop', 'SessionEnd', 'PreCompact', 'SubagentStop', 'SubagentStart', 'InstructionsLoaded', 'PostCompact') + ('PostToolBatch', 'PreModelSwitch', 'PostModelSwitch', 'WorktreeCreate', 'WorktreeRemove', 'FileChanged'):
        sys.exit(0)
    if ev == 'PreToolUse':  # policy engine: advice only, fail open, TZ_POLICY=0 disables
        try:
            import tzpolicy
            pa = tzpolicy.hook_advice(data)
            if pa:
                LIVE[0] = (LIVE[0] + '\n' + pa).strip()
        except Exception:
            _diag('policy', ev)
    if ev == 'PreToolUse' and data.get('tool_name') in ('Read', 'Grep', 'Glob'):  # v2.1 opt-in bulk-read block
        try:
            import tztips
            why = tztips.bulk_gate(data)
        except Exception:
            why = ''
            _diag('bulk', ev)
        if why:
            emit({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', 'permissionDecisionReason': why}})
            _pflush()
    if ev == 'PreToolUse' and data.get('tool_name') == 'Bash':  # opt-in (git_guard): hook() fails closed while on
        try:
            import tzgitguard
            why = tzgitguard.hook(data)
        except Exception:
            why = ''
            _diag('gitguard', ev)
        if why:
            emit({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', 'permissionDecisionReason': why}})
            _pflush()
    if ev == 'PreToolUse' and data.get('tool_name', 'Read') != 'Read':
        if data.get('tool_name') == 'Bash' and os.environ.get('TZ_SAFE') != '0':  # destructive-command guard (tz safe); TZ_SAFE=0 turns it off
            try:
                import tzops
                ok, why = tzops.safe((data.get('tool_input') or {}).get('command') or '', data.get('cwd'))
            except Exception:  # v2.1: fail closed (only a crash in tzops itself lands here; tzshell errors fall back to RULES)
                ok, why = False, 'safety check crashed (fail closed); retry, or run with TZ_SAFE=0'
                _diag('safe', ev)
            if not ok:
                emit({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                      'permissionDecisionReason': 'TOKEN ZOMBIE safe: blocked (%s). Ask the owner, or run it with TZ_SAFE=0.' % why}})
                _pflush()
        if data.get('tool_name') == 'Bash':  # v2.1 stale branch before a broad test run: warn, or opt-in deny once
            try:
                import tzclaw
                kind, why = tzclaw.hook(data)
            except Exception:
                kind, why = '', ''
                _diag('stale', ev)
            if kind == 'deny':
                emit({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', 'permissionDecisionReason': why}})
                _pflush()
            if kind:
                LIVE[0] = (LIVE[0] + '\n' + why).strip()
        if data.get('tool_name') in ('Edit', 'Write', 'MultiEdit', 'NotebookEdit') and advice('next_task'):
            try:  # another live chat claimed this file: warn BEFORE the write (advice only)
                import tzcont
                LIVE[0] = (LIVE[0] + '\n' + tzcont.file_guard(data)).strip()
            except Exception:
                _diag('fileguard', ev)
        if data.get('tool_name') == 'Bash':  # test/build output piped away hides lines and the exit code (advice only)
            try:
                from tzlib import feature
                if feature('check_pipe'):
                    from tzhumanlayer import check_pipe_advice
                    m = check_pipe_advice(data)
                    if m:
                        LIVE[0] = (LIVE[0] + '\n' + m).strip()
            except Exception:
                _diag('check_pipe', ev)
        if data.get('tool_name') == 'Bash':  # curl/wget host outside .tz/scope.json (advice only; silent without that file)
            try:
                from tzlib import feature
                if feature('scope_check'):
                    import tzscope
                    m = tzscope.advise(data)
                    if m:
                        LIVE[0] = (LIVE[0] + '\n' + m).strip()
            except Exception:
                _diag('scope', ev)
        if (data.get('tool_name') or '').startswith('mcp__'):  # v2.1: same read-only MCP call already answered (advice only)
            try:
                from tztoolprune import mcp_dup
                LIVE[0] = (LIVE[0] + '\n' + mcp_dup(data)).strip()
            except Exception:
                _diag('mcpdup', ev)
        if LIVE[0]:
            emit({'hookSpecificOutput': {'hookEventName': 'PreToolUse'}})
        sys.exit(0)
    if ev in ('PreToolUse', 'PostToolUse') and data.get('tool_name') == 'Read':  # opt-in read_delta: re-read of a changed file gets the diff
        try:
            import tztokopt
            why = tztokopt.advise(data)
        except Exception:
            why = ''
            _diag('delta', ev)
        if why and ev == 'PreToolUse':
            emit({'hookSpecificOutput': {'hookEventName': ev, 'permissionDecision': 'deny', 'permissionDecisionReason': why}})
            _pflush()
    if ev == 'PreToolUse':  # big Read: nudge once, never block twice (whole file may be truly needed)
        ti = data.get('tool_input') or {}
        f = ti.get('file_path') or ''
        if (ti.get('limit') or ti.get('offset') or not os.path.isfile(f) or os.path.getsize(f) <= cfg('read_warn')
                or f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf', '.ipynb'))):
            if not advice('dup_advice'):
                _pflush()
            try:  # same file+range already read and unchanged: advice (default) or, with read_guard=deny, deny once (retry allowed)
                from tzopt import read_decision, ledger
                r = read_decision(data)
                if r:
                    emit({'hookSpecificOutput': r})
            except Exception:
                pass
            _pflush()
        if not advice('read_nudge'):
            _pflush()
        state = os.path.expanduser(f"~/.claude/token-zombie/read-{data.get('session_id', 'x')}")
        seen = open(state).read().splitlines() if os.path.exists(state) else []
        if f in seen:
            _pflush()  # second attempt = Claude decided the whole file is needed: allow
        os.makedirs(os.path.dirname(state), exist_ok=True)
        open(state, 'a').write(f + '\n')
        emit(({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
            'permissionDecisionReason': f'TOKEN ZOMBIE (advice, not a ban): {f} is {os.path.getsize(f) // 1024} KB. '
            'If only part is needed: grep -n, then Read with offset+limit. If the task needs the whole file, '
            'repeat the same Read: it will be allowed.'}}))
        _pflush()
    if ev in ('PostToolUse', 'PostToolUseFailure') and advice('next_task'):  # circuit breaker: same tool/command failing 3x (advice only)
        try:
            import tzcont
            m = tzcont.breaker(data)
            if m:
                tzbus_mood('churn')
                LIVE[0] = (LIVE[0] + '\n' + m).strip()
        except Exception:
            _diag('breaker', ev)
    if ev in ('PostToolUse', 'PostToolUseFailure'):  # v2.1 OpenHands-style stuck patterns
        try:
            import tzstuck
            m = tzstuck.check(data)
            if m and ev in ('PostToolUse', 'PostToolUseFailure'):
                data['_stuck_said'] = 1
                LIVE[0] = (LIVE[0] + '\n' + m).strip()
        except Exception:
            _diag('stuck', ev)
    if ev == 'PostToolUse' and data.get('tool_name') in ('Write', 'Edit', 'MultiEdit'):  # SKILL.md spec check (advice only)
        try:
            import tzaskills
            m = tzaskills.advise(data)
            if m:
                LIVE[0] = (LIVE[0] + '\n' + m).strip()
        except Exception:
            _diag('skill_lint', ev)
    if ev == 'PostToolUseFailure':
        if LIVE[0]:
            emit({'hookSpecificOutput': {'hookEventName': ev}})
        sys.exit(0)
    if ev == 'PostToolUse':  # verified test pass -> task record + checkpoint (silent); before the trim, which exits
        try:
            import tznext
            tznext.on_tool(data)
        except Exception:
            _diag('next', ev)
        try:  # churn counters (per-file edits/reads, images); judged on the next prompt
            import tzcont
            tzcont.churn_tool(data)
            tzcont.churn_step(data)
            if advice('next_task'):  # loop + claim-board lines, sent with this call's output
                LIVE[0] = (LIVE[0] + '\n' + tzcont.tool_advice(data)).strip()
        except Exception:
            _diag('churn', ev)
        if (data.get('tool_name') or '') == 'Bash':  # rtk's measured cut feeds TOKENS SAVED / OPTIMIZATIONS live
            try:
                from tzopt import rtk_delta
                rtk_delta(data.get('session_id', 'x'))
            except Exception:
                _diag('rtk', ev)
    if ev == 'PostToolUse':  # big Read/Grep/WebFetch/MCP/Bash output: trim before the model sees it, full text kept (tz recall)
        tool = data.get('tool_name') or ''
        if tool in ('Read', 'Grep', 'WebFetch', 'Bash') or tool.startswith('mcp__'):
            try:
                from tzout import trim
                out, saved = trim(data)
                if out:
                    try:  # measured cut feeds TOKENS SAVED / OPTIMIZATIONS on the bar
                        from tzopt import ledger
                        ledger('output-trim', saved, 'measured', data.get('session_id', 'x'), 'trim ' + tool)
                    except Exception:
                        pass
                    try:  # tzlive must not call this result "still above" any more
                        tzlive.edit(data.get('session_id', 'x'), lambda s: s['calls'].get(tzlive.key(data), {}).update(trimmed=1))
                    except Exception:
                        pass
                    emit({'hookSpecificOutput': out})
                    sys.exit(0)
            except Exception:
                _diag('out', ev)
    used = used_tokens(data)
    k = used // 1000
    if used >= HARD and ev in ('PostToolUse', 'UserPromptSubmit'):  # before the limit: cheap safe checkpoint, no commands run
        try:
            import tznext
            tznext.checkpoint(data.get('cwd') or os.getcwd(), 'before-limit')
        except Exception:
            _diag('next', ev)
    if ev == 'PostToolUse':
        if used < HARD:
            if LIVE[0]:
                emit({'hookSpecificOutput': {'hookEventName': ev}})
            sys.exit(0)
        # speak once per 25k step so it never costs tokens on every tool call
        state = os.path.expanduser(f"~/.claude/token-zombie/guard-{data.get('session_id', 'x')}")
        step = used // 25000
        try:
            if int(open(state).read()) >= step:
                sys.exit(0)
        except (OSError, ValueError):
            pass
        os.makedirs(os.path.dirname(state), exist_ok=True)
        open(state, 'w').write(str(step))
        msg = (f'TOKEN ZOMBIE: chat is {k}k tokens past start; every step re-sends all of it. Do NOT drop the task. '
               'At the next safe point (not mid-edit, mid-test or mid-file-operation) write the daily handoff '
               '(Status/Done verified/Left/Next step/Changed files/Tests, <=30 lines) and the HANDOFF.md top block, '
               'then move the rest of the task to a fresh session (mcp__ccd_session__hand_off_to_session if available, '
               'else tell the owner: "new chat, say: read <handoff path> and continue").')
    else:
        cont = ''
        if advice('next_task'):  # early churn: one line of checkpoint advice, merged into this event's output
            try:
                import tzcont
                ch = tzcont.churn_prompt(data, used)
                if ch:
                    tzbus_mood('churn' if 'churn' in ch else 'fresh')
                    LIVE[0] = (LIVE[0] + '\n' + ch).strip()
            except Exception:
                _diag('churn', ev)
        if used >= LIMIT // 2 and advice('next_task'):  # expensive chat (growth, spend, repeated reads): verified checkpoint + manual step, once
            try:
                import tzcont
                cont = tzcont.on_prompt(data, used)
            except Exception:
                _diag('cont', ev)
        if cont and used < LIMIT:
            emit({'hookSpecificOutput': {'hookEventName': ev, 'additionalContext': cont}})
            sys.exit(0)
        if used < LIMIT:
            hint = pack_hint(data) if advice('pack_hints') else ''
            try:  # on-demand: optional capability the prompt needs is off
                import tzondemand
                w = tzondemand.want(data.get('prompt')) if advice('pack_hints') else []
                if w:
                    hint = (hint + ' ' if hint else '') + ('TOKEN ZOMBIE (suggestion): this task may need ' + ', '.join(w)
                            + ' (off now). If so: tz ondemand on ' + ' '.join(w) + ' --session ' + data.get('session_id', '')
                            + ' ; it is turned off again when this chat ends.')
            except Exception:
                _diag('ondemand', ev)
            try:  # several independent tasks in one prompt: one session per task, build first, test last
                import tzsplit
                ts = tzsplit.detect(data.get('prompt')) if advice('pack_hints') else []
                sh = tzsplit.ship_hint(data.get('prompt'), ts) if advice('pack_hints') else ''
                if sh:
                    hint = (hint + ' ' if hint else '') + sh
            except Exception:
                _diag('split', ev)
            try:  # engineering prompt: point at the coding pipeline once (advice)
                import tzopt
                if advice('pack_hints') and tzopt.classify(data.get('prompt') or '')[0] == 'ENGINEERING':
                    hint = (hint + ' ' if hint else '') + 'TOKEN ZOMBIE (suggestion): coding task: follow tz code (plan, build all first, test once, review the diff, simplify, ship after owner OK; best skill per phase).'
            except Exception:
                _diag('code', ev)
            if hint:
                emit(({'hookSpecificOutput': {'hookEventName': ev, 'additionalContext': hint}}))
            sys.exit(0)
        if not advice('next_task'):
            sys.exit(0)
        msg = (f'TOKEN ZOMBIE: chat is {k}k tokens past start. If this prompt continues the unfinished task, keep going until it is done, '
               'no big reads or images. If it is a NEW task: write the handoff first, then start it in a fresh session '
               '(mcp__ccd_session__start_session, context "fresh", short brief + handoff path; else tell the owner to open a new chat).')
        if cont:
            msg += '\n' + cont
    emit(({'hookSpecificOutput': {'hookEventName': ev, 'additionalContext': msg}}))
except SystemExit:
    pass
except Exception:
    FAILED[0] = True
    _diag('guard', ev)
finally:
    try:
        if LIVE[0] and not OUT[0]:
            emit({'hookSpecificOutput': {'hookEventName': ev}})
        import tzlive
        if CTX[0]:  # TZ's own context cost, every hook path, one entry per event
            from tzopt import ledger
            ledger('overhead-hook', CTX[0], 'measured', data.get('session_id', 'x'), 'advice text ' + ev)
        tzlive.timing(data.get('session_id', 'x'), ev + (':' + data['tool_name'] if data.get('tool_name') else ''),
                      (time.perf_counter() - T0) * 1000, OUT[0], FAILED[0])
    except Exception:
        pass
sys.exit(0)
