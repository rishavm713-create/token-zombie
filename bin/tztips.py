# MIT License. Part of TOKEN ZOMBIE (Created by Rishav Mishra).
# toolprune idea (per-server tool-definition cost) from microsoft/TokenEconomizer (MIT).
# v2.1 tips: instruction-file report/fix, model/plan nudges, bulk-read block, size gate, idle cost, defaults.
# All functions are pure or take paths/dicts as arguments and never raise. '' = no advice. Token numbers are [est] = chars // 4.
# paste_warn limit: a hook cannot merge messages or convert a paste before it enters the chat; it can only warn afterwards.
import os, re, sys, json, time, shutil

DEF = {'instr_warn_tokens': 3000, 'bulk_read_n': 8, 'size_soft': [50000, 100000], 'size_cap': 150000,
       'paste_warn_chars': 8000, 'mcp_unused_sessions': 5, 'paste_block_chars': 40000, 'small_msgs_n': 4,
       'small_msgs_chars': 40}


def _cfg(key, c=None):
    """Config value: explicit dict c, then env TZ_<KEY>, then tzlib config, then default. Never raises."""
    try:
        if c and key in c:
            return c[key]
        e = os.environ.get('TZ_' + key.upper())
        if e not in (None, ''):
            return json.loads(e) if key == 'size_soft' else int(e)
        import tzlib
        v = tzlib._conf.get(key)
        if v not in (None, ''):
            return v
    except Exception:
        pass
    return DEF[key]


def _est(t):
    return len(t or '') // 4


def _read(p):
    try:
        return open(p, encoding='utf-8', errors='ignore').read()
    except Exception:
        return ''


def _norm_lines(t):
    return {re.sub(r'\s+', ' ', l.strip().lower()) for l in t.splitlines() if l.strip()}


def _slug(cwd):
    return re.sub(r'[^A-Za-z0-9]', '-', cwd or '')


# ---------- 1. instruction files ----------
def _imports(path, seen):
    out = []
    base = os.path.dirname(path)
    for l in _read(path).splitlines():
        s = l.strip()
        if s.startswith('@') and len(s) > 1 and ' ' not in s:
            p = os.path.expanduser(s[1:])
            p = p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))
            if p not in seen and os.path.isfile(p):
                seen.add(p); out.append(p); out += _imports(p, seen)
    return out


def _sections(text):
    secs, cur, buf = [], None, []
    for l in text.splitlines():
        if re.match(r'#{1,6}\s', l):
            if cur is not None:
                secs.append((cur, '\n'.join(buf)))
            cur, buf = l.lstrip('#').strip(), [l]
        elif cur is not None:
            buf.append(l)
    if cur is not None:
        secs.append((cur, '\n'.join(buf)))
    return secs


def instr_report(home, cwd):
    """Files Claude Code loads every call (CLAUDE.md + @imports + project MEMORY.md) plus other candidates (AGENTS.md: loaded only if imported)."""
    try:
        cands, loaded = [], {}
        roots = [os.path.join(home, '.claude', 'CLAUDE.md'), os.path.join(cwd, 'CLAUDE.md'),
                 os.path.join(cwd, '.claude', 'CLAUDE.md'),
                 os.path.join(home, '.claude', 'projects', _slug(cwd), 'memory', 'MEMORY.md')]
        seen = set()
        for r in roots:
            if os.path.isfile(r):
                loaded[r] = 'CLAUDE.md / memory index'
                seen.add(r)
                for i in _imports(r, seen):
                    loaded[i] = '@import'
        for p in (os.path.join(home, 'AGENTS.md'), os.path.join(cwd, 'AGENTS.md')):
            if os.path.isfile(p) and p not in loaded:
                cands.append((p, 'AGENTS.md is not read by Claude Code unless imported'))
        files, texts = [], {}
        for p, why in list(loaded.items()) + cands:
            t = _read(p); texts[p] = t
            files.append({'path': p, 'tokens_est': _est(t), 'loaded': p in loaded, 'reason': why if p not in loaded else loaded[p]})
        total = sum(f['tokens_est'] for f in files if f['loaded'])
        secs = []
        for f in files:
            if f['loaded']:
                for h, b in _sections(texts[f['path']]):
                    secs.append({'file': f['path'], 'heading': h, 'tokens_est': _est(b), 'body': b})
        secs.sort(key=lambda s: -s['tokens_est'])
        big = [{k: v for k, v in s.items() if k != 'body'} for s in secs[:3]]
        step = re.compile(r'^\s*(\d+[.)]|[-*])\s+', re.M)
        skills = [{'file': s['file'], 'heading': s['heading'], 'tokens_est': s['tokens_est']}
                  for s in secs if s['tokens_est'] > 400 and len(step.findall(s['body'])) >= 5]
        dups = []
        for i in range(len(files)):
            for j in range(i + 1, len(files)):
                a, b = _norm_lines(texts[files[i]['path']]), _norm_lines(texts[files[j]['path']])
                if a and b and len(a & b) / len(a | b) >= 0.8:
                    dups.append({'a': files[i]['path'], 'b': files[j]['path'], 'a_loaded': files[i]['loaded'],
                                 'b_loaded': files[j]['loaded'], 'jaccard': round(len(a & b) / len(a | b), 2)})
        return {'files': files, 'total_est': total, 'biggest_sections': big, 'duplicates': dups, 'skill_candidates': skills}
    except Exception:
        return {'files': [], 'total_est': 0, 'biggest_sections': [], 'duplicates': [], 'skill_candidates': []}


