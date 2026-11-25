# superpowers integration: unverified_claim advice (F-safety spec + upstream verification table) and craft refs.
import glob, json, os, re, subprocess, sys, tempfile
from harness import ok, done, Z
import tzclaim as C


def sh(cmd, good=True):
    return {'name': 'Bash', 'input': {'command': cmd}, 'ok': good}


def ed(f='a.py'):
    return {'name': 'Edit', 'input': {'file_path': f}, 'ok': True}


AG = {'name': 'Agent', 'input': {'subagent_type': 'general-purpose'}, 'ok': True}
fires = lambda text, calls=(): bool(C.judge(text, list(calls)))

# research spec examples (docs/research/F-safety.md section 3)
ok('tests pass, no run', fires('All tests pass'))
ok('done after test script', not fires('Done', [ed(), sh('bash tests/test_x.sh')]))
ok('should work', fires('should work'))
# upstream table: claim -> required evidence / not sufficient
ok('previous run is not enough', fires('All tests pass.', [sh('pytest -q'), ed()]))
ok('failed run is not evidence', 'failed' in C.judge('Fixed the bug.', [ed(), sh('pytest', False)]))
ok('rerun after failure clears', not fires('Fixed.', [ed(), sh('pytest', False), ed(), sh('pytest')]))
ok('agent report not trusted', 'delegated' in C.judge('Done.', [AG]))
ok('agent + diff ok', not fires('Done.', [AG, sh('git diff --stat')]))
ok('diff does not prove tests', fires('All tests pass.', [AG, sh('git diff')]))
ok('diff does not back own edit', fires('Done.', [ed(), sh('git diff')]))
ok('red flag after edit', fires('Great, it is fixed!', [ed()]))
# false-positive guards
for t in ('This is not done yet.', 'Fixed, but not verified.', 'Are all tests passing?', 'I will report once the tests pass.',
          "I haven't fixed it.", 'Here is the plan.', 'The `done` flag is set.', '```\nall tests pass\n```'):
    ok(f'silent {t!r}', not fires(t, [ed()]))
ok('hedge elsewhere does not hide', fires('I did not touch docs. All tests pass.'))
ok('done with no change silent', not fires('Done reading, here is the summary.'))
ok('docs edit silent', not fires('Done.', [ed('README.md')]))
ok('read-only agent silent', not fires('Done.', [{'name': 'Agent', 'input': {'subagent_type': 'Explore'}, 'ok': True}]))
for cmd in ('pytest -q', 'cd x && npm run build', 'python3 -m pytest tests', 'python3 tests/v21/test_craft.py', 'CI=1 rtk cargo test',
            'bash tests/run_all.sh', './gradlew test', 'make', 'tz verify', 'uv run ruff check .', 'go vet ./...'):
    ok(f'check {cmd!r}', C.is_check(cmd))
for cmd in ('ls tests/', 'grep pytest requirements.txt', 'cat tests/test_x.sh', 'git commit -m "make test pass"', 'makefile-lint'):
    ok(f'not check {cmd!r}', not C.is_check(cmd))

# transcript parsing + Stop entry point
tmp = tempfile.mkdtemp()
os.environ['HOME'] = tmp
tp = os.path.join(tmp, 't.jsonl')


def write(*rows):
    with open(tp, 'w') as f:
        f.write('not json\n' + ''.join(json.dumps(r) + '\n' for r in rows))


user = lambda u, c: {'type': 'user', 'uuid': u, 'message': {'content': c}}
asst = lambda *b: {'type': 'assistant', 'message': {'content': list(b)}}
use = lambda i, n, inp: {'type': 'tool_use', 'id': i, 'name': n, 'input': inp}
res = lambda i, err: user('r' + i, [{'type': 'tool_result', 'tool_use_id': i, 'is_error': err}])
say = lambda s: asst({'type': 'text', 'text': s})
base = [user('u0', 'old'), asst(use('0', 'Bash', {'command': 'pytest'})), res('0', False),
        user('u1', 'fix it'), asst(use('1', 'Edit', {'file_path': 'a.py'})), res('1', False)]
write(*base, say('Fixed.'))
t = C.turn(tp)
ok('turn starts at last user message', t['id'] == 'u1' and [c['name'] for c in t['calls']] == ['Edit'] and t['text'] == 'Fixed.')
d = {'session_id': 's1', 'transcript_path': tp, 'hook_event_name': 'Stop'}
os.environ['TZ_FEAT_UNVERIFIED_CLAIM'] = '0'
ok('feature off silent', C.stop_advice(d) == '')
os.environ['TZ_FEAT_UNVERIFIED_CLAIM'] = '1'
m = C.stop_advice(d)
ok('advises', 'unverified_claim' in m and 'TOKEN ZOMBIE' in m)
ok('advice short', 0 < len(m.split()) <= 30)
ok('once per turn', C.stop_advice(d) == '')
ok('payload reply preferred', C.stop_advice(dict(d, session_id='s2', last_assistant_message='Looking now.')) == '')
write(*base, asst(use('2', 'Bash', {'command': 'pytest'})), res('2', True), say('Fixed.'))
ok('error result read', 'failed' in C.stop_advice(dict(d, session_id='s3')))
write(*base, asst(use('2', 'Bash', {'command': 'pytest'})), res('2', False), say('Fixed.'))
ok('good run silent', C.stop_advice(dict(d, session_id='s4')) == '')
ok('missing transcript silent', C.stop_advice({'transcript_path': '/nonexistent'}) == '')
write(*base, say('Fixed.'))
cli = lambda *a: subprocess.run([sys.executable, os.path.join(Z, 'bin', 'tzclaim.py'), *a], capture_output=True, text=True).returncode
ok('cli exit codes', (cli(tp), cli()) == (1, 2))

# craft references from superpowers
R = os.path.join(Z, 'skills', 'tz-craft', 'references')
sk = open(os.path.join(Z, 'skills', 'tz-craft', 'SKILL.md')).read()
for n in 'debug debug-trace debug-flaky verify review review-reply delegate finish-branch brainstorm test-quality skill-test'.split():
    p = os.path.join(R, n + '.md')
    ok(f'{n} routed and small', f'references/{n}.md' in sk and os.path.isfile(p) and 400 <= os.path.getsize(p) <= 1100)
linked = re.findall(r'references/([\w-]+)\.md', sk) + [x for f in glob.glob(R + '/*.md') for x in re.findall(r'\b([a-z]+-[a-z]+)\.md', open(f).read())]
ok('no dead links', all(os.path.isfile(os.path.join(R, n + '.md')) for n in linked))
lic = open(os.path.join(Z, 'third_party', 'superpowers', 'LICENSE')).read()
ok('licence saved', 'MIT License' in lic and 'Jesse Vincent' in lic)
done()
