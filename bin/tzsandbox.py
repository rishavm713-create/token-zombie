#!/usr/bin/env python3
"""tz sandbox: run a script or commands, show only a bounded part of what they print; keep the rest for `tz recall`.
Independent implementation from the behaviour described in the context-mode README (ELv2): no code, prompts or assets copied.
"Sandbox" is about OUTPUT only: the code runs as you, with your files, network and environment. It is NOT isolation,
so do not allow-list `tz sandbox` in Claude Code permissions (that would allow any code)."""
import argparse, os, shlex, shutil, signal, sqlite3, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tzmem, tzops, tzout

MAX = 8000  # chars shown; stays under tzout.OTHER_MAX so the PostToolUse trim does not cut the result a second time
CAP = 5_000_000  # bytes read back from one run: a runaway printer must not exhaust memory or fill the recall store
SNIP, TOP = 800, 3  # chars per matching part, parts per --find query
PRELOAD = ('LD_PRELOAD', 'DYLD_INSERT_LIBRARIES', 'NODE_OPTIONS', 'BASH_ENV')  # inject code before the script starts
LANGS = {'sh': '.sh', 'py': '.py', 'js': '.js'}


def interpreter(lang):
    """Path of the runtime for lang, or None when it is not installed."""
    if lang == 'py':
        return sys.executable
    if lang == 'js':
        return shutil.which('node')
    return shutil.which('bash') or shutil.which('sh')


def blocked(cmds):
    """Reason the first destructive shell command is refused, else ''."""
    for c in cmds:  # without this, wrapping a command in `tz sandbox` could hide it from the Bash guard
        ok, why = tzops.safe(c, os.getcwd())
        if not ok:
            return why
    return ''


def kill_tree(p):
    """Kill the child and everything it started."""
    try:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/T', '/F', '/PID', str(p.pid)], capture_output=True)
        else:
            os.killpg(p.pid, signal.SIGKILL)
    except OSError:
        pass
    p.wait()


def execute(argv, timeout, env):
    """Run argv (no shell) -> (exit code, printed text, bytes printed). Timeout gives 124 and keeps partial output."""
    with tempfile.TemporaryFile() as out:  # a file, not a pipe: a background grandchild holding a pipe would hang us
        try:
            p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, env=env,
                                 start_new_session=os.name != 'nt')
        except OSError as e:
            return 127, f'cannot start {argv[0]}: {e.strerror}', 0
        try:
            code = p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_tree(p)
            code = 124
        except BaseException:
            kill_tree(p)
            raise
        size = out.seek(0, os.SEEK_END)
        out.seek(0)
        return code, out.read(CAP).decode('utf-8', 'replace'), size


