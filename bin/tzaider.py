#!/usr/bin/env python3
# `tz aider important|similar|lint`: aider's helpers that save a re-read: key project files, the closest real lines
# after a failed Edit, and syntax errors shown with the lines around them. render_lines serves `tz rank --lines`.
# Adapted from aider aider/special.py, aider/repomap.py (render_tree, to_tree), aider/coders/editblock_coder.py
# (find_similar_lines, match_but_for_leading_whitespace, apply_edits failure hints) and aider/linter.py
# (https://github.com/Aider-AI/aider, Apache License 2.0, Copyright 2023-2025 Paul Gauthier and Aider contributors),
# see NOTICE and third_party/aider/LICENSE.
# Changes: ast/regex header lines instead of tree-sitter TreeContext, with line numbers; whitespace match checked
# in any direction; hint output capped; node --check / bash -n instead of tree-sitter; no automatic flake8.
import ast, os, re, shlex, shutil, subprocess, sys
from difflib import SequenceMatcher
from itertools import accumulate

IMPORTANT = {os.path.normpath(p) for p in """
.gitignore .gitattributes README README.md README.txt README.rst CONTRIBUTING CONTRIBUTING.md CONTRIBUTING.txt
CONTRIBUTING.rst LICENSE LICENSE.md LICENSE.txt CHANGELOG CHANGELOG.md CHANGELOG.txt CHANGELOG.rst SECURITY
SECURITY.md SECURITY.txt CODEOWNERS requirements.txt Pipfile Pipfile.lock pyproject.toml setup.py setup.cfg
package.json package-lock.json yarn.lock npm-shrinkwrap.json Gemfile Gemfile.lock composer.json composer.lock
pom.xml build.gradle build.gradle.kts build.sbt go.mod go.sum Cargo.toml Cargo.lock mix.exs rebar.config
project.clj Podfile Cartfile dub.json dub.sdl .env .env.example .editorconfig tsconfig.json jsconfig.json .babelrc
babel.config.js .eslintrc .eslintignore .prettierrc .stylelintrc tslint.json .pylintrc .flake8 .rubocop.yml
.scalafmt.conf .dockerignore .gitpod.yml sonar-project.properties renovate.json dependabot.yml
.pre-commit-config.yaml mypy.ini tox.ini .yamllint pyrightconfig.json webpack.config.js rollup.config.js
parcel.config.js gulpfile.js Gruntfile.js build.xml build.boot project.json build.cake MANIFEST.in pytest.ini
phpunit.xml karma.conf.js jest.config.js cypress.json .nycrc .nycrc.json .travis.yml .gitlab-ci.yml Jenkinsfile
azure-pipelines.yml bitbucket-pipelines.yml appveyor.yml circle.yml .circleci/config.yml .github/dependabot.yml
codecov.yml .coveragerc Dockerfile docker-compose.yml docker-compose.override.yml serverless.yml firebase.json
now.json netlify.toml vercel.json app.yaml terraform.tf main.tf cloudformation.yaml cloudformation.json ansible.cfg
kubernetes.yaml k8s.yaml schema.sql liquibase.properties flyway.conf next.config.js nuxt.config.js vue.config.js
angular.json gatsby-config.js gridsome.config.js swagger.yaml swagger.json openapi.yaml openapi.json .nvmrc
.ruby-version .python-version Vagrantfile .codeclimate.yml mkdocs.yml _config.yml book.toml readthedocs.yml
.readthedocs.yaml .npmrc .yarnrc .isort.cfg .markdownlint.json .markdownlint.yaml .bandit .secrets.baseline .pypirc
.gitkeep .npmignore
""".split()}
WORKFLOWS = os.path.join('.github', 'workflows')
MAX_BYTES, MAX_LINES, HINT_CHARS = 1_000_000, 20_000, 2000


def _read(path):
    """File text, or None when unreadable, binary or over MAX_BYTES."""
    try:
        if not os.path.isfile(path) or os.path.getsize(path) > MAX_BYTES:
            return None
        s = open(path, encoding='utf-8', errors='replace').read()
    except OSError:
        return None
    return None if '\0' in s else s


def is_important(path):
    """True for a repo-relative path that usually explains a project (root files and CI workflows)."""
    p = os.path.normpath(path)
    return p in IMPORTANT or (os.path.dirname(p) == WORKFLOWS and p.endswith('.yml'))


def important_files(root):
    """Sorted repo-relative important files that exist; names only, contents are never read."""
    out = []
    # WHY listdir, not isfile on each name: case-insensitive disks would accept readme.md; tzmap skips dot folders.
    for d in {os.path.dirname(p) for p in IMPORTANT} | {WORKFLOWS}:
        try:
            names = os.listdir(os.path.join(root, d))
        except OSError:
            continue
        out += [r for r in (os.path.join(d, n) for n in names) if is_important(r) and os.path.isfile(os.path.join(root, r))]
    return sorted(out)


