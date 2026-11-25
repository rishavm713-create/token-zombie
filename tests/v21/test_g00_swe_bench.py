"""SWE-bench parsers and grading; seaborn/skip/truncated-id cases mirror upstream tests/."""
import contextlib, io, json, os, tempfile
from harness import ok, done, Z
import tzswebench as S

P, F, K, E = 'PASSED', 'FAILED', 'SKIPPED', 'ERROR'


def check(parser, log, want):
    got = S.PARSERS[parser](log)
    if got != want:
        print(parser, got)
    ok('parse ' + parser, got == want)


# upstream tests/test_log_parsers_python.py
check('seaborn', 't.py::one PASSED [ 50%]\nPASSED t.py::two\nFAILED t.py::three\nPASSED\nFAILED\n PASSED\n',
      {'t.py::one': P, 't.py::two': P, 't.py::three': F})
check('pytest', 'PASSED a::x\nFAILED a::y - assert 1\nERROR a::z\nXFAIL a::w\nSKIPPED [2] a.py:3: no\nPASSED\nnoise',
      {'a::x': P, 'a::y': F, 'a::z': E, 'a::w': 'XFAIL'})
check('pytest-options', 'PASSED a::x[/tmp/q/f.txt]\nPASSED a::y[//keep/it]\n',
      {'a::x[/f.txt]': P, 'a::y[//keep/it]': P})
check('pytest-v2', '\x1b[32mPASSED\x1b[0m a::x[a b]\nFAILED a::y - boom - more\na::old PASSED\n',
      {'a::x[a b]': P, 'a::y': F, 'a::old': P})
check('matplotlib', 'PASSED a::x[MouseButton.LEFT]\n', {'a::x[1]': P})
check('sympy', 'test_a ok\ntest_b F\ntest_c E\n___ s/t.py:test_d ___\n',
      {'test_a': P, 'test_b': F, 'test_c': E, 's/t.py:test_d': F})
check('unittest', 'test_a (m.C) ... ok\ntest_b (m.C) ... FAIL\ntest_c (m.C) ... ERROR\n'
      "test_d (m.C) ... skipped 'x'\ntest_e (m.C) ... noisy\nok\nFAIL:\n",
      {'test_a (m.C)': P, 'test_b (m.C)': F, 'test_c (m.C)': E, 'test_d (m.C)': K, 'test_e (m.C)': P})
check('django', 't1 ... System check identified no issues (0 silenced)\nok\n', {'t1': P})
check('gotest', '--- PASS: TestA (0.00s)\n    --- FAIL: TestA/sub (0.1s)\n--- SKIP: TestB (0s)\n',
      {'TestA': P, 'TestA/sub': F, 'TestB': K})
check('cargo', 'test a::b ... ok\ntest a::c ... FAILED\ntest a::d ... ignored\n', {'a::b': P, 'a::c': F})
check('jest', '  ✓ adds (3 ms)\n  ✕ subs\n  ○ skip me\n', {'adds': P, 'subs': F, 'skip me': K})
check('jest-json', '[PASSED] a b\n[FAILED] c\n', {'a b': P, 'c': F})
check('vitest', ' ✓ a > b 3ms\n × c\n ↓ d [skipped]\n', {'a > b': P, 'c': F, 'd': K})
check('tap', 'ok 1 first\nnot ok 2 second\n# tests 2\n', {'first': P, 'second': F})
check('karma', 'x\nStarting browser\n  Suite\n    ✔ a\n    ✖ b\nSUMMARY:\n✔ 1\n',
      {'Suite > a': P, 'Suite > b': F})
check('maven', '+ mvn test -Dtest=A#x\n[INFO] BUILD SUCCESS\n+ mvn test -Dtest=B#y\n[INFO] BUILD FAILURE\n',
      {'A#x': P, 'B#y': F})
check('ant', '[junit] [PASS] a\n[junit] [ERR] b\n', {'a': P, 'b': F})
check('gradle', 'C > a PASSED\nC > b\nwarning: x\nFAILED\n> Task :t FAILED\n', {'C > a': P, 'C > b': F})

