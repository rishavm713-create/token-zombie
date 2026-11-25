# bin/tzscope.py: parity cases from upstream engine/scope.py _selftest (MIT), plus TZ cases. No network.
import io, json, os, tempfile, contextlib
from harness import ok, done, Z
import tzscope as s

sc = s.compile_scope({'in_scope': ['example.com', '*.test.example.com', '10.0.0.0/8', r're:^lab[0-9]+\.acme\.io$'],
                      'out_of_scope': ['admin.example.com', 'internal.example.com']})
for t in ['https://example.com/login', 'http://api.example.com/x', 'https://a.test.example.com',
          'https://10.1.2.3:8080/', 'https://lab42.acme.io', 'https://test.example.com', 'EXAMPLE.com.']:
    ok('in ' + t, s.reject_reason(sc, t) is None)
for t in ['https://admin.example.com', 'https://internal.example.com/x', 'https://x.admin.example.com',
          'https://evil.com', 'https://notexample.com', 'https://example.com.evil.com', 'https://11.0.0.1',
          'http://evil.com\\@example.com', 'https://example.com@evil.com', '']:
    ok('out ' + t, s.reject_reason(sc, t))
w = s.compile_scope({'in_scope': ['*.test.example.com']})
ok('wild sub', s.reject_reason(w, 'a.test.example.com') is None)
ok('wild not apex', s.reject_reason(w, 'test.example.com'))
d = s.compile_scope({'in_scope': ['example.com'], 'out_of_scope': ['https://admin.example.com:8443/login']})
ok('url deny rule not fail-open', s.reject_reason(d, 'admin.example.com'))
a = s.compile_scope({'in_scope': ['https://example.com/x@evil.com']})
ok('@ in rule path does not widen', s.reject_reason(a, 'evil.com') and s.reject_reason(a, 'example.com') is None)
v6 = s.compile_scope({'in_scope': ['2001:db8::1']})
ok('ipv6', s.reject_reason(v6, 'http://[2001:db8::1]/') is None)
for bad in [[], {'in_scope': 'example.com'}, {'out_of_scope': ['re:(']}, {'in_scope': ['*']}]:
    try:
        s.compile_scope(bad)
        ok('rejects %r' % (bad,), False)
    except ValueError:
        ok('rejects %r' % (bad,), True)

ok('urls and bare hosts', s.targets_in('cd x && curl -s -o out.json -H "Referer: https://r.io" api.foo.com/v1 | grep a.txt') == ['api.foo.com/v1'])
for c in ['curl -O https://evil.com/f', 'wget -m https://evil.com/f', 'curl -s \\\n  https://evil.com/f', 'curl --url=https://evil.com/f', 'curl -o https://evil.com/f']:
    ok('seen: ' + c, s.targets_in(c) == ['https://evil.com/f'])
ok('wget bool flag', s.targets_in('wget -m evil.com') == ['evil.com'])
ok('referer is not a target', s.targets_in('curl -e https://r.io https://a.com') == ['https://a.com'])
ok('redirect file skipped', s.targets_in('curl https://a.com > page.html; cat b.com') == ['https://a.com'])
ok('redirect then url', s.targets_in('curl >o.txt https://a.com') == ['https://a.com'])
ok('newline ends call', s.targets_in('curl https://a.com\ncat notes.md') == ['https://a.com'])
ok('non-network cmd', s.targets_in('git commit -m "see https://evil.com"') == [])
ok('unbalanced quote', s.targets_in('curl "x') == [])

with tempfile.TemporaryDirectory() as tmp:
    def pay(cmd):
        return {'tool_name': 'Bash', 'tool_input': {'command': cmd}, 'cwd': os.path.join(tmp, 'sub')}
    os.makedirs(os.path.join(tmp, 'sub'))
    os.makedirs(os.path.join(tmp, '.tz'))
    ok('silent without file', s.advise(pay('curl https://evil.com')) is None)
    f = os.path.join(tmp, '.tz', 'scope.json')
    with open(f, 'w') as h:
        json.dump({'in_scope': ['example.com']}, h)
    ok('advises out of scope', 'evil.com' in (s.advise(pay('curl https://evil.com')) or ''))
    ok('silent in scope', s.advise(pay('wget https://api.example.com/a')) is None)
    ok('silent loopback', s.advise(pay('curl localhost.localhost http://127.0.0.1:8000/')) is None)
    ok('silent other tool', s.advise({'tool_name': 'Read', 'tool_input': {}, 'cwd': tmp}) is None)
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        ok('cli in', s.main(['--file', f, 'example.com']) == 0)
        ok('cli out', s.main(['--file', f, 'example.com', 'evil.com']) == 1)
        ok('cli missing', s.main(['--file', f + 'x', 'a.com']) == 2)
        ok('cli usage', s.main([]) == 2)
    with open(f, 'w') as h:
        h.write('{')
    ok('broken file fails closed', 'unreadable' in (s.advise(pay('curl https://example.com')) or ''))
done()
