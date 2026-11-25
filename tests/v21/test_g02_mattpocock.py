# mattpocock/skills integration: opt-in git guard (upstream block list parity) and the tz-craft references.
import io, os, sys, subprocess, contextlib
from harness import ok, done, Z
import tzlib
tzlib._conf.clear()  # ignore the machine's own config.json
os.environ.pop('TZ_FEAT_GIT_GUARD', None)
import tzshell, tzgitguard as G

ORIG = tzshell._git
D = Z  # any real directory works as cwd

# upstream git-guardrails list: every entry blocked, including `git push origin main` from its verify step
for cmd, want in [('git push', 'push'), ('git push origin main', 'push'), ('git push --force', 'push'),
                  ('git push --force-with-lease origin x', 'push'), ('git reset --hard HEAD~1', 'reset-hard'),
                  ('git clean -f', 'clean-force'), ('git clean -fd', 'clean-force'),
                  ('git branch -D feat', 'branch-force-delete'), ('git checkout .', 'checkout-dot'),
                  ('git checkout -- .', 'checkout-dot'), ('git restore .', 'restore-dot'),
                  ('git restore --staged --worktree .', 'restore-dot'),
                  # forms the upstream raw grep misses
                  ('git -C /tmp/r push', 'push'), ('git -c a=b push', 'push'), ('git reset -q --hard', 'reset-hard'),
                  ('git add a && git push', 'push'), ('bash -c "git push"', 'push'), ('sudo git push', 'push'),
                  ('echo $(git push)', 'push'), ('git -c alias.p=push p', 'push'), ('git send-pack o main', 'push'),
                  ('git subtree push --prefix=a o b', 'push'),
                  # an earlier segment trips another rule or the text cannot be parsed: raw fallback
                  ('cat ~/.ss' + 'h/id_rsa; git push', 'push'), ('git push "unterminated', 'push')]:
    ok(f'blocked {cmd!r}', G.check(cmd, D) == want)
for cmd in ['git status', 'git commit -m "git push later"', 'echo git push', 'git stash push -m x', 'git log --grep=push',
            'git reset HEAD a', 'git clean -n', 'git clean -fdn', 'git branch -d feat', 'git checkout main',
            'git restore --staged .', 'git restore a.py', 'ls', '']:
    ok(f'allowed {cmd!r}', G.check(cmd, D) is None)
ok('tzshell restored', tzshell._git is ORIG)

# customisation (upstream step 4)
tzlib._conf.update(git_guard_allow=['push'], git_guard_block=['commit'])
ok('allow drops a rule', G.check('git push', D) is None)
ok('later rule still found', G.check('git push; git reset --hard', D) == 'reset-hard')
ok('extra subcommand', G.check('git commit -m x', D) == 'commit')
ok('extra in raw fallback', G.check('git commit -m "x', D) == 'commit')
tzlib._conf.clear()

# hook: off by default, deny reason when on, Bash only, fail closed on crash
P = {'tool_name': 'Bash', 'tool_input': {'command': 'git push'}, 'cwd': D}
ok('default off', G.hook(P) == '')
os.environ['TZ_FEAT_GIT_GUARD'] = '1'
ok('on: denies', '[push]' in G.hook(P) and 'ask the owner' in G.hook(P))
ok('no bypass hint', 'TZ_' not in G.hook(P))
ok('on: allows safe', G.hook(dict(P, tool_input={'command': 'git status'})) == '')
ok('non-Bash ignored', G.hook(dict(P, tool_name='Write')) == '')
real = G.check
G.check = lambda *a: 1 / 0
ok('crash fails closed', 'fail closed' in G.hook(P))
G.check = real
os.environ.pop('TZ_FEAT_GIT_GUARD')

# CLI: upstream blocks with exit 2
with contextlib.redirect_stdout(io.StringIO()) as out:
    ok('cli blocked exit 2', G.main(['check', 'git push origin main']) == 2)
    ok('cli allowed exit 0', G.main(['check', 'git status']) == 0)
    ok('cli status', G.main([]) == 0 and G.main(['bogus']) == 1)
ok('cli status text', 'git guard:' in out.getvalue() and 'push' in out.getvalue())
r = subprocess.run([sys.executable, os.path.join(Z, 'bin', 'tzgitguard.py'), 'check', 'git reset --hard'], capture_output=True)
ok('script exit 2', r.returncode == 2)

# references: small and carry the ported rules
R = os.path.join(Z, 'skills', 'tz-craft', 'references')
for name, words in {'tdd': ('seams', 'Tautological', 'system edges'), 'plan': ('vertical slices', 'expand'),
                    'git-safety': ('conflict', 'do not rephrase'), 'grill': ('recommended answer', 'confirms'),
                    'design': ('Deletion test', 'ADR'), 'agent-docs': ('every turn', 'pointer')}.items():
    p = os.path.join(R, name + '.md')
    text = open(p).read()
    ok(f'{name} size', 400 <= os.path.getsize(p) <= 1100)
    ok(f'{name} content', all(w in text for w in words))
lic = open(os.path.join(Z, 'third_party', 'mattpocock-skills', 'LICENSE')).read()
ok('licence saved', 'MIT License' in lic and 'Matt Pocock' in lic)
done()
