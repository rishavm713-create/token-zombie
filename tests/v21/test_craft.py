# tz-craft skill: files, sizes, frontmatter, keyword routing.
import os, re
from harness import ok, done, Z
import tzondemand as T

D = os.path.join(Z, 'skills', 'tz-craft')
R = os.path.join(D, 'references')
NAMES = 'verify debug tdd refactor review plan perf react git-safety learn'.split()

sk = open(os.path.join(D, 'SKILL.md')).read()
m = re.match(r'---\nname: (.+)\ndescription: (.+)\n---\n', sk)
ok('frontmatter valid', bool(m))
ok('name matches dir', bool(m) and m.group(1) == 'tz-craft')
ok('description <= 260 bytes', bool(m) and len(m.group(2).encode()) <= 260)
ok('router mentions every ref', all(f'references/{n}.md' in sk for n in NAMES))
for n in NAMES:
    p = os.path.join(R, n + '.md')
    ok(f'{n} exists', os.path.isfile(p))
    sz = os.path.getsize(p) if os.path.isfile(p) else 0
    ok(f'{n} size 400..1100', 400 <= sz <= 1100)
    ok(f'{n} <= 1.2KB', sz <= 1200)
ok('verify has unverified_claim', 'unverified_claim' in open(os.path.join(R, 'verify.md')).read())
for prompt, want in [('flaky test failing', 'debug'), ('please refactor this module', 'refactor'),
                     ('review my pull request', 'review'), ('the page is slow', 'perf'),
                     ('react component rerenders', 'react'), ('force push to main', 'git-safety'),
                     ('is it done?', 'verify'), ('lunch menu', None)]:
    ok(f'route {prompt!r}', T.craft(prompt) == want)
ok('want() unchanged', T.want('nothing relevant here') == [])
done()
