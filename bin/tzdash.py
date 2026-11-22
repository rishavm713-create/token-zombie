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


def window(led, now):
    """Entries in the rolling last 24 h, all chats (owner 2026-11-22). Exact and measurable (the 5h plan reset is not visible to the desktop app)."""
    start = now - 86400
    return [x for x in led if isinstance(x.get('t'), (int, float)) and x['t'] >= start]


def metrics(bus, now=None):
    """The four headline numbers. Each: (value, tag, note). tag = MEASURED | EST | UNKNOWN; never a made-up number."""
    import time
    from tzlib import skills_off
    now = now or time.time()
    ag = _j('agents.json', {})
    fresh = isinstance(ag.get('ts'), (int, float)) and now - ag['ts'] <= 180 and isinstance(ag.get('running'), int)
    agents = (ag['running'], 'MEASURED', 'subagents running (Mods agent.list)') if fresh else ('—', 'UNKNOWN', 'needs the in-chat panel loaded')
    sk = os.path.expanduser('~/.claude/skills')
    on = sum(os.path.isfile(os.path.join(sk, d, 'SKILL.md')) for d in os.listdir(sk)) if os.path.isdir(sk) else 0
    off_n, off_tok = skills_off()
    skills = (on, 'MEASURED', f'enabled on disk; {off_n} kept off (~{off_tok} tok/chat startup) [EST]')
    led = window([x for x in _j('ledger.json', []) if isinstance(x, dict) and isinstance(x.get('tok'), (int, float))], now)
    done = [x for x in led if x.get('basis') == 'measured' and not str(x.get('kind', '')).startswith('overhead')]
    over = sum(x['tok'] for x in led if str(x.get('kind', '')).startswith('overhead'))
    net = sum(x['tok'] for x in done) - over
    fj = _j('fresh.json', {})
    import time as _t
    fr = fj.get('tok', 0) if isinstance(fj.get('ts'), (int, float)) and fj['ts'] >= now - 86400 and isinstance(fj.get('tok'), int) else 0
    net += fr  # fresh-chat counterfactual (EST), shown inside TOKENS SAVED per owner; split kept in tz stats
    saved = (f'{net:,}' if led or fr else '0', 'EST', 'output cut by tz (MEASURED chars / 4), net of hook overhead; no A/B baseline, not a proven saving')
    opts = (len(done), 'MEASURED', 'filters/optimizations actually applied (ledger)')
    recent = any(isinstance(x.get('t'), (int, float)) and now - x['t'] <= 120 and x['tok'] > 0 for x in done)
    return {'agents': agents, 'skills': skills, 'saved': saved, 'opts': opts}, recent


