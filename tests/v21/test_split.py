# auto_split: a prompt with several independent tasks gets "start parallel sessions now" (on) or proposal cards (off).
import os
from harness import ok, done
import tzsplit as g
ts = ['fix the install tests', 'write the docs', 'run the benchmark']

os.environ['TZ_FEAT_AUTO_SPLIT'] = '1'
on = g.split_hint(ts)
ok('on: starts sessions now', 'user_asked' in on and 'NOW' in on)
ok('on: subagents inside, test once, push gated', 'subagents' in on and 'test once' in on and 'owner OK' in on)
ok('on: plan listed', 'tz split "fix the install tests"' in on)
os.environ['TZ_FEAT_AUTO_SPLIT'] = '0'
off = g.split_hint(ts)
ok('off: proposal cards only', 'own_initiative' in off and 'user_asked' not in off)
os.environ.pop('TZ_FEAT_AUTO_SPLIT')
done()
