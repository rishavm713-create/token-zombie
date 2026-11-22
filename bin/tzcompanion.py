#!/usr/bin/env python3
# Companion: token-authenticated, localhost-only live dashboard. Reads local status + savings ledger; no network/AI.
# Token file ~/.claude/token-zombie/companion.token (mode 600), send as ?token= or header X-TZ-Token.
import hmac, json, os, secrets, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tzmascot import mascot_state, svg, EMOJI

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark"><title>TOKEN ZOMBIE</title>
<style>
:root{color-scheme:dark;--bg:#050505;--panel:#101010;--line:#303030;--green:#7CFC00;--muted:#A3A3A3;--white:#F5F5F5}
*{box-sizing:border-box}body{margin:0;min-height:100vh;background:var(--bg);color:var(--white);font:15px/1.4 Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;padding:24px}
.shell{max-width:1320px;margin:34px auto}.top-wrap{background:#252525;border-radius:24px;padding:12px 14px 54px;margin-bottom:18px;box-shadow:0 14px 38px #0005}
.top{min-height:150px;border:1.5px solid #35b95a;border-radius:24px;background:#292929;display:flex;align-items:center;gap:clamp(18px,3vw,44px);padding:20px 30px;flex-wrap:wrap;box-shadow:0 0 0 1px #35ad5520}
.brand{display:flex;align-items:center;gap:22px;min-width:260px;flex:1}.zombie{width:104px;height:104px;display:grid;place-items:center;flex:none}.zombie svg{width:104px;height:104px;filter:drop-shadow(0 5px 7px #0008)}.wordmark{font-size:clamp(22px,2vw,30px);font-weight:650;white-space:nowrap;letter-spacing:-.8px}
.metrics{display:flex;align-items:center;justify-content:space-around;gap:clamp(14px,2.6vw,38px);flex:3;flex-wrap:wrap}.metric{text-align:center;min-width:112px}.value{font-size:clamp(26px,2.4vw,34px);font-weight:650;letter-spacing:-1px;font-variant-numeric:tabular-nums}.value.saved{color:#43b765}.label{color:#b0b0b0;font-size:clamp(11px,1.15vw,15px);letter-spacing:.35px;text-transform:uppercase;white-space:nowrap}
.state{display:flex;align-items:center;gap:12px;white-space:nowrap;font-size:clamp(15px,1.5vw,21px);padding:10px 16px}.dot{width:13px;height:13px;border-radius:50%;background:#92929d}.dot.live{background:#43b765;box-shadow:0 0 12px #43b76580}
.sub{margin:18px 4px;color:var(--muted);display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}.sub strong{color:var(--white);font-weight:550}.foot{margin-top:30px;color:#777;font-size:12px;letter-spacing:.8px}@media(max-width:760px){body{padding:12px}.shell{margin:12px auto}.top-wrap{padding:10px 10px 28px}.top{gap:16px;padding:16px;justify-content:center}.brand{min-width:100%;justify-content:center}.zombie,.zombie svg{width:82px;height:82px}.metrics{flex:1 1 100%;gap:18px}.metric{min-width:calc(50% - 18px)}.state{width:100%;justify-content:center}.value{font-size:26px}}
</style></head><body><main class="shell">
<section class="top-wrap"><header class="top" aria-label="TOKEN ZOMBIE live status">
<div class="brand"><div class="zombie" id="mascot" aria-hidden="true">🧟</div><div class="wordmark">TOKEN <b>ZOMBIE</b></div></div>
<div class="metrics">
<div class="metric"><div class="value" id="agents">—</div><div class="label">Agents</div></div>
<div class="metric"><div class="value" id="skills">—</div><div class="label">Skills used</div></div>
<div class="metric"><div class="value saved" id="saved">—</div><div class="label">Tokens saved</div></div>
<div class="metric"><div class="value" id="optimizations">—</div><div class="label">Optimizations</div></div>
</div><div class="state"><span class="dot" id="dot"></span><span id="mode">CONNECTING</span></div>
</header></section>
<div class="sub"><span><strong id="level">Waiting for local status</strong> · Context <strong id="context">—</strong> · Risk <strong id="risk">—</strong></span><span id="updated">Refreshing every 5 seconds</span></div>
<div class="foot">LOCAL-FIRST · LIVE DATA FROM YOUR TOKEN ZOMBIE INSTALLATION · NO CLOUD TELEMETRY</div>
</main><script>
const token=new URLSearchParams(location.search).get('token');
const fmt=n=>{if(n===null||n===undefined||!Number.isFinite(Number(n)))return '—';n=Number(n);return n>=1e6?(n/1e6).toFixed(1)+'M':n>=1e3?(n/1e3).toFixed(1)+'K':Math.round(n).toLocaleString()};
async function refresh(){try{const r=await fetch('/status.json?token='+encodeURIComponent(token||''),{cache:'no-store'});if(!r.ok)throw Error('offline');const s=await r.json();

document.getElementById('agents').textContent=fmt(s.agents_running??s.agent_count);
document.getElementById('skills').textContent=fmt(s.skills_used??s.skill_count);
document.getElementById('saved').textContent=fmt(s.tokens_saved_measured??s.tokens_saved);
document.getElementById('optimizations').textContent=fmt(s.optimizations??s.optimization_count);
document.getElementById('level').textContent=s.level||'Status available';
document.getElementById('context').textContent=s.ctx_pct===undefined?'—':s.ctx_pct+'%';
document.getElementById('risk').textContent=s.risk||'—';
const active=s.activity==='working';document.getElementById('dot').classList.toggle('live',active);document.getElementById('mode').textContent=active?'ACTIVE':s.activity==='idle'?'IDLE':'STATUS';
document.getElementById('updated').textContent='Updated '+new Date().toLocaleTimeString();
}catch(e){document.getElementById('mode').textContent='OFFLINE';document.getElementById('level').textContent='Waiting for local TOKEN ZOMBIE service';document.getElementById('dot').classList.remove('live')}}
refresh();setInterval(refresh,5000);
</script></body></html>"""
PAGE = PAGE.replace("<div class=\"zombie\" id=\"mascot\" aria-hidden=\"true\">🧟</div>", "<div class=\"zombie\" id=\"mascot\" aria-hidden=\"true\">" + svg("SLEEP") + "</div>")

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
                status = tzbus.read_bus()
                # Derive dashboard totals from the local savings ledger; keep measured and estimated separate.
                ledger_path = os.path.expanduser('~/.claude/token-zombie/ledger.json')
                try:
                    entries = json.load(open(ledger_path, encoding='utf-8'))
                    if not isinstance(entries, list):
                        entries = []
                except Exception:
                    entries = []
                measured = [e for e in entries if isinstance(e, dict) and e.get('basis') == 'measured'
                            and isinstance(e.get('tok'), (int, float)) and e.get('tok', 0) > 0
                            and not str(e.get('kind', '')).startswith('overhead')]
                estimated = [e for e in entries if isinstance(e, dict) and e.get('basis') == 'est'
                             and isinstance(e.get('tok'), (int, float)) and e.get('tok', 0) > 0
                             and not str(e.get('kind', '')).startswith('overhead')]
                status['tokens_saved_measured'] = sum(e['tok'] for e in measured)
                status['tokens_saved_estimated'] = sum(e['tok'] for e in estimated)
                status['optimizations'] = len(measured) + len(estimated)
                body = json.dumps(status).encode()
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
    socketserver.TCPServer.allow_reuse_address = True
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
