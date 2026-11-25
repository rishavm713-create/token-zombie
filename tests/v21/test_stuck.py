# tzstuck + tzagent v2.1 tests. Parity cases follow OpenHands tests/cross/test_stuck_detector.py (MIT):
# history_too_short, repeating_action_observation_not_stuck_less_than_4_repeats / _stuck, repeating_action_error_nudges_before_stuck,
# agent_monologue_stuck, not_stuck_with_different_actions, reset_after_user_message, is_stuck_uses_only_recent_event_window.
import os, sys, json, time, tempfile, subprocess
from harness import ok, done, Z
H = tempfile.mkdtemp(); os.environ['HOME'] = H; os.environ['TZ_FEAT_STUCK_DETECT'] = '1'
os.environ['USERPROFILE'] = os.environ['HOME']  # Windows expanduser reads this one
import tzstuck, tzagent
tzagent.STATE = os.path.join(H, '.claude', 'token-zombie')
S = [0]


def sid():
    S[0] += 1; return 's%d' % S[0]


def ev(s, tool='Bash', cmd='ls', out='a b', err=False):
    d = dict(session_id=s, tool_name=tool, tool_input={'command': cmd}, hook_event_name='PostToolUse')
    d['tool_response'] = {'is_error': True, 'content': out} if err else {'stdout': out}
    return tzstuck.check(d)


def msg(s):
    return tzstuck.check(dict(session_id=s, hook_event_name='Stop'))


s = sid(); r = [ev(s) for _ in range(3)]
ok('too short / 3 identical pairs -> silent (not_stuck_less_than_4_repeats)', r == ['', '', ''])
ok('4th identical pair -> stuck', 'stuck' in ev(s) and len(r) == 3)
ok('stuck speaks once per streak', ev(s) == '')
ok('streak broken then repeated speaks again', (ev(s, cmd='pwd'), [ev(s) for _ in range(3)], 'stuck' in ev(s))[2])
s = sid(); out = [ev(s, cmd='invalid_command', out="Command 'invalid_command' not found", err=True) for _ in range(4)]
ok('error x1,x2 silent', out[0] == out[1] == '')
ok('error x3 nudges with tool + error text', 'Bash' in out[2] and "invalid_command" in out[2] and 'stuck' not in out[2])
ok('error x4 stuck', 'stuck' in out[3])
ok('advice <= 200 chars', all(len(x) <= 200 for x in out))
s = sid(); ok('monologue x3 -> stuck', (msg(s), msg(s), 'no tool use' in msg(s))[2])
s = sid(); ok('different actions not stuck', all(ev(s, cmd='c%d' % i, out='o%d' % i) == '' for i in range(8)))
s = sid(); [ev(s) for _ in range(4)]
ok('user message resets', tzstuck.check(dict(session_id=s, hook_event_name='UserPromptSubmit')) == '' and ev(s) == '')
ok('after reset one different pair still silent', ev(s, cmd='pwd', out='/x') == '')
s = sid(); r = [ev(s, cmd='A' if i % 2 == 0 else 'B', out='oA' if i % 2 == 0 else 'oB') for i in range(6)]
ok('alternating A,B x6 -> stuck at 6th only', r[:5] == [''] * 5 and 'alternating' in r[5])
s = sid(); [ev(s) for _ in range(4)]
r = [ev(s, cmd='x%d' % i, out='y%d' % i) for i in range(20)]
ok('only recent window matters (old loop gone)', all(x == '' for x in r))
s = sid(); ok('timestamps in output normalised', [ev(s, out='t 2026-01-0%dT10:00:00Z' % i) for i in range(1, 4)] == ['', '', ''] and 'stuck' in ev(s, out='t 2026-01-09T10:00:00Z'))
os.environ['TZ_FEAT_STUCK_DETECT'] = '0'; s = sid()
ok('feature off -> silent', all(ev(s) == '' for _ in range(5)))
os.environ['TZ_FEAT_STUCK_DETECT'] = '1'
ok('state file written atomically, no tmp left', os.listdir(os.path.join(H, '.claude', 'token-zombie')) and not [f for f in os.listdir(os.path.join(H, '.claude', 'token-zombie')) if f.startswith('.stuck')])
# tzagent
ok('alive(self)', tzagent.alive(os.getpid()))
ok('alive(1) true (PermissionError = exists)', tzagent.alive(1))
ok('alive(dead) false', not tzagent.alive(2 ** 22 + 12345))
ok('claim fresh', tzagent.claim('t1', ['a.py']) == [])
ok('claim clash', tzagent.claim('t2', ['a.py', 'b.py']) == ['a.py'] and not os.path.exists(tzagent._cpath('b.py')))
ok('same task renews', tzagent.claim('t1', ['a.py']) == [])
ok('owners.json mirror for tzgate', json.load(open(tzagent.owners_path())) == {'a.py': 't1'})
tzagent.release('t1'); ok('release frees', tzagent.claim('t2', ['a.py']) == [])
ok('expired lease reclaimed', tzagent.claim('t3', ['a.py'], now=time.time() + tzagent.LEASE + 5) == [])
ok('force takes over', tzagent.claim('t4', ['a.py'], force=True) == [])
os.makedirs(os.path.join(H, 'w')); fake = os.path.join(H, 'fake')
open(fake, 'w').write("#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps({'type':'assistant','message':{'id':'m','usage':{'input_tokens':5,'output_tokens':1}}}))\nprint(json.dumps({'type':'result','result':'x'}))\nsys.exit(1)\n")
os.chmod(fake, 0o755); os.environ['CLAUDE_BIN'] = fake
rid, rows, sp, m = tzagent.run('t', os.path.join(H, 'w'), wall=1e-9)
ok('wall limit stops before first call', rows[0]['status'] == 'wall' and len(rows) == 1)
rid, rows, sp, m = tzagent.run('t2', os.path.join(H, 'w'), max_errors=2)
ok('max-errors 2', [r['status'] for r in rows] == ['error', 'error', 'errors'])
rid, rows, sp, m = tzagent.run('t3', os.path.join(H, 'w'))
ok('no limits: unchanged behaviour (error stops run)', rows[-1]['status'] == 'error')
done()
