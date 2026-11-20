#!/usr/bin/env python3
# Dashboard: static self-contained HTML from status.json + ledger + bench evidence + registry. No AI calls, no external requests.
# `tz dash --out f.html` ; `tz dash --serve [--port N]` binds 127.0.0.1 only.
import html, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tzmascot import mascot_state, svg, ASCII


def S():
    return os.path.expanduser('~/.claude/token-zombie')


def _j(name, d):
    try:
        v = json.load(open(os.path.join(S(), name)))
        return v if isinstance(v, type(d)) else d  # wrong-shaped file => empty, never a crash
    except Exception:
        return d


def bench_results(ev=None):
    """Read tests/ab evidence dir summary files (aggregate.json + *.json with total). MEASURED only if the files exist."""
    ev = ev or os.environ.get('TZ_AB_EVIDENCE') or os.path.join(S(), 'ab-evidence')
    out = []
    if os.path.isdir(ev):
        for f in sorted(os.listdir(ev)):
            if f.endswith('.json'):
                try:
                    j = json.load(open(os.path.join(ev, f)))
                except Exception:
                    continue
                out.append((f, j.get('total'), j.get('status', '')))
    return out


def render():
    import tzbus
    s = tzbus.read_bus()
    st = mascot_state(s)
    led = _j('ledger.json', [])[-20:]
    reg = {k: r for k, r in _j('registry.json', {}).items() if isinstance(r, dict)}
    e = html.escape
    rows = ''.join(f'<tr><td>{e(str(k))}</td><td>{e(str(v))}</td></tr>' for k, v in s.items() if k not in ('limits', 'tokens', 'label'))
    b = bench_results()
    brow = ''.join(f'<tr><td>{e(f)}</td><td>{t}</td><td>{e(str(x))}</td></tr>' for f, t, x in b) or '<tr><td colspan=3>no A/B evidence: UNKNOWN (not run)</td></tr>'
    rrow = ''.join(f"<tr><td>{e(k)}</td><td>{e(r.get('grade',''))}</td><td>{e(r.get('license',''))}</td></tr>" for k, r in reg.items()) or '<tr><td colspan=3>empty</td></tr>'
    return f"""<!doctype html><meta charset=utf-8><title>TOKEN ZOMBIE</title>
<style>body{{font:14px system-ui;margin:2em;background:#111;color:#ddd}}td{{padding:2px 10px;border-bottom:1px solid #333}}h2{{color:#9c6}}</style>
<h1>TOKEN ZOMBIE {svg(st)} <small>{e(st)} {e(ASCII[st])}</small></h1>
<h2>Status (bus; ctx% actual/est, minutes est)</h2><table>{rows or '<tr><td>no status: run tz sup tick</td></tr>'}</table>
<h2>Ledger</h2><pre>{e(json.dumps(led, indent=1)[:2000])}</pre>
<h2>A/B benchmark evidence (MEASURED only if present)</h2><table>{brow}</table>
<h2>Registry</h2><table>{rrow}</table>"""


def main(argv):
    if '--serve' in argv:
        import http.server, socketserver, tzcompanion
        port = tzcompanion.parse_port(argv, 8765)
        if port is None:
            return 2
        tok = tzcompanion.token()  # same token file as the companion
        base = tzcompanion.handler(tok, port)

        class H(base):  # companion handler already enforces Host + token; '/' now serves the full dashboard
            def do_GET(self):
                from urllib.parse import urlparse
                if urlparse(self.path).path == '/':
                    given = self.headers.get('X-TZ-Token') or (self.path.split('token=')[-1].split('&')[0] if 'token=' in self.path else '')
                    import hmac
                    if tzcompanion.host_ok(self.headers.get('Host'), port) and hmac.compare_digest(given, tok):
                        b = render().encode()
                        self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8'); self.send_header('Cache-Control', 'no-store')
                        self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'"); self.end_headers(); self.wfile.write(b)
                        return
                return super().do_GET()
        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer(('127.0.0.1', port), H) as srv:
            print(f'http://127.0.0.1:{port}/?token=<contents of ~/.claude/token-zombie/companion.token>  (Ctrl-C to stop)')
            try:
                srv.serve_forever()
            except KeyboardInterrupt:
                pass
        return 0
    out = argv[argv.index('--out') + 1] if '--out' in argv else None
    if not out:
        print('usage: tz dash --out FILE | --serve [--port N]', file=sys.stderr)
        return 2
    open(out, 'w').write(render())
    print(f'wrote {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
