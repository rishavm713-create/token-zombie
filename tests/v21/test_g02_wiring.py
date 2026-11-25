# group 2 hooks reach the single dispatcher, and stay silent with the switch off
import json, os, tempfile
from harness import ok, done, guard

for k in ('TZ_FEAT_GIT_GUARD', 'TZ_FEAT_UNVERIFIED_CLAIM', 'TZ_FEAT_MICRO_SKILLS'):
    os.environ.pop(k, None)
home = tempfile.mkdtemp()
bash = {'hook_event_name': 'PreToolUse', 'session_id': 'g2w', 'tool_name': 'Bash', 'cwd': home,
        'tool_input': {'command': 'git push origin main'}}


def out(payload, env=None, _n=[0]):
    _n[0] += 1  # distinct payload per run: the dispatcher drops an identical event seen twice (dup_hook)
    return json.dumps(guard(dict(payload, tool_use_id='t%d' % _n[0]), env or {}, home)[0])


off = out(bash)
ok('git_guard off by default: no deny', 'git guard' not in off)
on = out(bash, {'TZ_FEAT_GIT_GUARD': '1'})
ok('git_guard on: dispatcher denies push', 'deny' in on and 'git guard' in on)

tp = os.path.join(home, 't.jsonl')
with open(tp, 'w') as f:
    f.write(json.dumps({'type': 'user', 'uuid': 'u1', 'message': {'role': 'user', 'content': 'fix it'}}) + '\n')
stop = {'hook_event_name': 'Stop', 'session_id': 'g2w', 'transcript_path': tp, 'cwd': home,
        'last_assistant_message': 'All tests pass now.'}
ok('unverified_claim off by default', 'systemMessage' not in out(stop) or 'claim' not in out(stop).lower())
ok('unverified_claim on: Stop advice emitted', 'systemMessage' in out(stop, {'TZ_FEAT_UNVERIFIED_CLAIM': '1'}))

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'bin'))
import tzlib
for n in ('git_guard', 'unverified_claim', 'micro_skills', 'rtk_filters'):
    ok(n + ' registered, default off', tzlib.FEATURES.get(n) == 0)
for fn, name in (('tz-guard.py', 'tzfacts.session_end'), ('tz-start.py', 'tzfacts.session_start')):
    ok(name + ' called by ' + fn, name in open(os.path.join(os.path.dirname(__file__), '..', '..', 'bin', fn)).read())
done()
