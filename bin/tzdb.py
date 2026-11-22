#!/usr/bin/env python3
# One local SQLite ledger (~/.claude/token-zombie/tz.db): events, alerts (evidence -> intervention -> outcome), vault (spilled originals).
# Every writer fails open: a DB problem never blocks a hook. No network. Counts are MEASURED from hook events.
import json, os, sqlite3, sys, time

SCHEMA = '''
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, t INT, sid TEXT, kind TEXT, data TEXT);
CREATE INDEX IF NOT EXISTS ev_k ON events(kind, t);
CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY, t INT, sid TEXT, ev TEXT, msg TEXT, size0 INT, prompts INT DEFAULT 0, outcome TEXT DEFAULT 'open', intervention TEXT DEFAULT '', t_res INT);
CREATE TABLE IF NOT EXISTS vault(id TEXT, sid TEXT, t INT, tool TEXT, target TEXT, orig INT, shown INT, PRIMARY KEY(id, sid));
'''


def _path():
    return os.path.join(os.path.expanduser('~/.claude/token-zombie'), 'tz.db')


def _db():
    os.makedirs(os.path.dirname(_path()), exist_ok=True)
    c = sqlite3.connect(_path(), timeout=1)
    c.executescript(SCHEMA)
    return c


def _w(fn):
    try:
        c = _db()
        try:
            r = fn(c); c.commit(); return r
        finally:
            c.close()
    except Exception:
        return None


def record(kind, sid='', **data):
    return _w(lambda c: c.execute('INSERT INTO events(t,sid,kind,data) VALUES(?,?,?,?)', (int(time.time()), sid, kind, json.dumps(data)[:500])))


def alert_open(sid, ev, msg, size0):
    """An alert was shown. evidence = the message + transcript size (bytes, MEASURED) at that moment."""
    return _w(lambda c: c.execute('INSERT INTO alerts(t,sid,ev,msg,size0) VALUES(?,?,?,?,?)', (int(time.time()), sid, ev, msg[:300], int(size0))))


def alert_resolve(sid, ev, size):
    """Called on each later event. acted = compaction happened or the transcript shrank >=20%; ignored = 3 more prompts passed with neither."""
    def fn(c):
        for aid, size0, pr in c.execute("SELECT id,size0,prompts FROM alerts WHERE sid=? AND outcome='open'", (sid,)).fetchall():
            iv = 'compact' if ev in ('PreCompact', 'PostCompact') else ('smaller-context' if size0 and size <= size0 * 0.8 else '')
            if iv:
                c.execute("UPDATE alerts SET outcome='acted', intervention=?, t_res=? WHERE id=?", (iv, int(time.time()), aid))
            elif ev == 'UserPromptSubmit':
                if pr + 1 >= 3:
                    c.execute("UPDATE alerts SET outcome='ignored', prompts=?, t_res=? WHERE id=?", (pr + 1, int(time.time()), aid))
                else:
                    c.execute('UPDATE alerts SET prompts=? WHERE id=?', (pr + 1, aid))
    return _w(fn)


def vault_add(rid, sid, tool, target, orig, shown):
    return _w(lambda c: c.execute('INSERT OR REPLACE INTO vault VALUES(?,?,?,?,?,?,?)', (rid, sid, int(time.time()), tool, str(target)[:200], int(orig), int(shown))))


def main(argv):
    try:
        c = _db()
    except Exception as e:
        print(f'ledger unavailable: {e}'); return 1
    a = argv[0] if argv else ''
    if a == '--alerts':
        rows = c.execute('SELECT outcome, intervention, COUNT(*) FROM alerts GROUP BY 1,2').fetchall()
        print('alerts (evidence -> intervention -> outcome) [MEASURED]:' if rows else 'alerts: none recorded yet')
        for o, i, n in rows:
            print(f'  {o:8} {i or "-":16} {n}')
        for t, ev, m, o in c.execute('SELECT t,ev,msg,outcome FROM alerts ORDER BY id DESC LIMIT 5'):
            print(f'  {time.strftime("%m-%d %H:%M", time.localtime(t))} [{ev}] {o}: {m[:90]}')
    elif a == '--vault':
        tool = argv[argv.index('--tool') + 1] if '--tool' in argv else None
        fil = argv[argv.index('--file') + 1] if '--file' in argv else None
        q, p = 'SELECT id,sid,tool,target,orig,shown FROM vault WHERE 1=1', []
        if tool:
            q += ' AND tool=?'; p.append(tool)
        if fil:
            q += ' AND target LIKE ?'; p.append(f'%{fil}%')
        rows = c.execute(q + ' ORDER BY t DESC LIMIT 30', p).fetchall()
        print('vault: originals kept (id, session, tool, target, original vs model-visible chars) [MEASURED]:' if rows else 'vault: nothing matches')
        for r in rows:
            print(f'  {r[0]} {r[1][:8]} {r[2]} {r[3]} orig={r[4]:,} shown={r[5]:,}  -> tz recall {r[0]}')
    else:
        k = argv[argv.index('--kind') + 1] if '--kind' in argv else None
        rows = c.execute('SELECT kind, COUNT(*), MAX(t) FROM events' + (' WHERE kind=?' if k else '') + ' GROUP BY kind ORDER BY 2 DESC', [k] if k else []).fetchall()
        print(f'ledger {_path()} [MEASURED counts]' if rows else 'ledger: empty (hooks write here once active)')
        for kd, n, t in rows:
            print(f'  {kd:22} {n:6}  last {time.strftime("%m-%d %H:%M", time.localtime(t))}')
        print('  more: tz ledger --alerts | --vault [--tool T] [--file F]')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