# upstream tests/test_grading_skipped.py
rep = S.eval_report({'a': K, 'b': K, 'c': P}, {S.F2P: ['a', 'b'], S.P2P: ['c']})
ok('skipped f2p fails', rep[S.F2P] == {'success': [], 'failure': ['a', 'b']} and S.resolution(rep) == S.NO)
rep = S.eval_report({'a': P, 'c': K}, {S.F2P: ['a'], S.P2P: ['c']})
ok('skipped p2p kept', rep[S.P2P]['success'] == ['c'] and S.resolution(rep) == S.FULL)

# upstream tests/test_grading_truncated_ids.py
T = 't::x[args1-No'
ok('exact only for balanced', S._lookup('t::x[1]', {'t::x[1]-more]': P}) is None)
ok('truncated unique', S._lookup(T, {T + 'ne]': P}) == P)
ok('truncated mixed', S._lookup(T, {T + 'ne]': P, T + '-v]': F}) is None)
ok('passed+xfail same', S._lookup(T, {T + 'ne]': P, T + '-v]': 'XFAIL'}) in (P, 'XFAIL'))
ok('surplus ] no fallback', S._lookup('a] b', {'a] b more': P}) is None)

# partial / fail_only
rep = S.eval_report({'a': P, 'b': F}, {S.F2P: ['a', 'b']})
ok('partial', S.resolution(rep) == S.PARTIAL)
ok('fail_only absent passes', S.resolution(S.eval_report({}, {S.F2P: ['a']}, 'fail_only')) == S.FULL)

# before/after
before = 'FAILED t::bug\nPASSED t::keep\nSKIPPED t::skip\n'
good = 'PASSED t::bug\nPASSED t::keep\n'
ok('before/after full', S.grade(good, before=before)['resolved'])
ok('regression', S.grade('PASSED t::bug\nFAILED t::keep\n', before=before)['status'] == S.NO)
ok('dropped test is regression', S.grade('PASSED t::bug\n', before=before)['status'] == S.NO)
ok('nothing failing is invalid', S.grade(good, before=good)['status'] == S.INVALID)
ok('empty log invalid', S.grade('boom', before=before)['status'] == S.INVALID)
ok('empty before invalid', S.grade(good, before='boom')['status'] == S.INVALID)

# log trust checks
rs = lambda c: S.read_status(c, 'pytest')
ok('bad marker', rs('>>>>> Tests Timed Out\nPASSED a')[1] != '')
ok('half markers', rs('>>>>> Start Test Output\nPASSED a')[1] != '')
ok('slice markers', rs('PASSED no\n>>>>> Start Test Output\nPASSED a\n>>>>> End Test Output\n')[0] == {'a': P})
ok('fallback outside markers', rs('PASSED a\n>>>>> Start Test Output\n>>>>> End Test Output\n')[0] == {'a': P})
ok('spoofed pass', rs('PASSED a\n>>>>> Test Exit Code: 1')[1] != '')
ok('exit ok with failure', rs('FAILED a\n>>>>> Test Exit Code: 1')[1] == '')
ok('silent suite ran', S.read_status('3 passing', 'tap') == ({}, ''))
ok('zero-run not evidence', S.read_status('Executed 0 of 0', 'karma')[1] != '')


def cli(*argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        rc = S.main(list(argv))
    return rc, buf.getvalue()


with tempfile.TemporaryDirectory() as d:
    def w(name, text):
        p = os.path.join(d, name)
        with open(p, 'w') as fh:
            fh.write(text)
        return p
    b, a = w('b', before), w('a', good)
    rc, out = cli('grade', a, '--before', b)
    ok('cli grade full', rc == 0 and 'RESOLVED_FULL' in out and '1/1 [actual]' in out)
    spec = w('s', json.dumps({S.F2P: json.dumps(['t::bug']), S.P2P: ['t::gone']}))
    rc, out = cli('grade', a, '--spec', spec, '--json')
    ok('cli spec unresolved', rc == 1 and json.loads(out)['status'] == S.NO)
    ok('cli flag override', cli('grade', a, '--spec', spec, '--p2p', 't::keep')[0] == 0)
    rc, out = cli('parse', a, '--json')
    ok('cli parse', rc == 0 and json.loads(out) == {'t::bug': P, 't::keep': P})
    ok('cli invalid', cli('grade', w('e', ''), '--f2p', 'x')[0] == 2)
    ok('cli missing file', cli('parse', os.path.join(d, 'nope'))[0] == 2)
    ok('cli bad spec', cli('grade', a, '--spec', w('bad', '{"FAIL_TO_PASS": 3}'))[0] == 2)

done()
