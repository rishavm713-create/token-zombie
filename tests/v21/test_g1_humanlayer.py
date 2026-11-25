#!/usr/bin/env python3
import contextlib, io, os, sys, tempfile
from harness import ok, done, Z
import tzhumanlayer as H


def hit(c):
    return H.filtered_check(c) is not None


# upstream hook cases (check command + disallowed pipe filter)
for c in ('bun test | tail -20', 'npm run test | grep fail', 'CI=1 pnpm typecheck 2>&1 | head',
          'yarn test:ci | less', 'bun --bun run pkg:test | rg x', 'bun --bun turbo run typecheck | sed -n 1p',
          'turbo run test:llm | awk 1', 'oxlint . | more', 'oxfmt --check | egrep a'):
    ok('flag ' + c, hit(c))
# extra runners and shell shapes
for c in ('pytest -q 2>&1 | tail -5', 'cd app && python3 -m pytest | grep F', 'go test ./... |& head',
          'timeout 60 cargo test | tail', 'echo hi\nnpm test | tail', 'npm test | cat | tail', '(make test) ; pytest|tail'):
    ok('flag ' + c, hit(c))
for c in ('bun test', 'npm test > log 2>&1', 'npm test && tail log', 'cat log | grep npm test', 'cat x | grep a; npm test',
          'grep "pytest | tail" README.md', 'echo "npm test | head"', 'pytest | tee log | tail', 'pytest || tail log',
          'ls | head', 'cat <<EOF\nnpm test | tail\nEOF', 'pytest "unterminated | tail', 'npm install | tail', ''):
    ok('quiet ' + repr(c), not hit(c))
a = H.check_pipe_advice({'tool_name': 'Bash', 'tool_input': {'command': 'pytest | tail'}})
ok('advice names filter', a and 'tail' in a and 'pytest' in a and len(a) < 220)
ok('non-bash quiet', H.check_pipe_advice({'tool_name': 'Read', 'tool_input': {}}) is None)
ok('empty payload quiet', H.check_pipe_advice({}) is None)

PLAN = """# X Implementation Plan

## Overview
long preamble

## What We're NOT Doing
no UI

## Implementation Approach
words

## Phase 1: Schema
```diff
## Phase 9: fake
- [ ] fake box
```
### Success Criteria:
#### Automated Verification:
- [x] Compiles: `true`
#### Manual Verification:
- [x] looks right

## Phase 2: API
### Success Criteria:
#### Automated Verification:
- [ ] Tests pass: `%s`
#### Manual Verification:
- [ ] click it

## Phase 3: Docs
- [ ] docs

## References
tail text
"""
d = tempfile.mkdtemp()


def run(text, *args):
    p = os.path.join(d, 'plan.md')
    with open(p, 'w') as h:
        h.write(text)
    b = io.StringIO()
    with contextlib.redirect_stdout(b):
        rc = H.main([args[0], p] + list(args[1:]))
    return rc, b.getvalue()


_, ph = H.parse(PLAN % 'true')
ok('fenced phase ignored', [p['n'] for p in ph] == [1, 2, 3])
ok('kinds', [i['kind'] for i in ph[1]['items']] == ['auto', 'manual'])
ok('resume at first unticked', H.current(ph)['n'] == 2)
rc, o = run(PLAN % 'true', 'status')
ok('status', rc == 0 and '> Phase 2: API (0/2)' in o and 'Phase 1: Schema (2/2)' in o)
rc, o = run(PLAN % 'true', 'next')
ok('next is current + scope only', rc == 0 and 'no UI' in o and '## Phase 2' in o and 'Schema' not in o
   and 'Docs' not in o and 'long preamble' not in o and 'tail text' not in o)
rc, o = run(PLAN % 'true', 'gate')
ok('gate closed', rc == 2 and 'manual unticked: click it' in o)
ok('gate earlier phase open', run(PLAN % 'true', 'gate', '--phase', '1')[0] == 0)
ticked = (PLAN % 'true').replace('- [ ] Tests', '- [x] Tests').replace('- [ ] click', '- [x] click')
ok('gate open when ticked', run(ticked, 'gate', '--phase', '2')[0] == 0)
ok('later phase blocked by earlier', run(PLAN % 'true', 'gate', '--phase', '3')[0] == 2)
rc, o = run(ticked.replace('`true`\n#### Manual Verification:\n- [x] click', '`false`\n#### Manual Verification:\n- [x] click')
            .replace('Tests pass: `true`', 'Tests pass: `false`'), 'gate', '--phase', '2', '--run')
ok('ticked box with failing command stays closed', rc == 2 and 'FAIL false (exit 1)' in o)
rc, o = run(ticked, 'gate', '--phase', '2', '--run')
ok('run passes', rc == 0 and 'ok   true' in o)
mark = os.path.join(d, 'ran')
run(ticked.replace('Tests pass: `true`', 'Tests pass: `touch %s`' % mark), 'gate', '--phase', '2')
ok('no execution without --run', not os.path.exists(mark))
rc, o = run(ticked.replace('Tests pass: `true`', 'Tests pass: `rm -rf /`'), 'gate', '--phase', '2', '--run')
ok('unsafe command not run', rc == 2 and 'not run:' in o)
ok('bad usage', run(ticked, 'bogus')[0] == 1 and run(ticked, 'gate', '--phase')[0] == 1)
ok('unknown phase', run(ticked, 'gate', '--phase', '9')[0] == 1)
ok('no phases is not a pass', run('# nothing\n- [x] a\n', 'gate')[0] == 1)
done()
