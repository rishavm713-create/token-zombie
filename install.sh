#!/bin/bash
# Token-zombie installer: wires guard (prompt/tool/stop/session-end/precompact), lean-start, compaction-note and statusline hooks into ~/.claude/settings.json.
# Safe by design: backs up settings first, refuses unparseable/odd-shaped settings or config, atomic write + re-read verification (auto-restores on mismatch),
# idempotent, touches only commands containing token-zombie/bin/ (or the old chat-size-guard.py). Flags: --dry-run | --uninstall | --restore | --check
# | --statusline-only (sets only statusLine; for the plugin install, whose hooks come from hooks/hooks.json)
# Test hook: TZ_INSTALL_CRASH=1 kills the installer right before the final replace (simulates power loss).
DIR="$(cd "$(dirname "$0")" && pwd)"
SET="$HOME/.claude/settings.json"
if [ "${1:-}" = --restore ]; then
  # newest backup that does NOT already contain token-zombie hooks (a backup made by a repeated install holds them)
  B=""; for f in $(ls -t "$SET".bak-tz-* 2>/dev/null); do grep -q 'token-zombie/bin' "$f" || { B="$f"; break; }; done
  [ -n "$B" ] || { echo "no pre-install backup found next to $SET"; exit 1; }
  python3 -c "import json,sys;json.load(open(sys.argv[1]))" "$B" 2>/dev/null || { echo "backup $B is not valid JSON; not restoring"; exit 1; }
  { [ ! -f "$SET" ] || cp "$SET" "$SET.before-restore"; } && cp "$B" "$SET" && echo "restored $B (previous state kept as $SET.before-restore)"; exit 0
fi
MODE="${1:-}"
python3 - "$SET" "$DIR" "$MODE" <<'PY'
import json, os, shutil, sys, time
path, d, mode = sys.argv[1], sys.argv[2], sys.argv[3]
conf_p = os.path.expanduser('~/.claude/token-zombie/config.json')
dry, check, slo = mode == '--dry-run', mode == '--check', mode == '--statusline-only'
die = lambda m: sys.exit(m)
for stale in (path + '.tz-tmp', conf_p + '.tz-tmp'):  # leftovers of an interrupted run
    if not dry and not check and os.path.exists(stale):
        os.remove(stale)
try:
    s = json.load(open(path)) if os.path.exists(path) else {}
except Exception as e:
    die(f'settings.json is not valid JSON ({e}); nothing changed. Fix it or restore a backup first.')
if not isinstance(s, dict) or not isinstance(s.get('hooks', {}), dict):
    die('settings.json has an unexpected shape (not an object / hooks not an object); nothing changed.')
try:
    conf = json.load(open(conf_p)) if os.path.exists(conf_p) else {}
    assert isinstance(conf, dict)
except Exception as e:
    die(f'{conf_p} is not a valid JSON object ({e}); nothing changed. Fix or move it first.')
h = s.setdefault('hooks', {})
for ev, gs in h.items():
    if not isinstance(gs, list) or not all(isinstance(g, dict) and isinstance(g.get('hooks', []), list) for g in gs):
        die(f'hooks.{ev} has an unexpected shape; nothing changed.')
before = json.dumps(s, indent=2, sort_keys=True).splitlines()
guard, start, status, compact = (f'python3 "{d}/bin/{n}"' for n in ('tz-guard.py', 'tz-start.py', 'tz-status.py', 'tz-compact.py'))
EVENTS = ('UserPromptSubmit', 'PostToolUse', 'PreToolUse', 'SessionStart', 'PreCompact', 'Stop', 'SessionEnd')
mine = lambda c: 'token-zombie/bin/' in c or 'chat-size-guard.py' in c


def installed():
    return sorted(ev for ev, gs in h.items() if any(mine(x.get('command', '')) for g in gs for x in g.get('hooks', [])))


if check:
    sl = 'tz-status.py' in s.get('statusLine', {}).get('command', '')
    print(f"installed events: {', '.join(installed()) or 'none'}; statusline: {'tz' if sl else 'not tz'}")
    sys.exit(0)
for ev in ([] if slo else list(h)):  # drop only our own commands; keep foreign hooks, even inside the same group
    groups = []
    for g in h[ev]:
        g['hooks'] = [x for x in g.get('hooks', []) if not mine(x.get('command', ''))]
        if g['hooks']:
            groups.append(g)
    if groups:
        h[ev] = groups
    else:
        h.pop(ev)
if mode == '--uninstall':
    sl = s.get('statusLine', {})
    if 'tz-status.py' in sl.get('command', ''):
        if conf.get('prev_statusline'):
            s['statusLine'] = {'type': 'command', 'command': conf['prev_statusline']}
        else:
            s.pop('statusLine', None)
        conf.pop('prev_statusline', None)
    if not h:
        s.pop('hooks', None)
    msg = 'token-zombie removed (old chat-size-guard not restored; use the settings backup if you want it)'
else:
    plan = (('UserPromptSubmit', None, guard), ('PostToolUse', '', guard), ('PreToolUse', 'Read', guard), ('SessionStart', None, start),
            ('PreCompact', None, guard), ('PreCompact', None, compact), ('Stop', None, guard), ('SessionEnd', None, guard))
    for ev, m, cmd in (() if slo else plan):
        g = {'hooks': [{'type': 'command', 'command': cmd, 'timeout': 5}]}
        if m is not None:
            g['matcher'] = m
        h.setdefault(ev, []).append(g)
    cur = s.get('statusLine', {}).get('command', '') if isinstance(s.get('statusLine'), dict) else ''
    if 'tz-status.py' not in cur:
        conf['prev_statusline'] = cur
    s['statusLine'] = {'type': 'command', 'command': status}
    msg = 'token-zombie statusline set (hooks come from the plugin).' if slo else 'token-zombie installed: guard + supervisor (prompt/tool/stop/session-end/precompact), pack hints, lean start, compaction note, statusline. Open a new chat to see it.'
if dry:
    import difflib
    print('\n'.join(difflib.unified_diff(before, json.dumps(s, indent=2, sort_keys=True).splitlines(), 'settings.json now', 'settings.json after', lineterm='', n=1)))
    print('DRY RUN: nothing written.')
    sys.exit(0)
try:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    os.makedirs(os.path.dirname(conf_p), exist_ok=True)
    bak = None
    if os.path.exists(path):
        bak = f"{path}.bak-tz-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"
        shutil.copy2(path, bak)
    tmp = path + '.tz-tmp'  # atomic: write temp, verify it parses, then replace
    json.dump(s, open(tmp, 'w'), indent=2)
    assert json.load(open(tmp)) == s
    if os.environ.get('TZ_INSTALL_CRASH'):
        os._exit(9)
    ctmp = conf_p + '.tz-tmp'
    json.dump(conf, open(ctmp, 'w'))
    os.replace(tmp, path)
    os.replace(ctmp, conf_p)
    if json.load(open(path)) != s:  # read-back mismatch: put the backup back
        raise RuntimeError('read-back mismatch')
except Exception as e:
    if bak and os.path.exists(bak):
        shutil.copy2(bak, path)
    for t in (path + '.tz-tmp', conf_p + '.tz-tmp'):
        if os.path.exists(t):
            os.remove(t)
    die(f'install failed ({type(e).__name__}: {e}); settings left as before.')
print(msg)
PY
