# tzscrub: harbor redaction (Apache-2.0) + rea untrusted marker idea.
import os, json, tempfile
from harness import ok, done
import tzscrub as S
ok('plain', S.scrub('a sk-secret-123 b', ['sk-secret-123']) == 'a [REDACTED] b')
ok('longest first', S.scrub('abcdef abc', ['abc', 'abcdef']) == '[REDACTED] [REDACTED]')
j = '{"tokens": 12345678, "k": "x12345678y"}'
o = S.scrub(j, ['12345678'], '.json')
ok('json stays valid', json.loads(o)['tokens'] == 12345678 and json.loads(o)['k'] == 'x[REDACTED]y')
ok('no secret untouched', S.scrub('hi', ['zzz']) == 'hi')
ok('env floor', S.env_secrets({'API_KEY': 'abcdefghij', 'MY_TOKEN': 'x', 'HOME': '/Users/abcdefgh'}) == ['abcdefghij'])
ok('untrusted tag', S.mark_untrusted('hi', 'web').startswith('<untrusted source="web">') and 'hi' in S.mark_untrusted('hi'))
d = tempfile.mkdtemp(); p = os.path.join(d, 'a.txt'); open(p, 'w').write('x TOPSECRET1 y')
ok('cli', S.main([p, '--secret', 'TOPSECRET1']) == 0 and S.main([p + 'x']) == 1)
done()