def render():
    import tzbus
    from tzzombie import svg_zombie, visual_state, CSS as ZCSS
    s = tzbus.read_bus()
    st = mascot_state(s)
    m, recent = metrics(s)
    vs = os.environ.get('TZ_MASCOT_STATE') or visual_state(s, st, m['agents'][0] if isinstance(m['agents'][0], int) else 0, recent)
    led = _j('ledger.json', [])[-20:]
    reg = {k: r for k, r in _j('registry.json', {}).items() if isinstance(r, dict)}
    e = html.escape
    rows = ''.join(f'<tr><td>{e(str(k))}</td><td>{e(str(v))}</td></tr>' for k, v in s.items() if k not in ('limits', 'tokens', 'label'))
    try:
        import tzondemand, time as _t
        caps = ''.join(f"<tr><td>{_t.strftime('%H:%M', _t.localtime(x['t']))}</td><td>{e(x['act'])}</td><td>{e(x['cap'])}</td><td>{'ok' if x['ok'] else 'FAIL'}</td><td>{e(x.get('note', ''))}</td></tr>"
                       for x in tzondemand.events(_t.time() - 86400)[-20:]) or '<tr><td>no events</td></tr>'
    except Exception:
        caps = '<tr><td>UNKNOWN</td></tr>'
    b = bench_results()
    brow = ''.join(f'<tr><td>{e(f)}</td><td>{t}</td><td>{e(str(x))}</td></tr>' for f, t, x in b) or '<tr><td colspan=3>no A/B evidence: UNKNOWN (not run)</td></tr>'
    rrow = ''.join(f"<tr><td>{e(k)}</td><td>{e(r.get('grade',''))}</td><td>{e(r.get('license',''))}</td></tr>" for k, r in reg.items()) or '<tr><td colspan=3>empty</td></tr>'
    mode = _j('config.json', {}).get('mode') or 'full'
    ctx = s.get('ctx_pct')
    ctxs = f'{ctx}%' if isinstance(ctx, (int, float)) else '—'
    state = 'Alert' if vs == 'alert' else 'Off' if mode == 'off' else 'Idle' if vs == 'sleep' else 'Active'
    def bnum(key, label, cls=''):
        v = m[key][0]
        if key == 'saved' and isinstance(v, str) and v.replace(',', '').lstrip('-').isdigit():
            n = int(v.replace(',', ''))
            v = f'{n / 1e6:.1f}M' if abs(n) >= 1e6 else f'{round(n / 1e3)}K' if abs(n) >= 1e4 else f'{n / 1e3:.1f}K' if abs(n) >= 1e3 else str(n)
        return f'<span class="bm{cls}"><b class=bn>{e(str(v))}</b><span class=bl>{label}</span></span>'
    tile = lambda key, label: (f'<div class="tile"><div class="lab">{label}</div><div class="val">{e(str(m[key][0]))}</div>'
                               f'<div class="tag t-{m[key][1].lower()}">{m[key][1]}</div><div class="note">{e(m[key][2])}</div></div>')
    return f"""<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><meta http-equiv=refresh content=15><title>TOKEN ZOMBIE</title>
<style>
:root{{--bg:#07090c;--card:#0f1418;--card2:#131a20;--line:#1f2a31;--txt:#dce6dd;--dim:#7c8b84;--acc:#9dff3a;--amber:#ffb020;--zh:clamp(210px,34vw,300px)}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(1200px 600px at 70% -10%,#16301a 0,#07090c 55%) fixed;color:var(--txt);font:14px/1.45 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}}
.wrap{{max-width:980px;margin:0 auto;padding:60px 16px 40px}}
.tzx{{margin:0;padding:0;background:none;border:0}}.tzx>summary{{list-style:none}}.tzx>summary::-webkit-details-marker{{display:none}}
.tzbar{{position:relative;display:flex;align-items:center;gap:18px;min-height:58px;padding:9px 14px 9px 92px;background:linear-gradient(180deg,#15191d,#101316);border:1px solid #262d32;border-radius:14px;box-shadow:0 14px 30px -18px #000,inset 0 1px 0 #ffffff0a;cursor:pointer;color:var(--txt)}}
.tzbar:focus-visible{{outline:2px solid var(--acc);outline-offset:2px}}
.bz{{position:absolute;left:12px;top:-45px;width:68px;height:84px;pointer-events:none;filter:drop-shadow(0 6px 6px #0008)}}
.bt{{display:flex;align-items:center;gap:8px;flex:none;white-space:nowrap}}.bt h1{{font-size:14px;letter-spacing:.08em;font-weight:700;margin:0}}
.pill{{font-size:10.5px;font-weight:700;letter-spacing:.08em;color:var(--acc);background:#9dff3a1a;border:1px solid #9dff3a33;border-radius:999px;padding:1px 8px}}.bh{{display:flex;flex-direction:column;gap:2px}}.bt h1{{color:#fff;font-weight:800;letter-spacing:.12em}}.btag{{color:#fff;font-size:9.5px;font-weight:700;letter-spacing:.18em}}.pill[data-m=lite]{{color:#5ad1ff;background:#5ad1ff1a;border-color:#5ad1ff40}}.pill[data-m=ultra]{{color:#ff8a1f;background:#ff8a1f1a;border-color:#ff8a1f40}}.pill.off{{color:var(--dim);background:#ffffff0d;border-color:#ffffff1a}}
.bms{{display:flex;flex:1;min-width:0;justify-content:space-around;gap:12px}}
.bm{{display:flex;flex-direction:column;min-width:0}}.bn{{font-size:19px;font-weight:700;line-height:1.15;font-variant-numeric:tabular-nums;color:#f2fff0}}.bm.g .bn{{color:var(--acc)}}
.bl{{font-size:9.5px;letter-spacing:.11em;color:var(--dim);font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.bl i{{font-style:normal;color:var(--amber);margin-left:4px}}
.bs{{display:flex;align-items:center;gap:6px;flex:none;font-size:12px;color:var(--dim)}}.dot{{width:7px;height:7px;border-radius:50%;background:var(--acc);box-shadow:0 0 6px var(--acc)}}.dot.alert{{background:var(--amber);box-shadow:0 0 6px var(--amber)}}.dot.off,.dot.idle{{background:#5c6a64;box-shadow:none}}
.chev{{width:9px;height:9px;border-right:2px solid var(--dim);border-bottom:2px solid var(--dim);transform:rotate(45deg) translateY(-3px);margin:0 4px 0 8px;transition:transform .2s}}.tzx[open] .chev{{transform:rotate(-135deg) translateX(-3px)}}
.full{{margin-top:12px}}
.card{{position:relative;background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid var(--line);border-radius:16px;box-shadow:0 30px 60px -30px #000,inset 0 1px 0 #ffffff0d}}
.card:before{{content:"";position:absolute;inset:0 0 auto 0;height:2px;border-radius:16px 16px 0 0;background:linear-gradient(90deg,transparent,#9dff3a55,transparent)}}
.head{{padding:16px 20px 0}}
h1{{margin:0;font-size:20px;letter-spacing:.14em;font-weight:800}}h1 b{{color:var(--acc)}}.brand{{margin:0 0 12px}}.brand h1{{color:#fff;font-size:22px}}.tagline{{margin:2px 0 0;color:#fff;font-size:11px;font-weight:700;letter-spacing:.16em}}
.chips{{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}}.chip{{border:1px solid var(--line);background:#0b1014;border-radius:999px;padding:2px 10px;font-size:12px;color:var(--dim)}}.chip b{{color:var(--txt);font-weight:600}}
.st-alert b{{color:var(--amber)}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:14px 16px 18px}}
.tile{{background:#0a0f12;border:1px solid var(--line);border-radius:12px;padding:12px 14px;min-width:0}}
.lab{{font-size:11px;letter-spacing:.12em;color:var(--dim);font-weight:700}}.val{{font-size:30px;font-weight:800;margin:4px 0 2px;color:#f2fff0;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}}
.tag{{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.08em;border-radius:4px;padding:0 5px}}.t-measured{{background:#9dff3a22;color:var(--acc)}}.t-est{{background:#ffb02022;color:var(--amber)}}.t-unknown{{background:#ffffff14;color:var(--dim)}}
.note{{font-size:11.5px;color:var(--dim);margin-top:6px}}
details{{margin:12px 0 0;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:8px 14px}}summary{{cursor:pointer;color:var(--dim);font-weight:600}}
table{{border-collapse:collapse;width:100%;margin:8px 0}}td{{padding:3px 10px 3px 0;border-bottom:1px solid var(--line);font-size:12.5px;overflow-wrap:anywhere}}pre{{white-space:pre-wrap;font-size:12px;color:var(--dim)}}
@media (max-width:760px){{.grid{{grid-template-columns:repeat(2,1fr)}}}}
@media (max-width:820px){{.tzbar{{flex-wrap:wrap;row-gap:8px;padding:9px 12px 9px 86px}}.bt{{flex:1}}.bms{{order:3;flex:1 0 100%;margin-left:-74px;margin-top:4px;justify-content:space-between}}.bn{{font-size:16px}}.bl{{font-size:8.5px;letter-spacing:.06em}}.val{{font-size:24px}}}}
{ZCSS}
</style>
<div class=wrap>
<details class=tzx><summary class=tzbar aria-label="TOKEN ZOMBIE bar: open details"><span class=bz>{svg_zombie(vs)}</span>
<span class=bt><span class=bh><h1>TOKEN <b>ZOMBIE</b></h1><span class=btag>MAKE EVERY SINGLE TOKEN COUNT.</span></span><span data-m={e(str(mode))} class="pill{' off' if mode == 'off' else ''}">{e(str(mode)).upper()}</span></span>
<span class=bms>{bnum('agents', 'AGENTS')}{bnum('skills', 'SKILLS USED')}{bnum('saved', 'TOKENS SAVED', ' g')}{bnum('opts', 'OPTIMIZATIONS')}</span>
<span class=bs><span class="dot {e(state.lower())}"></span>{state}<span class=chev></span></span></summary>
<div class=full><div class=card>
<div class=head>
<div class=brand><h1>TOKEN <b>ZOMBIE</b></h1><p class=tagline>MAKE EVERY SINGLE TOKEN COUNT.</p></div>
<div class=chips style="margin-top:0"><span class="chip st-{e(vs)}">mascot <b>{e(vs.upper())}</b></span><span class=chip>mode <b>{e(str(mode)).upper()}</b></span><span class=chip>context <b>{e(ctxs)}</b></span><span class=chip>level <b>{e(str(s.get('level', '—')))}</b></span><span class=chip>supervisor <b>{e(str(s.get('state', '—')))}</b></span></div></div>
<div class=grid>{tile('agents', 'AGENTS RUNNING')}{tile('skills', 'SKILLS ENABLED')}{tile('saved', 'TOKENS SAVED')}{tile('opts', 'OPTIMIZATIONS EXECUTED')}</div>
</div>
<details><summary>On-demand capabilities, last 24h (MEASURED events)</summary><table>{caps}</table></details>
<details><summary>Status bus (ctx% actual/est, minutes est)</summary><table>{rows or '<tr><td>no status: run tz sup tick</td></tr>'}</table></details>
<details><summary>Ledger (last 20)</summary><pre>{e(json.dumps(led, indent=1)[:2000])}</pre></details>
<details><summary>A/B benchmark evidence (MEASURED only if present)</summary><table>{brow}</table></details>
<details><summary>Registry</summary><table>{rrow}</table></details>
</div></details>
</div></html>"""


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