def with_important(root, rs, focus=()):
    """Ranked (v, file, ident) with unlisted important files first, so a token budget keeps them."""
    have = {f for _, f, _ in rs} | {os.path.normpath(f) for f in focus}
    return [(0.0, f, '') for f in important_files(root) if f not in have] + list(rs)


def _py_headers(src):
    """{qualified name: [header line numbers]}; a method or nested class also lists its class headers."""
    out = {}

    def walk(body, pre, parents):
        for n in body:
            if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                out[pre + n.name] = parents + [n.lineno]
                if isinstance(n, ast.ClassDef):
                    walk(n.body, pre + n.name + '.', parents + [n.lineno])
    try:
        walk(ast.parse(src).body, '', [])
    except (SyntaxError, ValueError, RecursionError):
        pass
    return out


def _headers(src, path, ident):
    """1-based line numbers that show where ident is defined, [] if not found."""
    if path.endswith('.py'):
        return _py_headers(src).get(ident, [])
    n = re.escape(ident)
    rx = re.compile(r'^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:(?:def|class|function\*?|const|let|var|interface|type|enum)\s+%s\b|%s\s*\(\)\s*\{)' % (n, n))
    for i, line in enumerate(src.split('\n'), 1):
        if rx.match(line):
            return [i]
    return []


def render_lines(root, rs):
    """Aider-style map: per file the definition lines of ranked idents, numbered, each cut to 100 chars."""
    by = {}
    for _, f, i in rs:
        by.setdefault(f, []).extend([i] if i else [])
    out = []
    for f, ids in by.items():
        if not ids:
            out.append(f)
            continue
        src = _read(os.path.join(root, f)) or ''
        lines, nums, missing = src.split('\n'), set(), []
        for i in ids:
            h = _headers(src, f, i)
            nums.update(h)
            if not h:
                missing.append(i)
        out.append(f + ':')
        out += [f' {n}| {lines[n - 1].rstrip()}'[:100] for n in sorted(nums)]
        out += [f'  {i}'[:100] for i in missing]
    return ''.join(x + '\n' for x in out)


def whitespace_match(search_lines, content_lines):
    """(start, end) of the first block equal to search except for leading/trailing whitespace, else None."""
    want = [x.strip() for x in search_lines]
    if not any(want):
        return None
    have = [x.strip() for x in content_lines]
    n = len(want)
    for i in range(len(have) - n + 1):
        if have[i:i + n] == want:
            return i, i + n
    return None


def similar_window(search_lines, content_lines, threshold=0.6, pad=5):
    """(start, end) of the closest block (padded unless its first and last line already match), else None."""
    n = len(search_lines)
    if not n or n > len(content_lines) or len(content_lines) > MAX_LINES:
        return None
    shared = set(search_lines)
    hits = [0, *accumulate(x in shared for x in content_lines)]
    best, at = 0, 0
    for i in range(len(content_lines) - n + 1):
        if hits[i + n] - hits[i] < max(threshold * n, 1):  # WHY: cannot reach threshold; keeps the hook fast
            continue
        r = SequenceMatcher(None, search_lines, content_lines[i:i + n]).ratio()
        if r > best:
            best, at = r, i
    if not best or best < threshold:
        return None
    if content_lines[at] == search_lines[0] and content_lines[at + n - 1] == search_lines[-1]:
        return at, at + n
    return max(0, at - pad), min(len(content_lines), at + n + pad)


def find_similar_lines(search, content, threshold=0.6):
    """Text of the content block closest to search, '' when nothing reaches threshold."""
    c = content.splitlines()
    w = similar_window(search.splitlines(), c, threshold)
    return '\n'.join(c[w[0]:w[1]]) if w else ''


def match_report(path, old, new=''):
    """Short report on why old did not match path: closest real lines and an already-applied note; '' if nothing useful."""
    content = _read(path)
    if content is None or not old.strip():
        return ''
    s, c = old.splitlines(), content.splitlines()
    out = []
    w = whitespace_match(s, c) if len(c) <= MAX_LINES else None
    kind = 'only whitespace differs' if w else 'similar lines'
    w = w or similar_window(s, c)
    if w:
        head = f'Closest match in {path}, lines {w[0] + 1}-{w[1]} [actual], {kind}.'
        body = '\n'.join(c[w[0]:w[1]])
        if len(body) > HINT_CHARS:  # WHY no cut text: a truncated line cannot be copied into old_string
            out.append(f'{head} Too long to show: Read offset={w[0] + 1} limit={w[1] - w[0]}.')
        else:
            out.append(f'{head} Copy exact text from here instead of re-reading the file:\n{body}')
    if len(new.strip()) >= 20 and new in content:
        out.append(f'new_string is already in {path}: check that this edit is still needed.')
    return '\n'.join(out)


