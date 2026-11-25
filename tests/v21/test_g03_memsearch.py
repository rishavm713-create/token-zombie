# tzmemsearch: parity with memsearch tests (chunker, expand section), incremental index, search/expand.
import contextlib, io, os, shutil, tempfile
from harness import ok, done, Z
import tzmemsearch as m

C = lambda t, **kw: m.chunk(t, **kw)

# chunker parity (upstream tests/test_chunker.py)
ok('empty', C('') == [])
p = C('Just some text without any heading.\n\nMore text.')
ok('preamble', len(p) == 1 and p[0]['heading'] == '' and p[0]['level'] == 0)
h = [c['heading'] for c in C('# Title\n\nSome intro text.\n\n## Section A\n\nContent A here.\n\n## Section B\n\nContent B here.\n')]
ok('heading split', h == ['Title', 'Section A', 'Section B'])
c = C('# T\n## A\ntext a\n## B\ntext b')
ok('bodyless heading dropped, lines', [(x['heading'], x['start'], x['end']) for x in c] == [('A', 2, 3), ('B', 4, 5)])
ok('hash', C('hello')[0]['hash'] == '2cf24dba5fb0a30e')
ok('hash ignores source, id does not', C('# H\n\nWorld')[0]['hash'] == C('# H\n\nWorld')[0]['hash']
   and m.chunk_id('a', c[0]) != m.chunk_id('b', c[0]) and len(m.chunk_id('a', c[0])) == 16)
s = C('## Session 03:16\n\n## Session 03:17\n\n### 03:18\n<!-- session:a turn:b transcript:/p -->\n- something important\n')
ok('empty session headings filtered', [x['heading'] for x in s] == ['03:18'])
ok('comment only dropped', C('### 08:00\n<!-- session:aaa -->\n') == [])
ok('clean', m.clean('### 1\n<!-- session:x transcript:/p -->\n- chunking') == '### 1\n\n- chunking'.replace('\n\n', '\n\n'))
ok('clean collapses', m.clean('a\n\n<!-- x -->\n\n\nb') == 'a\n\nb')
big = C('# Big Section\n\n' + '\n\n'.join('Paragraph %d. ' % i + 'x' * 200 for i in range(20)), size=500)
ok('large split keeps heading', len(big) > 1 and all(x['heading'] == 'Big Section' and len(x['content']) <= 500 for x in big))
t = C('# Big Section\n\n' + '\n'.join(['alpha ' * 18, 'beta ' * 18, 'tail ' * 18]), size=120, overlap=0)
ok('tail flushed', len(t) >= 2 and any('tail' in x['content'] for x in t) and t[-1]['end'] >= t[-1]['start'])
L = C('\n'.join(['short', 'x' * 9500, 'tail']))
ok('long line bounded', len(L) > 1 and all(len(x['content']) <= 1500 for x in L) and any('tail' in x['content'] for x in L))
cj = C('这是一个很长的中文句子用来测试分割。' * 8, size=40)
ok('cjk boundary', len(cj) > 1 and all(len(x['content']) <= 40 for x in cj) and all(x['content'].endswith('。') for x in cj[:-1]))
mx = C('请检查 Redis cache 是否命中。Then verify the fallback path works!' * 5, size=45)
ok('mixed boundary', len(mx) > 1 and all(x['content'].endswith(('。', '!')) for x in mx[:-1]))
ok('ascii dots kept', m.split_long('see v1.2.3 now. ' + 'z' * 30, 30)[0] == 'see v1.2.3 now. ')

# extract_section parity (upstream tests/test_cli_expand_section.py)
LOG = ('## Session 10:00\n\n### 10:01\n<!-- session:AAA turn:t1 transcript:/tmp/a.jsonl -->\n- Fixed the login redirect bug.\n\n'
       '### 10:05\n<!-- session:AAA turn:t2 transcript:/tmp/a.jsonl -->\n- Added rate limiting to the API.\n')
body, a, b = m.extract_section(LOG.splitlines(), 7, 3)
ok('section starts at own heading', (a, b) == (7, 9) and body.startswith('### 10:05') and 'turn:t1' not in body)
ok('walks back', m.extract_section(['## A', '', 'first', '', 'second', '## B', 'o'], 5, 2)[1:] == (1, 5))
ok('children kept, peer excluded', m.extract_section(['## Parent', 'intro', '### Child', 'detail', '## Peer', 'o'], 1, 2)
   == ('## Parent\nintro\n### Child\ndetail', 1, 4))
ok('hash lines are not headings', m.extract_section(['## A', '#!/bin/sh', '#tag', 'x'], 1, 2)[2] == 4)

# rrf parity (research spec example 8)
ok('rrf both first', abs(m.rrf([['d'], ['d']])['d'] - 1) < 1e-9)
ok('rrf one list', abs(m.rrf([['d'], []])['d'] - .5) < 1e-9)
ok('rrf 1st+2nd', round(m.rrf([['d', 'e'], ['e', 'd']])['d'], 4) == 0.9919)


# index + recall
def put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


