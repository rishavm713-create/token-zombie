# aider port: important files, definition-line maps, failed-Edit hints, lint context. Parity cases from aider tests/basic.
import os, subprocess, sys, tempfile
from harness import ok, done, Z
sys.path.insert(0, os.path.join(Z, 'bin'))
import tzaider, tzrank

T = tempfile.mkdtemp()
def w(rel, s):
    p = os.path.join(T, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'w').write(s); return p
def cli(script, *a):
    return subprocess.run([sys.executable, os.path.join(Z, 'bin', script)] + list(a), capture_output=True, text=True)

# special files (upstream test_special.py)
imp = tzaider.is_important
ok('important root files', all(imp(f) for f in ['README.md', '.gitignore', 'requirements.txt', 'setup.py', 'README',
   'README.txt', 'README.rst', 'LICENSE', 'LICENSE.md', 'LICENSE.txt', 'Dockerfile', 'package.json', 'pyproject.toml']))
ok('important workflows', imp('.github/workflows/test.yml') and imp('.github/workflows/deploy.yml'))
ok('not important', not any(imp(f) for f in ['random_file.txt', 'src/main.py', 'tests/test_app.py']))
ok('case and path rules', not imp('readme.md') and not imp('.GITIGNORE') and not imp('project/README.md')
   and imp('./README.md') and not imp('/absolute/path/to/README.md'))
for f in ('README.md', '.gitignore', '.github/workflows/test.yml', '.circleci/config.yml', 'sub/README.md', 'random.txt'):
    w(f, 'SECRET_BODY\n')
found = tzaider.important_files(T)
ok('important_files lists root and dot folders', found == sorted(['README.md', '.gitignore', '.github/workflows/test.yml', '.circleci/config.yml']))

# map rendering
w('lib/core.py', 'import os\n\nclass MyClass:\n    def my_method(self):\n        return 1\n\ndef my_function(' + 'a' * 150 + '):\n    return 2\n')
w('lib/user.py', 'from core import MyClass\nx = MyClass().my_method()\ny = my_function(1)\n')
w('web/app.js', 'const x = 1\nexport function renderPage() {}\n')
w('web/use.js', 'renderPage(); renderPage();\n')
out = tzaider.render_lines(T, [(1, 'lib/core.py', 'MyClass.my_method'), (1, 'lib/core.py', 'my_function'),
                               (1, 'web/app.js', 'renderPage'), (0, 'lib/user.py', '')])
ok('method shows class header with numbers', ' 3| class MyClass:\n 4|     def my_method(self):\n' in out)
ok('lines cut to 100 chars', max(len(x) for x in out.splitlines()) == 100)
ok('js definition line', 'web/app.js:\n 2| export function renderPage() {}\n' in out)
ok('tagless file is bare name', out.endswith('lib/user.py\n'))
ok('unlocated ident kept by name', '  ghost_name\n' in tzaider.render_lines(T, [(1, 'web/app.js', 'ghost_name')]))
r = cli('tzrank.py', '--tokens', '400', '--lines', T)
ok('rank --lines map has def lines', r.returncode == 0 and 'def my_method(self):' in r.stdout and 'tag(s)' in r.stdout)
ok('rank map lists important files first, no contents', r.stdout.index('README.md') < r.stdout.index('lib/core.py') and 'SECRET_BODY' not in r.stdout)
r = cli('tzrank.py', '--lines', '--n', '2', T)
ok('rank --lines without budget', r.returncode == 0 and '| ' in r.stdout and 'README.md' in r.stdout)
r = cli('tzrank.py', '--n', '3', T)
ok('plain rank unchanged', 'README.md' not in r.stdout and 'top definition(s)' in r.stdout)
ok('focus file not re-added', all(f != 'README.md' for _, f, _ in tzaider.with_important(T, [], ['README.md'])))
# upstream test_get_repo_map_with_identifiers: class, method and function all in the map
ok('identifiers parity', {'MyClass', 'MyClass.my_method', 'my_function'} <= {i for _, f, i in tzrank.ranked(T, methods=True) if f == 'lib/core.py'})