def edit_hint(data):
    """PostToolUseFailure payload -> advice text for an Edit whose old_string was not found, else ''."""
    if data.get('tool_name') not in ('Edit', 'MultiEdit'):
        return ''
    if 'string to replace not found' not in str(data.get('error') or data.get('tool_response') or '').lower():
        return ''
    inp = data.get('tool_input') or {}
    path = inp.get('file_path') or ''
    for e in inp.get('edits') or [inp]:
        old = e.get('old_string') or ''
        content = _read(path)
        if content is None or old in content:
            continue
        m = match_report(path, old, e.get('new_string') or '')
        if m:
            return 'TOKEN ZOMBIE: ' + m
    return ''


def context(path, code, line_nums, pad=3):
    """Numbered lines around line_nums (1-based, first 5), bad lines marked with a block; gaps shown as ..."""
    lines = code.split('\n')
    bad = sorted({n for n in line_nums if 0 < n <= len(lines)})[:5]
    show = sorted({i for n in bad for i in range(max(1, n - pad), min(len(lines), n + pad) + 1)})
    if not show:
        return ''
    out, prev = [f'{path}:'], 0
    for i in show:
        if prev and i > prev + 1:
            out.append('...')
        out.append(f'{i:>5}{chr(0x2588) if i in bad else "|"} {lines[i - 1]}'[:120])
        prev = i
    return '\n'.join(out)


def _run(args):
    """(return code, combined output tail) of a checker command."""
    try:
        r = subprocess.run(args, capture_output=True, text=True, errors='replace', timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return 2, f'lint command failed to run: {e}'
    return r.returncode, '\n'.join((r.stdout + r.stderr).strip().splitlines()[-40:])


def _found(path, text):
    """Line numbers named as <file>:<n> in checker output."""
    return {int(n) for n in re.findall(re.escape(os.path.basename(path)) + r':(\d+)\b', text)}


def lint_file(path, cmd=None):
    """Errors plus marked source context; '' when clean or no checker applies. cmd is a user linter run on path."""
    code = _read(path)
    if code is None:
        return ''
    full = os.path.abspath(path)  # a name starting with '-' must not become a checker option
    ext = os.path.splitext(path)[1]
    if cmd:
        rc, text = _run(shlex.split(cmd) + [full])
        nums = _found(path, text)
    elif ext == '.py':
        try:
            compile(code, path, 'exec', dont_inherit=True)  # parses only, never runs the code
            return ''
        except (SyntaxError, ValueError, RecursionError) as e:
            line = getattr(e, 'lineno', None) or 0
            end = getattr(e, 'end_lineno', None) or line
            rc, text = 1, f'{type(e).__name__}: {getattr(e, "msg", e)} (line {line})'
            nums = set(range(line, max(line, end) + 1))
    elif ext in ('.js', '.mjs', '.cjs') and shutil.which('node'):
        rc, text = _run(['node', '--check', full])
        nums = _found(path, text)
    elif ext == '.sh' and shutil.which('bash'):
        rc, text = _run(['bash', '-n', full])
        nums = {int(n) for n in re.findall(r'line (\d+):', text)}
    else:
        return ''
    if rc == 0:
        return ''
    return '\n'.join(x for x in (text, context(path, code, nums)) if x)


def main(argv):
    """CLI: important [DIR] | similar FILE SNIPPET_FILE | lint [--cmd CMD] FILE..."""
    if argv and argv[0] == 'aider':
        argv = argv[1:]
    c, rest = (argv[0], argv[1:]) if argv else ('', [])
    if c == 'important':
        print('\n'.join(important_files(rest[0] if rest else '.')) or 'no important files found')
        return 0
    if c == 'similar' and len(rest) == 2:
        old = _read(rest[1])
        m = match_report(rest[0], old or '')
        print(m or 'no close match')
        return 0 if m else 1
    if c == 'lint':
        cmd = None
        if rest[:1] == ['--cmd'] and len(rest) > 1:
            cmd, rest = rest[1], rest[2:]
        if rest:
            bad = 0
            for p in rest:
                if not os.path.isfile(p):
                    print(f'{p}: not found')
                    bad = 1
                    continue
                m = lint_file(p, cmd)
                if m:
                    print(m)
                    bad = 1
            if not bad:
                print('no errors found by the available checks')
            return bad
    print('usage: tz aider important [DIR] | similar FILE SNIPPET_FILE | lint [--cmd CMD] FILE...')
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
