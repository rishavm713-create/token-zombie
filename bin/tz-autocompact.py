#!/usr/bin/env python3
"""Opt-in: set Claude Code auto-compact size.
Shows the exact change, asks y/N, backs up settings.json, then applies it.
Usage: python3 bin/tz-autocompact.py [tokens] [--yes] [--dry-run]   (default 150000)
Applies to NEW chats only. Nothing is changed unless you answer y (or pass --yes).
"""
import json, os, shutil, sys, time

args = sys.argv[1:]
yes, dry = '--yes' in args, '--dry-run' in args
nums = [a for a in args if a.isdigit()]
n = nums[0] if nums else '150000'
if not 50000 <= int(n) <= 1000000:
    sys.exit('tokens must be between 50000 and 1000000')
p = os.path.join(os.environ.get('CLAUDE_CONFIG_DIR') or os.path.expanduser('~/.claude'), 'settings.json')
want = {'CLAUDE_CODE_AUTO_COMPACT_WINDOW': n, 'CLAUDE_AUTOCOMPACT_PCT_OVERRIDE': '100'}

print(f'This will edit {p} (a backup is made first) and set in its "env" block:')
for k, v in want.items():
    print(f'  {k} = "{v}"')
print(f'Claude Code then compacts a chat at about {n} tokens. New chats only.')
if dry:
    sys.exit('dry run: nothing changed.')
if not yes and input('Apply? [y/N] ').strip().lower() not in ('y', 'yes'):
    sys.exit('nothing changed.')

s = {}
if os.path.exists(p):
    s = json.load(open(p))  # a broken file raises: we never overwrite what we cannot read
    shutil.copy2(p, f"{p}.bak-tz-compact-{time.strftime('%Y%m%d-%H%M%S')}")
s.setdefault('env', {}).update(want)
tmp = p + '.tz-tmp'
json.dump(s, open(tmp, 'w'), indent=2)
json.load(open(tmp))  # read-back check before swapping in
os.replace(tmp, p)
print('done. Open a new chat for it to take effect.')