def instr_advice(report, threshold=None):
    try:
        th = threshold if threshold is not None else _cfg('instr_warn_tokens')
        if not report or report.get('total_est', 0) < th:
            return ''
        s = f"TOKEN ZOMBIE instructions: {report['total_est']} tokens [est] load every call"
        if report.get('biggest_sections'):
            b = report['biggest_sections'][0]
            s += f"; biggest section '{b['heading']}' {b['tokens_est']} [est]"
        if report.get('duplicates'):
            d = report['duplicates'][0]
            s += f"; duplicate: {os.path.basename(d['a'])} ~ {os.path.basename(d['b'])}"
        return s + '. Fix: tz instr --fix'
    except Exception:
        return ''


def _sha_copy(src, bdir):
    os.makedirs(bdir, exist_ok=True)
    dst = os.path.join(bdir, re.sub(r'[^A-Za-z0-9._-]', '_', src) + '.bak')
    shutil.copy2(src, dst)
    return dst


def instr_fix(report, apply=False, backup_dir=None):
    """Plan (list of action dicts); with apply=True back up first, replace the duplicate with '@<first>'; returns the plan with undo info."""
    plan = []
    try:
        for d in report.get('duplicates', []):
            if d['a_loaded'] and d['b_loaded']:
                plan.append({'action': 'replace', 'path': d['b'], 'with': '@' + d['a'], 'note': 'both loaded: second becomes a one-line import'})
            else:
                plan.append({'action': 'none', 'path': d['b'] if not d['b_loaded'] else d['a'],
                             'note': 'duplicate is not loaded by Claude Code; nothing to do for Claude'})
        if apply and backup_dir:
            undo = []
            for a in plan:
                if a['action'] == 'replace' and os.path.isfile(a['path']):
                    undo.append({'path': a['path'], 'backup': _sha_copy(a['path'], backup_dir)})
                    open(a['path'], 'w', encoding='utf-8').write(a['with'] + '\n')
            idx = os.path.join(backup_dir, 'instr-undo.json')
            json.dump(undo, open(idx, 'w'))
            for a in plan:
                a['applied'] = a['action'] == 'replace'
            plan.append({'action': 'undo-info', 'undo': undo, 'restore': 'tz instr --fix --restore'})
    except Exception:
        pass
    return plan


def instr_restore(backup_dir):
    n = 0
    try:
        for u in json.load(open(os.path.join(backup_dir, 'instr-undo.json'))):
            shutil.copy2(u['backup'], u['path']); n += 1
    except Exception:
        pass
    return n


# ---------- 2. model advice ----------
MECH = ('rename', 'format', 'typo', 'translate', 'list files', 'reformat', 'lint', 'indent', 'sort', 'fix spelling', 'spelling', 'capitalize', 'bump version')
HARD = ('design', 'architecture', 'debug', 'investigate', 'why ', 'race condition', 'security', 'refactor', 'algorithm', 'optimi', 'root cause', 'tradeoff', 'trade-off', 'performance')