T = os.path.realpath(tempfile.mkdtemp())
R, db, old_cwd, old_home = os.path.join(T, 'proj'), os.path.join(T, 'ms.db'), os.getcwd(), os.environ.get('HOME')
try:
    day = os.path.join(R, 'handoffs', '2026-09-24.md')
    put(day, LOG)
    put(os.path.join(R, 'HANDOFF.md'), '# H\n\nzebra enclosure notes\n')
    put(os.path.join(R, '.hidden', 'x.md'), '# x\n\nsecretzebra\n')
    put(os.path.join(R, 'sub', 'deep.md'), '# d\n\nnarwhal horn\n')
    os.chdir(R)
    r = m.index(db=db)
    ok('default index', r['files'] == 2 and r['added'] == 3 and r['failed'] == [])
    ok('reindex writes nothing', m.index(db=db)['added'] == 0)
    hit = m.search('rate limiting', db=db)
    ok('search hit', hit and hit[0]['source'] == day and hit[0]['heading'] == '10:05' and hit[0]['start'] == 7 and hit[0]['score'] == 1.0)
    ok('comment ids not searchable', m.search('AAA', db=db) == [])
    ok('no match / empty / odd query', m.search('nonexistentterm', db=db) == [] and m.search('"*(', db=db) == []
       and m.search('x', db=os.path.join(T, 'none.db')) == [])
    e = m.expand(hit[0]['id'], db=db)
    ok('expand section + anchor', e['start'] == 7 and e['content'].startswith('### 10:05') and e['anchor']['turn'] == 't2')
    ok('expand lines', m.expand(hit[0]['id'], around=1, db=db)['start'] == 6)
    ok('expand unknown', m.expand('0' * 16, db=db) is None)
    put(day, 'new first line\n\n' + LOG)
    ok('expand follows moved chunk', m.expand(hit[0]['id'], db=db)['start'] == 9)
    r = m.index(db=db)
    ok('moved chunks re-indexed', r['added'] == 3 and r['removed'] == 2)
    new = m.search('rate limiting', db=db)[0]['id']
    put(day, LOG.replace('rate limiting', 'throttling'))
    ok('expand reports out of sync', 'out of sync' in m.expand(new, db=db)['error'])
    m.index(db=db)
    ok('edit replaces', m.search('limiting', db=db) == [] and m.search('throttling', db=db))
    put(os.path.join(R, 'handoffs', 'copy.md'), LOG.replace('rate limiting', 'throttling'))
    m.index(db=db)
    ok('same content shown once', len(m.search('throttling', db=db)) == 1)
    os.remove(day); os.remove(os.path.join(R, 'handoffs', 'copy.md'))
    ok('expand deleted file', 'error' in m.expand(m.search('throttling', db=db)[0]['id'], db=db))
    ok('deleted files pruned (day + copy, 2 chunks each)', m.index(db=db)['removed'] == 4 and m.search('throttling', db=db) == [])
    m.index([R], db=db)
    ok('explicit dir recursive, hidden skipped', m.search('narwhal', db=db) and m.search('secretzebra', db=db) == [])
    ok('default run keeps explicit rows', m.index(db=db)['removed'] == 0 and m.search('narwhal', db=db))
    shutil.rmtree(os.path.join(R, 'sub'))
    m.index([R], db=db)
    ok('explicit dir prunes', m.search('narwhal', db=db) == [])
    other = os.path.join(T, 'proj-2')
    put(os.path.join(other, 'HANDOFF.md'), '# O\n\nzebra elsewhere\n')
    m.index([os.path.join(other, 'HANDOFF.md')], db=db)
    ok('prefix scope', len(m.search('zebra', db=db)) == 2 and [x['source'] for x in m.search('zebra', prefix=R, db=db)]
       == [os.path.join(R, 'HANDOFF.md')])
    os.utime(os.path.join(R, 'HANDOFF.md'), (1, 1))
    ok('recent fuses mtime', len(m.search('zebra', recent=True, db=db)) == 2 and m.search('zebra', k=1, db=db).__len__() == 1)
    ok('force rewrites', m.rebuild([R], db=db)['added'] == 1 and len(m.search('zebra', db=db)) == 2)
    put(db, 'not a database ' * 100)
    ok('damaged index rebuilt', m.rebuild([R], db=db)['added'] == 1 and m.search('zebra', db=db))
    m.USE_FTS = False
    fb = os.path.join(T, 'fb.db')
    m.index([R, other], db=fb)
    ok('bm25 fallback', len(m.search('zebra', db=fb)) == 2 and len(m.search('zebra', prefix=R, db=fb)) == 1)
    m.USE_FTS = True
    # CLI
    os.environ['HOME'] = T

    def run(*argv):
        o = io.StringIO()
        with contextlib.redirect_stdout(o), contextlib.redirect_stderr(o):
            code = m.main(list(argv))
        return code, o.getvalue()

    ok('cli index', run('index')[0] == 0 and os.path.isfile(m.db_path()) and m.db_path().startswith(T))
    code, out = run('search', 'zebra', 'notes')
    ok('cli search', code == 0 and 'expand ID' in out)
    code, ex = run('expand', out.split()[0], '--max', '5')
    ok('cli expand capped', code == 0 and 'cut ' in ex and 'enclosure' not in ex)
    ok('cli misses', run('search', 'qqqq')[0] == 1 and run('expand', 'nope')[0] == 1 and run()[0] == 2)
finally:
    os.chdir(old_cwd)
    if old_home is not None:
        os.environ['HOME'] = old_home
    shutil.rmtree(T, ignore_errors=True)

done()
