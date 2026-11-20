# tz mode: show or set the mode profile (off|lite|full|ultra) in ~/.claude/token-zombie/config.json.
import json, os, sys, time
from tzlib import PROFILES, DEFAULTS, ADVICE, cfg, mode, _conf

KEYS = ('limit', 'hard', 'read_warn', 'plan_warn', 'plan_stop')


def show():
    m = mode()
    print(f'mode = {m}')
    for k in KEYS:
        env, exp, prof = os.environ.get(f'TZ_{k.upper()}'), _conf.get(k), PROFILES[m].get(k)
        src = 'env' if env else 'config.json (explicit, overrides profile)' if exp else f'{m} profile' if prof else 'default'
        print(f'{k} = {cfg(k)} ({src})')
    on = PROFILES[m]['advice']
    print('advice on:  ' + (', '.join(on) or 'none'))
    print('advice off: ' + (', '.join(a for a in ADVICE if a not in on) or 'none'))
    print('always on: hard-limit handoff warning, plan_stop, quarantine, errors.log, vet HIGH')
    return 0


def main(args):
    if not args:
        return show()
    m = args[0].lower()
    if len(args) > 1 or m not in PROFILES:
        print('usage: tz mode [off|lite|full|ultra]', file=sys.stderr)
        return 2
    p = os.path.expanduser('~/.claude/token-zombie/config.json')
    conf = {}
    if os.path.exists(p):
        try:
            conf = json.load(open(p))
        except Exception:
            conf = None
        if not isinstance(conf, dict):
            print(f'tz mode: {p} is not a JSON object; refusing to touch it', file=sys.stderr)
            return 1
        open(f'{p}.bak-mode-{time.strftime("%Y%m%d-%H%M%S")}', 'w').write(open(p).read())
    os.makedirs(os.path.dirname(p), exist_ok=True)
    conf['mode'] = m
    tmp = p + '.tmp'
    json.dump(conf, open(tmp, 'w'), indent=2)
    os.replace(tmp, p)
    print(f'mode set to {m}')
    over = [k for k in KEYS if conf.get(k)]
    if over:
        print('note: explicit config.json keys override the profile: ' + ', '.join(f'{k}={conf[k]}' for k in over))
    return 0