def model_advice(prompt, cur_model=''):
    try:
        p = (prompt or '').lower()
        if re.search(r'sonnet|haiku', (cur_model or '').lower()):
            return ''
        if any(h in p for h in HARD):
            return ''
        n = len(p.split())
        if any(m in p for m in MECH) and n < 25:
            return ('TOKEN ZOMBIE model: mechanical task: Sonnet/Haiku at low effort is enough '
                    '(model menu / --model sonnet); never switched silently.')
    except Exception:
        pass
    return ''


# ---------- 3. plan advice ----------
BROAD = re.compile(r'\b(build|redesign|migrate|rewrite|overhaul|refactor (the )?(whole|entire|all)|from scratch)\b', re.I)
SPECIFIC = re.compile(r'`|[\w.-]+/[\w./-]+|\b\w+\.(py|js|ts|tsx|md|json|sh|go|rs|css|html)\b|\bline \d+|\b\w+\(\)')


def plan_advice(prompt):
    try:
        p = prompt or ''
        if SPECIFIC.search(p):
            return ''
        if len(p.split()) >= 60 or BROAD.search(p):
            return ('TOKEN ZOMBIE plan: big and vague task: plan first (shift+tab for plan mode, or EnterPlanMode) '
                    'so the work is agreed before tokens are spent on edits.')
    except Exception:
        pass
    return ''


# ---------- 4. bulk reads ----------
READS = {'Read', 'Grep', 'Glob'}


def _tool_names(src):
    out = []
    for x in src or []:
        if isinstance(x, str) and not x.lstrip().startswith('{'):
            out.append(x); continue
        try:
            d = json.loads(x) if isinstance(x, str) else x
            if d.get('isSidechain'):
                continue
            m = d.get('message')
            if d.get('type') == 'assistant' and isinstance(m, dict) and isinstance(m.get('content'), list):
                out += [b['name'] for b in m['content'] if isinstance(b, dict) and b.get('type') == 'tool_use']
        except Exception:
            pass
    return out


def bulk_reads(transcript_lines, n=None):
    try:
        n = n or _cfg('bulk_read_n')
        t = _tool_names(transcript_lines)
        return len(t) >= n and all(x in READS for x in t[-n:])
    except Exception:
        return False


def bulk_block_msg():
    return ('TOKEN ZOMBIE: many Read/Grep/Glob calls in a row in the main chat. Use an Explore subagent '
            '(Agent tool, subagent_type Explore) for the rest of the searching; it returns only the conclusion. '
            'This blocks once; repeating the call works. Turn it off: TZ_FEAT_BULK_READ_BLOCK=0, or '
            'features.bulk_read_block 0 in ~/.claude/token-zombie/config.json.')


# ---------- 5. size gate + handoff ----------
def size_gate(used_tokens, c=None):
    try:
        soft = _cfg('size_soft', c); cap = int(_cfg('size_cap', c))
        if cap and used_tokens >= cap:
            return 'block', 'TOKEN ZOMBIE: chat is %d tokens [est]: /clear now; handoff saved (see handoffs/ folder, run `tz handoff save`).' % used_tokens
        tier = 'ok'
        if len(soft) > 1 and soft[1] and used_tokens >= soft[1]:
            tier = 'soft100'
        elif soft and soft[0] and used_tokens >= soft[0]:
            tier = 'soft50'
        if tier == 'ok':
            return 'ok', ''
        return tier, (f'TOKEN ZOMBIE: chat is {used_tokens} tokens; every step re-sends it. At a safe point end this turn with '
                      'mcp__ccd_turn__wrap_up offering a button labelled "Fresh chat". On click: write the handoff '
                      '(handoffs/YYYY-MM-DD.md + `tz handoff save`), then call mcp__ccd_session_mgmt__clear_session with '
                      'session_id "self" (the app asks the user to approve; the old chat stays resumable). In the terminal CLI '
                      'print the exact line `/clear` and say the handoff is saved. Never stop mid-task.')
    except Exception:
        return 'ok', ''


