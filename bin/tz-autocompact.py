#!/usr/bin/env python3
"""Opt-in: set Claude Code auto-compact size.
Shows the exact change, asks y/N, backs up settings.json, then applies it.
Usage: python3 bin/tz-autocompact.py [tokens] [--yes] [--dry-run] [--force]   (default 200000)
Applies to NEW chats only. Nothing is changed unless you answer y (or pass --yes).
"""
import json, os, shutil, sys, time

args = sys.argv[1:]
yes, dry = '--yes' in args, '--dry-run' in args
nums = [a for a in args if a.isdigit()]
n = nums[0] if nums else '200000'
if not 50000 <= int(n) <= 1000000:
    sys.exit('tokens must be between 50000 and 1000000')
# Claude compacts about 32k BELOW this number. If your base context (system prompt, skills, MCP tools, CLAUDE.md) is already near
# that point, every message re-triggers compaction ("Context window was full" loop). So low values need --force.
if int(n) < 200000 and '--force' not in args:
    sys.exit(f'{n} is below 200000: on a machine with many skills/MCP tools this can make Claude compact on every message. '
             'Use 200000 or more, or add --force if you know your base context is small.')
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
