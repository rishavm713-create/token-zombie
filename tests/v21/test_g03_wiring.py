# group 3: every command is reachable through bin/tz and the hooks run through the one dispatcher.
import json, os, subprocess, sys, tempfile
from harness import ok, done, Z
sys.path.insert(0, os.path.join(Z, 'bin'))
import tzlib

H = tempfile.mkdtemp()
env = dict(os.environ, HOME=H, TZ_DEDUPE='0')
run = lambda a, i='', e=None: subprocess.run([sys.executable, *a], input=i, capture_output=True, text=True, env=dict(env, **(e or {})), cwd=H)
tz = os.path.join(Z, 'bin', 'tz')
for args in (['budget'], ['line', 'preview'], ['squad', 'list'], ['obs', 'sessions'], ['ts', 'doctor'], ['stale', '-h'],
             ['memsearch', '-h'], ['read', tz, 'lines', '1-2'], ['skills', 'check', os.path.join(Z, 'skills', 'tz-craft')]):
    r = run([tz, *args])
    ok('tz ' + ' '.join(args[:2]), 'unknown command' not in r.stderr and 'Traceback' not in r.stderr and r.returncode in (0, 1))
ok('opt-in switches default off', not any(tzlib.FEATURES[k] for k in ('budget_block', 'stale_block', 'obs_record', 'obs_file_context', 'obs_inject', 'line_custom_command')))

repo = os.path.realpath(tempfile.mkdtemp())  # real cwds arrive resolved (macOS /var is a symlink)
git = lambda *a: subprocess.run(['git', '-C', repo, '-c', 'user.name=t', '-c', 'user.email=t@example.com', *a], capture_output=True, check=True)
git('init', '-q', '-b', 'main'); git('commit', '-q', '--allow-empty', '-m', 'one'); git('checkout', '-q', '-b', 'work')
git('checkout', '-q', 'main'); git('commit', '-q', '--allow-empty', '-m', 'two'); git('checkout', '-q', 'work')
ev = lambda sid: json.dumps({'hook_event_name': 'PreToolUse', 'session_id': sid, 'tool_name': 'Bash', 'tool_input': {'command': 'pytest'}, 'cwd': repo})
guard = os.path.join(Z, 'bin', 'tz-guard.py')
ok('hook: stale warn', 'stale branch' in run([guard], ev('a')).stdout)
ok('hook: stale off switch', 'stale branch' not in run([guard], ev('b'), {'TZ_FEAT_STALE_WARN': '0'}).stdout)
ok('hook: stale block opt-in', '"deny"' in run([guard], ev('c'), {'TZ_FEAT_STALE_BLOCK': '1'}).stdout)

post = json.dumps({'hook_event_name': 'PostToolUse', 'session_id': 'o', 'tool_name': 'Edit', 'tool_input': {'file_path': os.path.join(repo, 'a.py'), 'new_string': 'def zed(): pass'}, 'cwd': repo})
obs = lambda: subprocess.run([sys.executable, tz, 'obs', 'recent'], capture_output=True, text=True, env=env, cwd=repo).stdout
run([guard], post)
ok('hook: obs off by default', 'a.py' not in obs())
run([guard], post, {'TZ_FEAT_OBS_RECORD': '1'})
ok('hook: obs records when on', 'a.py' in obs())
done()