def save_handoff(cwd, note, now=None):
    """Append a dated block to <cwd>/handoffs/YYYY-MM-DD.md (never clobbers); keeps the file <= 30 lines. Returns the path."""
    try:
        now = now or time.time()
        d = os.path.join(cwd, 'handoffs'); os.makedirs(d, exist_ok=True)
        p = os.path.join(d, time.strftime('%Y-%m-%d', time.localtime(now)) + '.md')
        old = _read(p).rstrip('\n')
        blk = '## %s\n%s' % (time.strftime('%H:%M', time.localtime(now)), (note or '').strip())
        lines = ((old + '\n' if old else '') + blk).splitlines()
        if len(lines) > 30:  # drop oldest blocks, keep newest
            keep = (old + '\n' + blk).split('\n## ')
            lines = []
            for i in range(len(keep) - 1, -1, -1):
                b = (keep[i] if keep[i].startswith('## ') else '## ' + keep[i]).splitlines()
                if len(lines) + len(b) > 30:
                    break
                lines = b + lines
            lines = lines or blk.splitlines()[:30]
        open(p, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
        return p
    except Exception:
        return ''


# ---------- 6. task switch ----------
STOP = set('the a an and or to of in on for with is it this that i you me my we do does did can please just are be as at by from'.split())
CUE = re.compile(r'new task|\bnext\b|now do|different|another project|switch|\bnow (let\'s|lets|i want)', re.I)


def _words(t):
    return {w for w in re.findall(r'[a-z0-9_]{3,}', (t or '').lower()) if w not in STOP}


def _paths(t):
    return set(re.findall(r'(?:~|/)[\w.-]+(?:/[\w.-]+)*', t or ''))


def task_switch(prompt, prev_prompts):
    try:
        if len((prompt or '').split()) < 6 or not prev_prompts:
            return False
        prev = prev_prompts[-3:]
        w = _words(prompt); pw = set().union(*[_words(x) for x in prev])
        j = len(w & pw) / len(w | pw) if (w | pw) else 1
        if j >= 0.15:
            return False
        pp, np_ = set().union(*[_paths(x) for x in prev]), _paths(prompt)
        newproj = bool(np_ and pp and not (np_ & pp) and {p.split('/')[1] if p.startswith('/') and len(p.split('/')) > 2 else p for p in np_}.isdisjoint(
            {p.split('/')[1] if p.startswith('/') and len(p.split('/')) > 2 else p for p in pp}))
        return bool(CUE.search(prompt)) or newproj
    except Exception:
        return False


# ---------- 7. idle cost ----------
def idle_cost(used_tokens, gap_s, ttl_s, startup=20000):
    try:
        if gap_s <= 300 or gap_s <= ttl_s:
            return ''
        mult = 2.0 if ttl_s >= 3600 else 1.25
        return ('TOKEN ZOMBIE idle: cache expired after %ds idle (cache lives 5 min or 1 h; this one: %s). Next message rewrites the cache: '
                '~%d token-equivalents [est] (%gx of %d) vs ~%d for a fresh start. Offer: button "Fresh chat".'
                % (gap_s, '1 h' if ttl_s >= 3600 else '5 min', int(used_tokens * mult), mult, used_tokens, startup))
    except Exception:
        return ''


# ---------- 8. home cwd ----------
def home_cwd(cwd, home):
    try:
        if os.path.realpath(cwd) != os.path.realpath(home):
            return ''
        best = None
        for i, n in enumerate(sorted(os.listdir(home))):
            if i >= 200:
                break
            p = os.path.join(home, n)
            if n.startswith('.') or not os.path.isdir(p):
                continue
            if os.path.exists(os.path.join(p, '.git')) or os.path.exists(os.path.join(p, 'HANDOFF.md')):
                m = os.path.getmtime(p)
                if best is None or m > best[0]:
                    best = (m, n)
        if not best:
            return ''
        return 'TOKEN ZOMBIE: started in ~; project folder? cd ~/%s (newest: %s)' % (best[1], best[1])
    except Exception:
        return ''


# ---------- 9. paste warn ----------
def paste_warn(prompt, n=None):
    try:
        n = n or _cfg('paste_warn_chars')
        if len(prompt or '') > n:
            return ('TOKEN ZOMBIE paste: %d chars [est %d tokens] pasted; it is now in every later call. Next time save it to a file '
                    'and give the path.' % (len(prompt), len(prompt) // 4))
    except Exception:
        pass
    return ''


def paste_block(data, now=None):
    """Opt-in (feature paste_block): save a very large prompt to <cwd>/handoffs/paste-<time>.md and return a block reason.
    Claude Code drops a blocked prompt from the context. '' when off, small, or the save failed (then nothing is blocked)."""
    try:
        import tzlib
        prompt = data.get('prompt') or ''
        if not tzlib.feature('paste_block') or len(prompt) <= _cfg('paste_block_chars') or prompt.lstrip().startswith('/'):
            return ''
        now = now or time.time()
        d = os.path.join(data.get('cwd') or os.getcwd(), 'handoffs'); os.makedirs(d, exist_ok=True)
        p = os.path.join(d, 'paste-%s.md' % time.strftime('%Y%m%d-%H%M%S', time.localtime(now)))
        open(p, 'w', encoding='utf-8').write(prompt)
        return ('TOKEN ZOMBIE paste: %d chars [est %d tokens] saved to %s and not sent. Send "read %s" (plus what to do with it). '
                'Turn this off: TZ_FEAT_PASTE_BLOCK=0.' % (len(prompt), len(prompt) // 4, p, p))
    except Exception:
        return ''


def small_msgs(lens, n=None, chars=None):
    """Tip when the last n prompts were all short: each one re-sends the whole chat."""
    n, chars = n or _cfg('small_msgs_n'), chars or _cfg('small_msgs_chars')
    if len(lens) >= n and all(0 < x <= chars for x in lens[-n:]):
        return ('TOKEN ZOMBIE: %d short messages in a row; each one re-sends the whole chat. Send one full message with '
                'everything instead.' % n)
    return ''


ARCHIVE_CUE = re.compile(r'\b(done|finished|that\'?s all|thanks?|thank you|ship it|wrap up)\b', re.I)


def archive_advice(prompt):
    """Task-end prompt: tell the model to offer the app's auto-archive setting; it changes it only after the owner's yes."""
    if ARCHIVE_CUE.search(prompt or '') and len(prompt or '') < 200:
        return ('TOKEN ZOMBIE archive: the task looks finished. If the Code tab auto-archive setting is off (ccd_settings '
                'get_settings), offer once to turn it on; change it only after the owner says yes.')
    return ''


# ---------- 10. defaults ----------
def defaults_plan(settings, verified_env):
    ch = []
    try:
        env = settings.get('env') or {}
        if 'model' not in settings:
            ch.append(('model', None, 'sonnet'))
        if env.get('CLAUDE_CODE_SUBAGENT_MODEL') != 'haiku':
            ch.append(('env.CLAUDE_CODE_SUBAGENT_MODEL', env.get('CLAUDE_CODE_SUBAGENT_MODEL'), 'haiku'))
        if (verified_env or {}).get('CLAUDE_AUTOCOMPACT_PCT_OVERRIDE'):
            if env.get('CLAUDE_AUTOCOMPACT_PCT_OVERRIDE') != '50':
                ch.append(('env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE', env.get('CLAUDE_AUTOCOMPACT_PCT_OVERRIDE'), '50'))
        else:
            ch.append(('MISSING', None, 'CLAUDE_AUTOCOMPACT_PCT_OVERRIDE not verified to exist in this Claude Code: skipped'))
    except Exception:
        pass
    return ch


def _setk(d, key, v):
    if key.startswith('env.'):
        d.setdefault('env', {})
        t, k = d['env'], key[4:]
    else:
        t, k = d, key
    if v is None:
        t.pop(k, None)
    else:
        t[k] = v


def apply_defaults(path, changes, backup_dir):
    """Backs up the settings file, writes real changes, records old values in <backup_dir>/defaults-state.json. Returns applied keys."""
    try:
        real = [c for c in changes if c[0] != 'MISSING']
        s = json.loads(_read(path) or '{}')
        os.makedirs(backup_dir, exist_ok=True)
        if os.path.exists(path):
            shutil.copy2(path, os.path.join(backup_dir, 'settings.json.bak'))
        for k, old, new in real:
            _setk(s, k, new)
        json.dump(s, open(path, 'w'), indent=2)
        json.dump({'path': path, 'applied': [[k, o, n] for k, o, n in real]}, open(os.path.join(backup_dir, 'defaults-state.json'), 'w'))
        return [k for k, _, _ in real]
    except Exception:
        return []


def restore_defaults(path, backup_dir):
    """Undo exactly the keys apply_defaults set (old value restored, or key removed)."""
    try:
        st = json.load(open(os.path.join(backup_dir, 'defaults-state.json')))
        s = json.loads(_read(path) or '{}')
        for k, old, new in st['applied']:
            _setk(s, k, old)
        if isinstance(s.get('env'), dict) and not s['env']:
            s.pop('env')
        json.dump(s, open(path, 'w'), indent=2)
        return [k for k, _, _ in st['applied']]
    except Exception:
        return []


# ---------- 11. unused MCP ----------
def _tool_uses(path):
    out = set()
    for l in _read(path).splitlines():
        if 'tool_use' not in l:
            continue
        try:
            d = json.loads(l); m = d.get('message')
            if isinstance(m, dict) and isinstance(m.get('content'), list):
                out |= {b['name'] for b in m['content'] if isinstance(b, dict) and b.get('type') == 'tool_use' and b.get('name')}
        except Exception:
            pass
    return out


def mcp_unused(transcript_paths, configured_servers, n_sessions=None):
    """-> {'unused': [...], 'tokens_est': {server: n}, 'advice': line}. Park command reused from tzondemand: `tz ondemand off NAME`."""
    try:
        n = n_sessions or _cfg('mcp_unused_sessions')
        paths = sorted((p for p in transcript_paths if os.path.isfile(p)), key=os.path.getmtime)[-n:]
        if len(paths) < n:
            return {'unused': [], 'tokens_est': {}, 'advice': ''}
        used = set().union(*[_tool_uses(p) for p in paths])
        unused = [s for s in configured_servers if not any(u.startswith('mcp__%s__' % s) for u in used)]
        try:
            import tztoolprune
            guess = tztoolprune.MCP_GUESS
        except Exception:
            guess = None
        est = {s: guess for s in unused} if guess else {}
        adv = ''
        if unused:
            adv = ('TOKEN ZOMBIE mcp: no use in the last %d chats: %s. Park: %s ; restore: tz ondemand on NAME (or tz ondemand rollback).'
                   % (n, ', '.join(unused), '; '.join('tz ondemand off ' + s for s in unused)))
        return {'unused': unused, 'tokens_est': est, 'advice': adv}
    except Exception:
        return {'unused': [], 'tokens_est': {}, 'advice': ''}


# ---------- 12. context breakdown ----------
def context_breakdown(transcript_path, home, cwd):
    r = {'system': 'UNKNOWN', 'tools': 'UNKNOWN', 'mcp': 'UNKNOWN', 'memory_files': 0, 'messages': 'UNKNOWN'}
    try:
        r['memory_files'] = instr_report(home, cwd)['total_est']
        last = 0
        for l in _read(transcript_path).splitlines():
            if '"usage"' not in l:
                continue
            try:
                u = (json.loads(l).get('message') or {}).get('usage') or {}
                t = sum(int(u.get(k) or 0) for k in ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens'))
                last = t or last
            except Exception:
                pass
        if last:
            r['messages'] = max(0, last - r['memory_files'])
    except Exception:
        pass
    return r


def render_breakdown(b):
    rows = ['%-13s %s' % (k, ('%s [est]' % v) if isinstance(v, int) else v) for k, v in b.items()]
    return '\n'.join(rows + ['Exact numbers: /context (breakdown), /cost (session cost), /usage (plan limits).'])


# ---------- 13. hook glue (called by tz-guard / tz-start) ----------
def _tail(path, size=400000):
    try:
        with open(path, 'rb') as f:
            f.seek(max(0, os.path.getsize(path) - size))
            return f.read().decode('utf-8', 'ignore').splitlines()
    except Exception:
        return []


def chat_size(path):
    """(latest main-chat input tokens, model). 0 tokens after a compaction until the next reply reports the new size."""
    for l in reversed(_tail(path)):
        if '"compact_boundary"' in l or '"isCompactSummary":true' in l.replace(' ', ''):
            return 0, ''
        if '"usage"' not in l:
            continue
        try:
            d = json.loads(l); m = d.get('message') or {}; u = m.get('usage') or {}
            t = sum(int(u.get(k) or 0) for k in ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens'))
        except Exception:
            continue
        if t and not d.get('isSidechain'):
            return t, str(m.get('model') or '')
    return 0, ''


def _state_path(sid=None):
    """One file for all sessions (per-session files piled up in the state dir); the last 50 sessions are kept."""
    return os.path.expanduser('~/.claude/token-zombie/tips.json')


def _all():
    try:
        d = json.load(open(_state_path()))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def load_state(sid):
    st = _all().get(str(sid))
    return st if isinstance(st, dict) else {}


def save_state(sid, st):
    try:
        d = _all()
        d.pop(str(sid), None)
        d[str(sid)] = st  # newest last; dicts keep insertion order
        for k in list(d)[:-50]:
            del d[k]
        os.makedirs(os.path.dirname(_state_path()), exist_ok=True)
        tmp = _state_path() + '.tmp%d' % os.getpid()
        json.dump(d, open(tmp, 'w'))
        os.replace(tmp, _state_path())
    except Exception:
        pass


def cap_block(data):
    """Block reason when feature size_cap is on and the chat is at the cap, else ''. Slash commands and the Fresh chat
    click always pass, so the way out is never blocked. The handoff is saved before the reason is returned."""
    import tzlib
    prompt = (data.get('prompt') or '').strip()
    if not tzlib.feature('size_cap') or prompt.startswith('/') or re.fullmatch(r'(?i)fresh chat[.!]?', prompt):
        return ''
    n = chat_size(data.get('transcript_path'))[0]
    tier, msg = size_gate(n)
    if tier != 'block':
        return ''
    cwd = data.get('cwd') or os.getcwd()
    p = save_handoff(cwd, 'auto-saved at the size cap: chat %d tokens, session %s.\nChat log: %s\nNext: read this file, check git status, continue.'
                     % (n, data.get('session_id', 'x'), data.get('transcript_path')))
    if p:
        msg = 'TOKEN ZOMBIE: chat is %d tokens: /clear now; handoff saved to %s.' % (n, p)
    else:
        msg = 'TOKEN ZOMBIE: chat is %d tokens: handoff could NOT be saved; run `tz handoff save`, then /clear.' % n
    return msg + (' Your last message was not sent. Turn this cap off: TZ_FEAT_SIZE_CAP=0, or "features": {"size_cap": 0} '
                  'in ~/.claude/token-zombie/config.json.')


def prompt_tips(data, home=None):
    """Advice lines for one UserPromptSubmit. Each speaks at most once per chat (size: once per tier; paste: each time;
    task switch: each detected switch)."""
    import tzlib
    on = tzlib.feature
    sid, prompt = data.get('session_id', 'x'), data.get('prompt') or ''
    st = load_state(sid); said = set(st.get('said', [])); out = []

    def once(key, text):
        if text and key not in said:
            said.add(key); out.append(text)

    n, model = chat_size(data.get('transcript_path'))
    if on('size_gate'):
        tier, msg = size_gate(n, {'size_cap': 0})
        if tier != 'ok':
            once(tier, msg)
    prev = st.get('prev', [])
    if on('task_switch') and task_switch(prompt, prev):
        out.append('TOKEN ZOMBIE task switch: this looks unrelated to the earlier work. Before carrying the old context, offer '
                   'a fresh start: a new-session card, or a "Fresh chat" button (write the handoff first). If it is a follow-up, ignore this.')
    kept = ' '.join(sorted(_words(prompt) | _paths(prompt)))[:600]  # words and paths only, never the raw prompt
    if len(kept.split()) >= 3:
        st['prev'] = (prev + [kept])[-3:]
    if on('home_cwd') and 'home' not in said:
        once('home', home_cwd(data.get('cwd') or os.getcwd(), home or os.path.expanduser('~')))
    if on('paste_warn'):
        w = paste_warn(prompt)
        if w:
            out.append(w)
    if on('small_msgs'):
        st['lens'] = (st.get('lens', []) + [len(prompt.strip())])[-8:]
        if 'small' not in said and small_msgs(st['lens']):
            once('small', small_msgs(st['lens']))
    if on('archive_advice'):
        once('archive', archive_advice(prompt))
    if on('model_advice') and model:
        once('model', model_advice(prompt, model))
    if on('plan_advice') and data.get('permission_mode') != 'plan':
        once('plan', plan_advice(prompt))
    if on('instr_advice') and 'instr' not in said:  # normally said by tz-start; this covers chats it did not see
        said.add('instr')
        a = instr_advice(instr_report(home or os.path.expanduser('~'), data.get('cwd') or os.getcwd()))
        if a:
            out.append(a)
    st['said'] = sorted(said)
    save_state(sid, st)
    return '\n'.join(out)


def start_tips(data, home=None):
    """SessionStart lines: instruction-file report, and (opt-in) a one-time-ever defaults offer."""
    import tzlib
    home = home or os.path.expanduser('~')
    sid, out = data.get('session_id', 'x'), []
    if tzlib.feature('instr_advice'):
        st = load_state(sid)
        if 'instr' not in st.get('said', []):
            a = instr_advice(instr_report(home, data.get('cwd') or os.getcwd()))
            if a:
                out.append(a)
            st['said'] = st.get('said', []) + ['instr']
            save_state(sid, st)
    flag = os.path.join(home, '.claude', 'token-zombie', 'defaults-offered')
    if tzlib.feature('defaults_advice') and not os.path.exists(flag):
        try:
            plan = [c for c in defaults_plan(json.loads(_read(os.path.join(home, '.claude', 'settings.json')) or '{}'), {}) if c[0] != 'MISSING']
            if plan:
                os.makedirs(os.path.dirname(flag), exist_ok=True)
                open(flag, 'w').write('1')
                out.append('TOKEN ZOMBIE defaults: cheaper defaults available (%s). Show the owner the diff with `tz defaults`; '
                           'run `tz defaults apply --yes` only after their yes (undo: `tz defaults restore`).' % ', '.join(c[0] for c in plan))
        except Exception:
            pass
    return '\n'.join(out)


def bulk_gate(data):
    """Deny reason for the next Read/Grep/Glob after a run of them in the main chat (feature bulk_read_block). One deny,
    then the next bulk_read_n such calls pass, so it can never lock the work out. Subagents are never blocked."""
    import tzlib
    if not tzlib.feature('bulk_read_block') or data.get('agent_id') or data.get('tool_name') not in READS:
        return ''
    sid = data.get('session_id', 'x')
    streak = bulk_reads(_tail(data.get('transcript_path')))
    st = load_state(sid)
    left = st.get('bulk_left', 0)
    if not streak:
        if left:
            st['bulk_left'] = 0; save_state(sid, st)
        return ''
    st['bulk_left'] = left - 1 if left > 0 else int(_cfg('bulk_read_n'))
    save_state(sid, st)
    return '' if left > 0 else bulk_block_msg()


# ---------- 14. CLI ----------
def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    home, cwd = os.path.expanduser('~'), os.getcwd()
    bk = os.path.join(home, '.claude', 'token-zombie', 'tips-backups')
    try:
        c = a[0] if a else ''
        if c == 'instr':
            rep = instr_report(home, cwd)
            if '--fix' not in a:
                for f in rep['files']:
                    print('%6d  %-6s %s' % (f['tokens_est'], 'loaded' if f['loaded'] else 'no', f['path']))
                print('total %d tokens [est]' % rep['total_est'])
                for s in rep['biggest_sections']:
                    print('  section %-30s %d [est]' % (s['heading'][:30], s['tokens_est']))
                for s in rep['skill_candidates']:
                    print('  could be a skill:', s['heading'])
                print(instr_advice(rep, 0))
            elif '--restore' in a:
                print('restored %d file(s)' % instr_restore(bk))
            else:
                plan = instr_fix(rep, apply='--apply' in a, backup_dir=bk)
                for p in plan:
                    print(p.get('action'), p.get('path', ''), p.get('note', ''))
                if not plan:
                    print('nothing to fix')
                if '--apply' not in a:
                    print('dry run; add --apply to write (backups first), --restore to undo')
        elif c == 'defaults':
            sp = os.path.join(home, '.claude', 'settings.json')
            if '--restore' in a:
                print('restored:', restore_defaults(sp, bk))
            else:
                plan = defaults_plan(json.loads(_read(sp) or '{}'), {})
                for k, o, n in plan:
                    print(k, o, '->', n)
                if '--apply' in a:
                    if '--yes' not in a:
                        print('add --yes to confirm')
                        return 1
                    print('applied:', apply_defaults(sp, plan, bk))
        elif c == 'breakdown':
            tp = a[1] if len(a) > 1 else ''
            print(render_breakdown(context_breakdown(tp, home, cwd)))
        elif c == 'mcp-unused':
            proj = os.path.join(home, '.claude', 'projects')
            tr = [os.path.join(dp, f) for dp, _, fs in os.walk(proj) for f in fs if f.endswith('.jsonl')] if os.path.isdir(proj) else []
            cj = json.loads(_read(os.path.join(home, '.claude.json')) or '{}')
            print(mcp_unused(tr, list((cj.get('mcpServers') or {}).keys()))['advice'] or 'no unused MCP servers found')
        else:
            print('usage: tz tips instr [--fix [--apply|--restore]] | defaults [--apply --yes|--restore] | breakdown [transcript] | mcp-unused')
        return 0
    except Exception as e:
        print('tips error:', e)
        return 1


if __name__ == '__main__':
    sys.exit(main())