def run_code(code, lang, timeout, env):
    """Write code to a private temp script and execute it in the current folder."""
    with tempfile.TemporaryDirectory(prefix='tz-sandbox-') as d:
        path = os.path.join(d, 'script' + LANGS[lang])
        with open(path, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(code)
        return execute([interpreter(lang), path], timeout, env)


def _rank(rows, query):
    """Best TOP parts for query: FTS5 bm25, or tzmem's pure-Python BM25 when FTS5 is missing."""
    toks = tzmem._tok(query)
    if not toks:
        return []
    if tzmem.USE_FTS:
        db = sqlite3.connect(':memory:')
        try:
            db.execute('create virtual table t using fts5(body, n unindexed)')
            db.executemany('insert into t values (?,?)', [(r[3], i) for i, r in enumerate(rows)])
            m = ' OR '.join(f'"{t}"' for t in toks)
            hits = db.execute('select n from t where t match ? order by bm25(t) limit ?', (m, TOP)).fetchall()
            return [rows[n] for n, in hits]
        except sqlite3.OperationalError:
            pass
        finally:
            db.close()
    return [r for _, r in tzmem._bm25(rows, query)[:TOP]]


def _window(text, query):
    """At most SNIP chars of text, centred on the first query word (one minified line can be megabytes)."""
    if len(text) <= SNIP:
        return text
    low = text.lower()
    at = min((i for i in (low.find(t) for t in tzmem._tok(query)) if i >= 0), default=0)
    a = max(0, min(at - SNIP // 4, len(text) - SNIP))
    return text[a:a + SNIP]


def find(stored, queries, budget):
    """stored [(recall id, text)] -> matching parts for each query, within budget chars."""
    rows = [(rid, line, None, body) for rid, text in stored for line, body in tzmem.chunks(text)]
    out, seen, used = [], set(), 0
    for q in queries:
        hits = _rank(rows, q)
        if not hits:
            out.append(f'-- no match for "{q}"')
        for rid, line, _, body in hits:
            if (rid, line) in seen:
                continue
            part = f'-- "{q}" in {rid}, from line {line}:\n{_window(body, q)}'
            if used + len(part) > budget:
                out.append('-- more matches cut: narrow the query or use tz recall')
                return '\n'.join(out)
            seen.add((rid, line)); used += len(part); out.append(part)
    return '\n'.join(out)


def report(results, queries, limit):
    """results [(label, exit, text, bytes)] -> what the model gets to see."""
    many = len(results) > 1
    heads = [f'== [{i}] {lb[:60]} (exit {c})' for i, (lb, c, _, _) in enumerate(results, 1)] if many else ['']
    total = sum(len(t) for _, _, t, _ in results)
    out, stored = [], []
    for head, (_, code, text, size) in zip(heads, results):
        if head:
            out.append(head)
        if total <= limit:
            out.append(text.rstrip('\n'))
        elif queries:
            rid = tzout.spill(text)
            stored.append((rid, text))
            out.append(f'stored: {len(text)} chars [actual]. Full text: tz recall {rid} --grep PATTERN')
        else:
            got = tzout.cut(text, max(200, limit // len(results)), False)
            out.append((got[0] if got else text).rstrip('\n'))
        if size > CAP:
            out.append(f'[output was {size} bytes [actual]; only the first {CAP} were read]')
        if code and not many:
            out.append(f'[exit {code}{" = timeout" if code == 124 else ""}]')
    if stored:
        out.append(find(stored, queries, limit))
    shown = '\n'.join(x for x in out if x)
    if total > limit:
        shown += f'\n[sandbox: {total} chars printed, {len(shown)} shown [actual]]'
    return shown


def parser():
    """CLI options."""
    p = argparse.ArgumentParser(prog='tz sandbox', description='Run code or a command; show only a bounded part of the output.',
                                epilog='Runs with your own rights (output filter, not isolation). Command form: tz sandbox [opts] -- CMD ARGS')
    p.add_argument('-c', '--code', action='append', default=[], help="script text; '-' reads stdin; repeat for a batch")
    p.add_argument('--lang', choices=sorted(LANGS), default='sh')
    p.add_argument('--file', help='data file for the script, passed as $TZ_FILE')
    p.add_argument('--find', action='append', default=[], metavar='WORDS', help='big output: show only matching parts; repeatable')
    p.add_argument('--index', metavar='PATH', help='store a text file for recall/--find without printing it')
    p.add_argument('--max', type=int, default=MAX, help=f'chars shown (default {MAX})')
    p.add_argument('--timeout', type=float, default=120, help='seconds per command (default 120)')
    return p


def index(path, queries, limit):
    """Keep a file in the recall store; print its id and any --find matches."""
    try:
        with open(path, 'rb') as fh:
            text = fh.read(CAP + 1)
    except OSError as e:
        print(f'cannot read {path}: {e.strerror}'); return 2
    if len(text) > CAP:
        print(f'{path} is over {CAP} bytes: not stored'); return 2
    text = text.decode('utf-8', 'replace')
    rid = tzout.spill(text)
    print(f'stored {path}: {len(text)} chars [actual]. Full text: tz recall {rid} --grep PATTERN')
    if queries:
        print(find([(rid, text)], queries, limit))
    return 0


def main(argv):
    """`tz sandbox` entry; returns the first failing command's exit code, 2 usage, 3 refused."""
    cut = argv.index('--') if '--' in argv else len(argv)
    cmd = argv[cut + 1:]
    try:
        a = parser().parse_args(argv[:cut])
    except SystemExit as e:
        return int(e.code or 0)
    if a.max < 200 or a.timeout <= 0:
        print('--max must be >= 200 and --timeout > 0'); return 2
    if a.index and not (a.code or cmd):
        return index(a.index, a.find, a.max)
    if bool(a.code) == bool(cmd) or a.index:
        print('usage: tz sandbox [--lang sh|py|js] -c CODE [-c CODE..] | -- CMD ARGS | --index PATH  [--find WORDS]'); return 2
    if a.code and not interpreter(a.lang):
        print(f'no runtime for --lang {a.lang} on PATH'); return 2
    env = {k: v for k, v in os.environ.items() if k not in PRELOAD}
    if a.file:
        if not os.path.isfile(a.file):
            print(f'no such file: {a.file}'); return 2
        env['TZ_FILE'] = os.path.abspath(a.file)
    codes = [sys.stdin.read() if c == '-' else c for c in a.code]
    why = blocked([shlex.join(cmd)] if cmd else codes if a.lang == 'sh' else [])  # py/js cannot be parsed: see module doc
    if why:
        print(f'refused: {why}. Nothing was run.'); return 3
    if cmd:
        results = [(shlex.join(cmd), *execute(cmd, a.timeout, env))]
    else:
        results = [((c.strip().splitlines() or [''])[0], *run_code(c, a.lang, a.timeout, env)) for c in codes]
    text = report(results, a.find, a.max)
    if text:
        sys.stdout.buffer.write((text + '\n').encode('utf-8', 'replace'))  # Windows consoles are not always UTF-8
    return next((r[1] for r in results if r[1]), 0)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
