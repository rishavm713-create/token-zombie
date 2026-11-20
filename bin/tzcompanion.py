#!/usr/bin/env python3
# Companion: tiny local server, 127.0.0.1 only, token-authenticated, serves status.json + a small always-visible page.
# Token file ~/.claude/token-zombie/companion.token (mode 600), send as ?token= or header X-TZ-Token.
# NOT built (BLOCKED): native always-on-top overlay (Swift/Electron needs toolchain install approval). Open the page in a pinned/PiP window instead.
import hmac, json, os, secrets, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tzmascot import mascot_state, svg, EMOJI

PAGE = """<!doctype html><meta charset=utf-8><title>TZ</title><body style="margin:0;font:13px system-ui;background:#111;color:#ddd;text-align:center">
<div id=m style="font-size:40px"></div><div id=t></div>
<script>const q=new URLSearchParams(location.search).get('token');
async function u(){try{const r=await fetch('/status.json?token='+q);const s=await r.json();
document.getElementById('m').textContent=s.emoji||'😴';
document.getElementById('t').textContent=(s.mascot||'SLEEP')+' '+(s.level||'?')+' ctx '+(s.ctx_pct??'?')+'% risk '+(s.risk||'?')}catch(e){document.getElementById('t').textContent='offline'}}
u();setInterval(u,5000)</script>"""


def token():
    p = os.path.expanduser('~/.claude/token-zombie/companion.token')
    if not os.path.exists(p):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.write(fd, secrets.token_hex(16).encode())
        os.close(fd)
    return open(p).read().strip()


def host_ok(h, port):
    """DNS-rebinding guard: only accept Host 127.0.0.1:<port> or localhost:<port>."""
    return (h or '') in (f'127.0.0.1:{port}', f'localhost:{port}')


def handler(tok, port=None):
    import http.server
    from urllib.parse import urlparse, parse_qs

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            u = urlparse(self.path)
            if port and not host_ok(self.headers.get('Host'), port):
                self.send_response(403); self.end_headers(); self.wfile.write(b'bad host'); return
            given = (parse_qs(u.query).get('token') or [self.headers.get('X-TZ-Token', '')])[0]
            if not hmac.compare_digest(given, tok):
                self.send_response(401); self.end_headers(); self.wfile.write(b'token required'); return
            if u.path == '/status.json':
                import tzbus
                body = json.dumps(tzbus.read_bus()).encode()  # always valid JSON, even when status.json is missing/corrupt
                ct = 'application/json'
            elif u.path == '/':
                body, ct = PAGE.encode(), 'text/html; charset=utf-8'
            else:
                self.send_response(404); self.end_headers(); return
            self.send_response(200); self.send_header('Content-Type', ct); self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff'); self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; connect-src 'self'")
            self.end_headers(); self.wfile.write(body)

        def do_POST(self):
            self.send_response(405); self.end_headers()
        do_PUT = do_DELETE = do_POST

        def log_message(self, *a):
            pass
    return H


def parse_port(argv, dflt):
    try:
        p = int(argv[argv.index('--port') + 1]) if '--port' in argv else dflt
        assert 1024 <= p <= 65535
        return p
    except (ValueError, IndexError, AssertionError):
        print('tz: --port must be a number 1024-65535', file=sys.stderr)
        return None


def main(argv):
    import socketserver
    socketserver.TCPServer.allow_reuse_address = True  # restart right after stop
    port = parse_port(argv, 8766)
    if port is None:
        return 2
    tok = token()
    if '--print-token-path' in argv:
        print(os.path.expanduser('~/.claude/token-zombie/companion.token'))
        return 0
    with socketserver.TCPServer(('127.0.0.1', port), handler(tok, port)) as srv:
        print(f'http://127.0.0.1:{port}/?token=<contents of companion.token>  (Ctrl-C to stop)')
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