# did-you-mean (upstream editblock_coder behaviour)
whole = '\n    line1\n    line2\n        line3\n    line4\n'
ok('whitespace match', tzaider.whitespace_match(['line2', '    line3'], whole.splitlines()) == (2, 4))
ok('blank search never matches', tzaider.whitespace_match(['', ' '], ['', '']) is None)
body = ''.join(f'row_{i} = {i}\n' for i in range(40))
near = 'row_10 = 10\nrow_11 = 999\nrow_12 = 12\n'
sim = tzaider.find_similar_lines(near, body)
ok('similar block with matching ends is exact size', sim == 'row_10 = 10\nrow_11 = 11\nrow_12 = 12')
sim = tzaider.find_similar_lines('row_10 = 10\nrow_11 = 11\nrow_12 = 999\n', body).splitlines()
# first best window wins (as upstream): rows 9-11 score the same as 10-12, then 5 lines each side
ok('similar block padded by 5', sim[0] == 'row_4 = 4' and sim[-1] == 'row_16 = 16' and len(sim) == 13)
ok('below threshold is empty', tzaider.find_similar_lines('zzz\nyyy\n', body) == '')
ok('search longer than file', tzaider.find_similar_lines('a\nb\nc\n', 'a\n') == '')

p = w('edit/a.py', body)
def fail(old, new='x', tool='Edit', err='String to replace not found in file.\nString: ...'):
    return tzaider.edit_hint({'hook_event_name': 'PostToolUseFailure', 'tool_name': tool, 'error': err,
                              'tool_input': {'file_path': p, 'old_string': old, 'new_string': new}})
h = fail(near)
ok('hint gives real lines and range', 'lines 11-13 [actual]' in h and 'row_11 = 11' in h)
ok('hint flags whitespace', 'only whitespace differs' in fail('  row_3 = 3\n  row_4 = 4'))
ok('hint says already applied', 'already in' in fail('nothing like it', 'row_20 = 20\nrow_21 = 21\n'))
ok('other errors silent', fail(near, err='File has not been read yet') == '')
ok('other tools silent', fail(near, tool='Bash') == '')
ok('nothing close is silent', fail('zzz') == '')
ok('missing file silent', tzaider.edit_hint({'tool_name': 'Edit', 'error': 'String to replace not found', 'tool_input': {'file_path': T + '/no', 'old_string': 'a'}}) == '')
ok('empty payload silent', tzaider.edit_hint({}) == '')
long = w('edit/long.py', ''.join(f'v{i} = "{"q" * 200}"\n' for i in range(20)))
m = tzaider.match_report(long, ''.join(f'  v{i} = "{"q" * 200}"\n' for i in range(15)))
ok('oversize hint gives Read range only', 'Read offset=1 limit=15' in m and len(m) < 500)

# lint (aider linter.py)
bad = w('lint/bad.py', 'a = 1\nb = 2\ndef f(:\n    pass\n')
m = tzaider.lint_file(bad)
ok('python syntax error with marked line', 'SyntaxError' in m and '    3' + chr(0x2588) + ' def f(:' in m and '    1| a = 1' in m)
ok('return outside function caught', 'SyntaxError' in tzaider.lint_file(w('lint/ret.py', 'return 1\n')))
marker = os.path.join(T, 'ran')
ok('lint never runs code', tzaider.lint_file(w('lint/run.py', f'open({marker!r}, "w")\n')) == '' and not os.path.exists(marker))
sh = w('lint/bad.sh', 'echo a\nif true; then\necho b\n')
ok('shell syntax error', bool(tzaider.lint_file(sh)) and tzaider.lint_file(w('lint/ok.sh', 'echo ok\n')) == '')
fake = w('lint/fake.py', 'import sys\nprint(sys.argv[1] + ":2: boom")\nsys.exit(1)\n')
tgt = w('lint/(main) [id].txt', 'one\ntwo\n')
m = tzaider.lint_file(tgt, f'{sys.executable} {fake}')
ok('custom cmd output and context, special chars', 'boom' in m and '    2' + chr(0x2588) + ' two' in m)
ok('missing linter reported', 'failed to run' in tzaider.lint_file(tgt, 'tz-no-such-linter'))
r = cli('tzaider.py', 'lint', bad)
ok('cli lint exit 1', r.returncode == 1 and 'SyntaxError' in r.stdout)
ok('cli lint clean exit 0', cli('tzaider.py', 'lint', T + '/lib/core.py').returncode == 0)
ok('cli important', 'README.md' in cli('tzaider.py', 'important', T).stdout)
ok('cli similar', 'row_11 = 11' in cli('tzaider.py', 'similar', p, w('edit/snip', near)).stdout)
ok('cli usage', cli('tzaider.py').returncode == 2)
done()
