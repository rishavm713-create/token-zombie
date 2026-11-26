'use strict';
(function () {
  const D = window.STUDIO;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const SVG = 'http://www.w3.org/2000/svg';

  // DOM builder. All text goes through textContent / text nodes, never innerHTML.
  function make(el, props, kids) {
    for (const [k, v] of Object.entries(props || {})) {
      if (v === undefined || v === null || v === false) continue;
      if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else if (k === 'text') el.textContent = v;
      else el.setAttribute(k, v === true ? '' : v);
    }
    el.append(...kids.flat(3).filter(x => x !== null && x !== undefined && x !== false));
    return el;
  }
  const h = (tag, props, ...kids) => make(document.createElement(tag), props, kids);
  const s = (tag, props, ...kids) => make(document.createElementNS(SVG, tag), props, kids);
  const fill = (el, ...kids) => { el.replaceChildren(...kids.flat(3).filter(Boolean)); return el; };
  const CAP = Object.fromEntries(D.CAPABILITIES.map(c => [c.id, c]));
  const chip = status => h('span', { class: 'chip ' + status, text: D.STATUS[status].label });
  const capLine = id => h('div', { class: 'capline' }, h('span', { text: CAP[id].name }), chip(CAP[id].status));
  const list = items => h('ul', null, items.map(t => h('li', { text: t })));
  const table = (head, rows) => h('div', { class: 'tablewrap' }, h('table', { class: 'stack' },
    h('thead', null, h('tr', null, head.map(t => h('th', { scope: 'col', text: t })))),
    h('tbody', null, rows.map(r => h('tr', null, r.map((c, i) => h('td', { 'data-label': head[i] }, c)))))));

  /* ---------- motion, header, scroll ---------- */
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  let motion = !reduced.matches;
  const motionListeners = [];
  function setMotion(on) {
    motion = on;
    document.documentElement.classList.toggle('still', !on);
    const b = $('#motion');
    b.textContent = on ? 'Pause motion' : 'Play motion';
    b.setAttribute('aria-pressed', String(!on));
    motionListeners.forEach(f => f(on));
  }
  $('#motion').addEventListener('click', () => setMotion(!motion));
  reduced.addEventListener('change', e => setMotion(!e.matches));

  const menu = $('#menu'), nav = $('#nav');
  const closeMenu = () => { nav.classList.remove('open'); menu.setAttribute('aria-expanded', 'false'); };
  menu.addEventListener('click', () => menu.setAttribute('aria-expanded', String(nav.classList.toggle('open'))));
  nav.addEventListener('click', e => { if (e.target.closest('a')) closeMenu(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && nav.classList.contains('open')) { closeMenu(); menu.focus(); } });
  const bar = $('#scrollbar');
  function onScroll() {
    const max = document.documentElement.scrollHeight - innerHeight;
    bar.value = max > 0 ? Math.round(scrollY / max * 1000) : 0;
    let current = '';
    $$('main section[id]').forEach(x => { if (x.getBoundingClientRect().top < innerHeight * .35) current = x.id; });
    $$('#nav a').forEach(a => { if (a.hash === '#' + current) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current'); });
  }
  addEventListener('scroll', onScroll, { passive: true });
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } }), { threshold: .1 });
    $$('main section').forEach(x => io.observe(x));
  }
  const smooth = el => el.scrollIntoView({ behavior: motion ? 'smooth' : 'auto', block: 'start' });

  async function copy(text, field, status) {
    try { await navigator.clipboard.writeText(text); status.textContent = 'Copied.'; }
    catch (e) { field.focus(); field.select(); status.textContent = 'Copy was blocked. The text is selected: copy it manually.'; }
  }

  /* ---------- reusable tabs (ARIA, arrow keys) ---------- */
  let uid = 0;
  function tabs(label, names, onSelect, extra = '') {
    const id = 'tabs' + (++uid);
    const panel = h('div', { role: 'tabpanel', id: id + 'p', tabindex: '0', class: 'panel' });
    let cur = -1;
    const btns = names.map((n, i) => h('button', { type: 'button', role: 'tab', id: id + 't' + i, 'aria-controls': id + 'p', text: n, onclick: () => select(i) }));
    const bar = h('div', { role: 'tablist', 'aria-label': label, class: 'tabs ' + extra }, btns);
    bar.addEventListener('keydown', e => {
      const n = names.length;
      const to = { ArrowRight: (cur + 1) % n, ArrowDown: (cur + 1) % n, ArrowLeft: (cur + n - 1) % n, ArrowUp: (cur + n - 1) % n, Home: 0, End: n - 1 }[e.key];
      if (to === undefined) return;
      e.preventDefault(); select(to); btns[to].focus();
    });
    function select(i) {
      cur = i;
      btns.forEach((b, k) => { b.setAttribute('aria-selected', String(k === i)); b.tabIndex = k === i ? 0 : -1; });
      panel.setAttribute('aria-labelledby', id + 't' + i);
      fill(panel, h('div', { class: 'fade' }, onSelect(i)));
    }
    return { bar, panel, select, get index() { return cur; } };
  }

  /* ---------- hero ---------- */
  const counts = {};
  D.CAPABILITIES.forEach(c => { counts[c.status] = (counts[c.status] || 0) + 1; });
  const nums = ['working', 'partial', 'planned'].map(k => {
    const b = h('b', { text: String(counts[k] || 0) });
    $('#hero-counts').append(h('li', null, h('a', { href: '#roadmap' }, b, D.STATUS[k].label + ' today')));
    return [b, counts[k] || 0];
  });
  if (motion) {
    let n = 0;
    const t = setInterval(() => { n++; nums.forEach(([b, v]) => { b.textContent = String(Math.round(v * Math.min(1, n / 20))); }); if (n >= 20) clearInterval(t); }, 40);
  }

  (function hero() {
    const stages = D.WORKFLOWS.new.stages;
    const items = stages.map(x => h('li', { text: x.name }));
    $('#hero-flow').append(...items);
    let at = 0; const log = [];
    function draw() {
      items.forEach((li, i) => li.className = i < at ? 'done' : i === at ? 'now' : '');
      $('#hero-progress').value = Math.round((at + 1) / stages.length * 100);
      $('#hero-budget').value = Math.min(92, 6 + at * 8);
      $('#hero-log').textContent = log.join('\n');
    }
    function step() {
      at = (at + 1) % stages.length;
      if (!at) log.length = 0;
      log.push('[sim] ' + stages[at].name.toLowerCase() + ' → ' + stages[at].output.toLowerCase());
      if (stages[at].gate !== 'None') log.push('[sim] gate: ' + stages[at].gate.toLowerCase());
      log.splice(0, Math.max(0, log.length - 6));
      draw();
    }
    log.push('[sim] idea → product brief'); draw();
    setInterval(() => { if (motion && !document.hidden) step(); }, 1500);
  })();

  (function network() {
    const c = $('#net'), x = c.getContext && c.getContext('2d');
    if (!x) return;
    let w = 0, ht = 0, pts = [], visible = true, raf = 0;
    function size() {
      const r = c.getBoundingClientRect(), d = Math.min(2, devicePixelRatio || 1);
      w = r.width; ht = r.height; c.width = w * d; c.height = ht * d; x.setTransform(d, 0, 0, d, 0, 0);
      pts = Array.from({ length: Math.min(60, Math.round(w / 22)) }, () => ({ x: Math.random() * w, y: Math.random() * ht, vx: (Math.random() - .5) * .35, vy: (Math.random() - .5) * .35 }));
      draw(false);
    }
    function draw(move) {
      x.clearRect(0, 0, w, ht);
      for (const p of pts) {
        if (move) { p.x += p.vx; p.y += p.vy; if (p.x < 0 || p.x > w) p.vx *= -1; if (p.y < 0 || p.y > ht) p.vy *= -1; }
        x.fillStyle = '#b6f36a'; x.fillRect(p.x - 1, p.y - 1, 2, 2);
      }
      for (let i = 0; i < pts.length; i++) for (let j = i + 1; j < pts.length; j++) {
        const dx = pts[i].x - pts[j].x, dy = pts[i].y - pts[j].y, q = Math.hypot(dx, dy);
        if (q < 120) { x.strokeStyle = 'rgba(182,243,106,' + (1 - q / 120) * .25 + ')'; x.beginPath(); x.moveTo(pts[i].x, pts[i].y); x.lineTo(pts[j].x, pts[j].y); x.stroke(); }
      }
    }
    function loop() { raf = 0; if (!motion || !visible) return; draw(true); raf = requestAnimationFrame(loop); }
    const start = () => { if (!raf) raf = requestAnimationFrame(loop); };
    addEventListener('resize', size);
    if ('IntersectionObserver' in window) new IntersectionObserver(es => { visible = es[0].isIntersecting; start(); }).observe(c);
    motionListeners.push(start);
    size(); start();
  })();

  $$('[data-status]').forEach(el => el.replaceWith(chip(CAP[el.dataset.status].status)));

  /* ---------- 2 and 3: lifecycle and workflows ---------- */
  const lifecycle = (function () {
    const root = $('#lifecycle-app'), keys = ['new', 'existing'];
    let wf = 'new', stageTabs, timer = 0;
    const play = h('button', { type: 'button', text: 'Play journey', onclick: () => timer ? stop() : start() });
    const stop = () => { clearInterval(timer); timer = 0; play.textContent = 'Play journey'; };
    function start() {
      play.textContent = 'Pause';
      const n = D.WORKFLOWS[wf].stages.length;
      if (stageTabs.index === n - 1) stageTabs.select(0);
      timer = setInterval(() => { if (stageTabs.index >= n - 1) stop(); else stageTabs.select(stageTabs.index + 1); }, 2200);
    }
    const move = d => { stop(); const n = D.WORKFLOWS[wf].stages.length; stageTabs.select((stageTabs.index + d + n) % n); };
    const host = h('div');
    function build(i) {
      const stages = D.WORKFLOWS[wf].stages;
      const prog = h('progress', { max: stages.length, value: 1, 'aria-label': 'Position in lifecycle' });
      stageTabs = tabs(D.WORKFLOWS[wf].title + ' stages', stages.map((x, k) => (k + 1) + '. ' + x.name), k => {
        const x = stages[k]; prog.value = k + 1;
        return [h('h3', { text: x.name }), h('p', { text: x.what }),
          h('div', { class: 'two' },
            h('div', null, h('h4', { text: 'You get' }), h('p', { text: x.output }), h('h4', { text: 'Gate' }), h('p', { text: x.gate })),
            h('div', null, h('h4', { text: 'Capabilities and status today' }), x.caps.map(capLine)))];
      }, 'stagebar');
      fill(host, h('p', { class: 'muted', text: D.WORKFLOWS[wf].lead }), prog, stageTabs.bar, stageTabs.panel);
      stageTabs.select(i || 0);
    }
    const paths = keys.map(k => h('button', { type: 'button', 'aria-pressed': String(k === wf), text: D.WORKFLOWS[k].title, onclick: () => show(k, 0) }));
    function show(k, i) { stop(); wf = k; paths.forEach((b, j) => b.setAttribute('aria-pressed', String(keys[j] === k))); build(i); }
    fill(root, h('div', { class: 'bar', role: 'group', 'aria-label': 'Path' }, paths), host,
      h('div', { class: 'bar' }, h('button', { type: 'button', text: '‹ Previous stage', onclick: () => move(-1) }), play, h('button', { type: 'button', text: 'Next stage ›', onclick: () => move(1) })));
    build(0);
    return { show };
  })();
  fill($('#workflows-app'), ['new', 'existing'].map(k => h('div', { class: 'panel' },
    h('h3', { text: D.WORKFLOWS[k].title }), h('p', { class: 'muted', text: D.WORKFLOWS[k].lead }),
    h('ol', { class: 'steps' }, D.WORKFLOWS[k].stages.map((x, i) => h('li', null, h('button', { type: 'button', text: x.name, onclick: () => {
      lifecycle.show(k, i); smooth($('#lifecycle'));
      const t = $('#lifecycle-app [role=tab][aria-selected=true]'); if (t) t.focus({ preventScroll: true });
    } })))),
    h('p', null, h('a', { class: 'btn', href: k === 'new' ? '#demo' : '#improve', text: k === 'new' ? 'Simulate this path' : 'Simulate an import' })))));

  /* ---------- 4 capability explorer, 14 matrix ---------- */
  fill($('#legend'), Object.keys(D.STATUS).map(k => h('div', null, h('dt', null, chip(k)), h('dd', { text: D.STATUS[k].meaning }))));
  function filtered(root, render) {
    const domain = h('select', null, h('option', { value: '', text: 'All areas' }), D.DOMAINS.map(d => h('option', { value: d, text: d })));
    const status = h('select', null, h('option', { value: '', text: 'All statuses' }), ['working', 'partial', 'planned'].map(k => h('option', { value: k, text: D.STATUS[k].label })));
    const q = h('input', { type: 'search', placeholder: 'e.g. security', maxlength: '60' });
    const info = h('p', { class: 'muted', role: 'status' }), host = h('div');
    const reset = h('button', { type: 'button', text: 'Reset filters', onclick: () => { domain.value = ''; status.value = ''; q.value = ''; draw(); } });
    function draw() {
      const t = q.value.trim().toLowerCase();
      const hits = D.CAPABILITIES.filter(c => (!domain.value || c.domain === domain.value) && (!status.value || c.status === status.value) && (!t || [c.name, c.goal, c.today, c.gap].join(' ').toLowerCase().includes(t)));
      info.textContent = 'Showing ' + hits.length + ' of ' + D.CAPABILITIES.length + ' capabilities.';
      fill(host, hits.length ? render(hits) : h('p', { class: 'note', text: 'Nothing matches. Reset the filters.' }));
    }
    [domain, status, q].forEach(e => e.addEventListener('input', draw));
    fill(root, h('div', { class: 'bar' }, h('label', null, 'Area ', domain), h('label', null, 'Status ', status), h('label', null, 'Search ', q), reset), info, host);
    draw();
  }
  filtered($('#capabilities-app'), hits => h('div', { class: 'cards' }, hits.map(c => h('details', { class: 'fade' },
    h('summary', null, c.name, ' ', chip(c.status)),
    h('h4', { text: 'Designed to' }), h('p', { text: c.goal }), h('h4', { text: 'Today' }), h('p', { text: c.today }),
    h('h4', { text: 'Still missing' }), h('p', { text: c.gap })))));
  filtered($('#matrix-app'), hits => table(['Capability', 'Area', 'Status', 'What exists today'], hits.map(c => [c.name, c.domain, chip(c.status), c.today])));
  fill($('#roadmap-app'), D.ROADMAP.map(m => h('li', null, h('h3', { text: m.name }), h('p', { text: m.what }), m.caps.map(capLine))));
  $('#asof').textContent = 'Status as of ' + D.AS_OF + '. Order matters; no dates are promised.';

  /* ---------- 5 repository intelligence (fictional) ---------- */
  (function () {
    const NEEDS = {
      'Video captions': [['example/caption-kit', 'MIT', 88, 'active'], ['example/subtitle-forge', 'GPL-3.0', 91, 'active'], ['example/old-captions', 'MIT', 54, 'stale'], ['example/word-timing', 'none', 80, 'active']],
      'User sign-in': [['example/tiny-auth', 'Apache-2.0', 84, 'active'], ['example/gatekeeper', 'AGPL-3.0', 86, 'active'], ['example/legacy-login', 'BSD-3-Clause', 47, 'stale'], ['example/session-demo', 'MIT', 62, 'active']],
      'Game dialogue': [['example/branch-talk', 'MIT', 79, 'active'], ['example/story-graph', 'GPL-3.0', 83, 'active'], ['example/lines-db', 'none', 70, 'active'], ['example/quest-script', 'Apache-2.0', 66, 'active']]
    };
    function verdict([, lic, fit, state]) {
      if (lic === 'none') return ['D · Not suitable', 'No licence means no permission to reuse.', 'bad'];
      if (state === 'stale') return ['D · Not suitable', 'No recent maintenance; adopting it would add risk.', 'bad'];
      if (/GPL/.test(lic)) return ['C · Study and implement independently', 'Copyleft code is not copied into a proprietary product. Learn the approach, or call it as a separate tool after legal review.', 'warn'];
      if (fit < 70) return ['B · Optional external tool', 'Licence allows use but the fit is weak. Keep it replaceable.', 'warn'];
      return ['A · Reuse with required notices', 'Compatible licence and good fit. Record the licence and notice, and read the source first.', 'good'];
    }
    const need = h('select', null, Object.keys(NEEDS).map(k => h('option', { text: k })));
    const only = h('input', { type: 'checkbox' });
    const host = h('div'), out = h('div', { role: 'status' });
    function draw() {
      fill(out);
      const rows = NEEDS[need.value].filter(r => !only.checked || /MIT|Apache|BSD/.test(r[1])).sort((a, b) => b[2] - a[2]);
      fill(host, table(['Candidate (fictional)', 'Licence', 'Fit score', 'Maintenance', 'Decision'], rows.map(r => [r[0], r[1],
        h('span', null, h('meter', { min: 0, max: 100, low: 60, high: 80, optimum: 100, value: r[2], 'aria-label': 'Fit ' + r[2] + ' of 100' }), ' ' + r[2]), r[3],
        h('button', { type: 'button', text: 'Evaluate', 'aria-label': 'Evaluate ' + r[0], onclick: () => { const v = verdict(r); fill(out, h('p', { class: 'note fade ' + v[2] }, h('b', { text: r[0] + ': ' + v[0] + '. ' }), v[1])); } })])));
    }
    need.addEventListener('change', draw); only.addEventListener('change', draw);
    fill($('#intelligence-app'), h('div', { class: 'bar' }, h('label', null, 'Need ', need), h('label', { class: 'inline' }, only, 'Only permissive licences')), host, out);
    draw();
  })();

  /* ---------- 6 planning ---------- */
  (function () {
    const NODES = [['Desktop UI', 20, 20, 'Timeline, preview and caption editor. Talks only to the local service.'], ['Local service', 230, 20, 'Validates every request and owns the job queue.'], ['Media worker', 440, 20, 'Silence detection and rendering in a separate process.'], ['Project database', 230, 150, 'SQLite file per project: clips, words, edits.'], ['Speech model', 440, 150, 'Word-level transcription. Local or API: an owner decision with cost attached.']];
    const EDGES = [[0, 1], [1, 2], [1, 3], [2, 4]];
    function architecture() {
      const info = h('p', { class: 'note', role: 'status', text: 'Select a component to see its role.' });
      const nodes = [];
      const edges = EDGES.map(([a, b]) => s('path', { class: 'edge', d: 'M' + (NODES[a][1] + 80) + ' ' + (NODES[a][2] + 30) + ' L' + (NODES[b][1] + 80) + ' ' + (NODES[b][2] + 30) }));
      const pick = i => { nodes.forEach((n, k) => { n.classList.toggle('on', k === i); n.setAttribute('aria-pressed', String(k === i)); }); edges.forEach((e, k) => e.classList.toggle('on', EDGES[k].includes(i))); info.textContent = NODES[i][0] + ': ' + NODES[i][3]; };
      NODES.forEach(([name, x, y], i) => nodes.push(s('g', { class: 'node', role: 'button', tabindex: '0', 'aria-pressed': 'false', 'aria-label': name, onclick: () => pick(i), onkeydown: e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(i); } } },
        s('rect', { x, y, width: 160, height: 60, rx: 10 }), s('text', { x: x + 80, y: y + 35, 'text-anchor': 'middle', text: name }))));
      return [s('svg', { viewBox: '0 0 620 230', role: 'group', 'aria-label': 'Sample architecture diagram' }, edges, nodes), info];
    }
    const VIEWS = {
      PRD: () => [h('h3', { text: 'ClipPilot (fictional): product requirements' }), h('h4', { text: 'Problem' }), h('p', { text: 'Solo creators spend hours removing silences and adding captions.' }), h('h4', { text: 'Must have' }), list(['Import a video and transcribe it with word times', 'Remove silences without cutting inside a word', 'Editable captions', 'Undo every automatic edit']), h('h4', { text: 'Out of scope for version 1' }), list(['Multi-user editing', 'Mobile app']), h('h4', { text: 'Acceptance' }), list(['No cut edge falls inside a word', 'Source file is never modified'])],
      Architecture: architecture,
      Database: () => [table(['Table', 'Columns', 'Rule'], [['projects', 'id, name, created_at', 'One folder per project'], ['clips', 'id, project_id, path, duration', 'Source path is read-only'], ['words', 'id, clip_id, text, start_ms, end_ms', 'start_ms < end_ms'], ['edits', 'id, clip_id, kind, from_ms, to_ms, undone', 'Non-destructive, reversible']])],
      'Design system': () => [h('p', { text: 'Sample tokens with contrast measured against the dark background.' }), h('div', { class: 'swatches' }, [['Background', '#0b0d0c', 'base'], ['Text', '#e8efe9', 'high contrast'], ['Accent', '#b6f36a', 'actions'], ['Warning', '#f4c15d', 'attention'], ['Danger', '#ff8b7a', 'errors']].map(([n, c, u]) => h('figure', null, s('svg', { viewBox: '0 0 100 50', 'aria-hidden': 'true' }, s('rect', { width: 100, height: 50, rx: 8, fill: c, stroke: '#4a6254' })), h('figcaption', null, h('b', { text: n }), h('br'), h('code', { text: c }), h('br'), u)))), h('p', null, h('button', { type: 'button', class: 'primary', text: 'Primary button' }), ' ', h('span', { class: 'muted', text: 'Component sample (does nothing).' }))]
    };
    const names = Object.keys(VIEWS), t = tabs('Planning documents', names, i => VIEWS[names[i]]());
    fill($('#planning-app'), t.bar, t.panel); t.select(0);
  })();

  /* ---------- 7 sessions ---------- */
  (function () {
    // [task, units, parallel lane, depends on]
    const TASKS = [['Data model', 3, 0, []], ['API', 4, 0, [0]], ['Timeline UI', 5, 1, [0]], ['Captions', 4, 2, [0]], ['Tests', 3, 1, [1, 2]], ['Docs', 2, 2, [3]]];
    let parallel = false, timer = 0, done = [], ticks = 0;
    const host = h('div', { class: 'panel' }), status = h('p', { class: 'note', role: 'status' });
    const run = h('button', { type: 'button', class: 'primary', text: 'Run simulation', onclick: () => timer ? pause() : start() });
    const merge = h('button', { type: 'button', text: 'Approve merge', onclick: () => { merge.disabled = true; status.textContent = 'Simulated merge approved. Nothing was merged anywhere.'; run.focus(); } });
    const modes = [false, true].map(p => h('button', { type: 'button', 'aria-pressed': String(p === parallel), text: p ? 'Blueprint: parallel (Planned)' : 'Today: one at a time (Partial)', onclick: () => { parallel = p; modes.forEach((b, i) => b.setAttribute('aria-pressed', String(!!i === p))); reset(); } }));
    let bars = [];
    function pause() { clearInterval(timer); timer = 0; run.textContent = 'Resume'; }
    function reset() {
      clearInterval(timer); timer = 0; ticks = 0; done = TASKS.map(() => 0); run.textContent = 'Run simulation'; merge.disabled = true;
      status.textContent = 'Ready. ' + (parallel ? 'Three sessions, each owning its own files.' : 'One session runs tasks in dependency order.');
      bars = [];
      const lanes = parallel ? [0, 1, 2] : [null];
      fill(host, lanes.map(l => h('div', { class: 'lane' }, h('b', { text: l === null ? 'Session 1' : 'Session ' + (l + 1) }),
        h('div', null, TASKS.map((t, i) => {
          if (l !== null && t[2] !== l) return null;
          const p = h('progress', { max: t[1], value: 0, 'aria-label': t[0] + ' progress' }), st = h('span', { class: 'res', text: 'waiting' });
          bars[i] = [p, st];
          return h('div', { class: 'task' }, h('span', { text: t[0] }), p, st);
        })))));
    }
    function tick() {
      const ready = TASKS.map((t, i) => i).filter(i => done[i] < TASKS[i][1] && TASKS[i][3].every(d => done[d] >= TASKS[d][1]));
      let active = [];
      if (parallel) { const used = new Set(); for (const i of ready) if (!used.has(TASKS[i][2])) { used.add(TASKS[i][2]); active.push(i); } } else active = ready.slice(0, 1);
      ticks++;
      active.forEach(i => { done[i]++; });
      TASKS.forEach((t, i) => { const [p, st] = bars[i]; p.value = done[i]; const fin = done[i] >= t[1]; st.textContent = fin ? 'done' : active.includes(i) ? 'running' : 'waiting'; st.className = 'res ' + (fin ? 'pass' : active.includes(i) ? 'skip' : ''); });
      status.textContent = 'Time units: ' + ticks;
      if (done.every((d, i) => d >= TASKS[i][1])) { clearInterval(timer); timer = 0; run.textContent = 'Run again'; merge.disabled = false; status.textContent = 'Finished in ' + ticks + ' simulated time units. Merge waits for your approval.'; }
    }
    function start() { if (done.every((d, i) => d >= TASKS[i][1])) reset(); run.textContent = 'Pause'; timer = setInterval(tick, 450); }
    fill($('#sessions-app'), h('div', { class: 'bar', role: 'group', 'aria-label': 'Mode' }, modes), host, h('div', { class: 'bar' }, run, h('button', { type: 'button', text: 'Reset', onclick: reset }), merge), status);
    reset();
  })();

  /* ---------- 8 quality ---------- */
  (function () {
    const CHECKS = [['Unit tests', 'testing'], ['App flows in a browser', 'browserqa'], ['Mobile layout', 'browserqa'], ['Secret scan', 'scanners'], ['Dependency audit', 'scanners'], ['Permission review', 'security']];
    const inject = h('input', { type: 'checkbox' }), nobrowser = h('input', { type: 'checkbox' }), leak = h('input', { type: 'checkbox' });
    const ul = h('ul', { class: 'checks' }), verdict = h('p', { class: 'note', role: 'status' });
    let timer = 0;
    const outcome = i => (i === 0 && inject.checked) ? ['fail', 'failed: caption timing off by one word'] : ((i === 1 || i === 2) && nobrowser.checked) ? ['skip', 'skipped: no browser (not passed)'] : (i === 3 && leak.checked) ? ['fail', 'failed: key found in a config file'] : ['pass', 'passed'];
    function reset() {
      clearInterval(timer); timer = 0; run.disabled = false;
      fill(ul, CHECKS.map(([n, c]) => h('li', null, h('span', null, n + ' ', chip(CAP[c].status)), h('span', { class: 'res', text: 'not run' }))));
      verdict.className = 'note'; verdict.textContent = 'Not verified yet.';
    }
    const run = h('button', { type: 'button', class: 'primary', text: 'Run checks', onclick: () => {
      reset(); run.disabled = true; let i = 0; const res = [];
      const rows = $$('li .res', ul); rows[0].textContent = 'running'; rows[0].className = 'res run';
      timer = setInterval(() => {
        const [k, msg] = outcome(i); res.push(k); rows[i].textContent = msg; rows[i].className = 'res ' + k; i++;
        if (i < CHECKS.length) { rows[i].textContent = 'running'; rows[i].className = 'res run'; return; }
        clearInterval(timer); timer = 0; run.disabled = false;
        const f = res.filter(r => r === 'fail').length, sk = res.filter(r => r === 'skip').length;
        verdict.className = 'note ' + (f ? 'bad' : sk ? 'warn' : 'good');
        verdict.textContent = f ? 'Release blocked: ' + f + ' check(s) failed. Fix, then run again.' : sk ? 'Not verified: ' + sk + ' check(s) skipped. A skipped check is not a pass.' : 'All simulated checks passed. Ready for your review; you still decide the release.';
      }, 420);
    } });
    [inject, nobrowser, leak].forEach(e => e.addEventListener('change', reset));
    fill($('#quality-app'), h('div', { class: 'bar' }, h('label', { class: 'inline' }, inject, 'Inject a failing test'), h('label', { class: 'inline' }, nobrowser, 'Browser unavailable'), h('label', { class: 'inline' }, leak, 'Leak a secret')),
      h('div', { class: 'panel' }, ul), h('div', { class: 'bar' }, run, h('button', { type: 'button', text: 'Reset', onclick: reset })), verdict);
    reset();
  })();

  /* ---------- 9 budget and approvals ---------- */
  (function () {
    const PHASES = [['Research', 0.6, 140], ['Requirements', 0.3, 40], ['Architecture', 0.9, 150], ['Design', 0.5, 70], ['Build', 4.8, 900], ['Test and fix', 2.1, 380], ['Security review', 1.2, 190], ['Release notes', 0.3, 40]];
    let at = 0, spent = 0, tokens = 0, timer = 0;
    const cap = h('input', { type: 'range', min: 1, max: 20, step: 1, value: 6 }), capText = h('b');
    const meter = h('progress', { max: 6, value: 0, 'aria-label': 'Simulated spend against cap' });
    const rows = h('ul', { class: 'checks' }), status = h('p', { class: 'note', role: 'status' });
    const run = h('button', { type: 'button', class: 'primary', text: 'Run phases', onclick: () => {
      if (at >= PHASES.length) reset();
      run.disabled = true; clearInterval(timer);
      timer = setInterval(() => {
        const p = PHASES[at];
        if (!p) { clearInterval(timer); run.disabled = false; status.className = 'note good'; status.textContent = 'All phases fit the cap: $' + spent.toFixed(2) + ' simulated.'; return; }
        if (spent + p[1] > Number(cap.value) + 1e-9) { clearInterval(timer); run.disabled = false; status.className = 'note warn'; status.textContent = 'Stopped before "' + p[0] + '": it would exceed the $' + cap.value + ' cap. Raise the cap and press Run to continue.'; return; }
        spent += p[1]; tokens += p[2]; at++; draw();
      }, 420);
    } });
    function draw() {
      capText.textContent = '$' + cap.value; meter.max = Number(cap.value); meter.value = spent;
      fill(rows, PHASES.map((p, i) => h('li', null, h('span', { text: p[0] }), h('span', { class: 'res ' + (i < at ? 'pass' : ''), text: (i < at ? 'spent' : 'estimate') + ' $' + p[1].toFixed(2) + ' · ' + p[2] + 'k tokens' }))));
      total.textContent = 'Simulated spend $' + spent.toFixed(2) + ' of $' + cap.value + ' · ' + tokens + 'k tokens';
    }
    const total = h('p');
    function reset() { clearInterval(timer); at = spent = tokens = 0; run.disabled = false; status.className = 'note'; status.textContent = 'Set a cap, then run.'; draw(); }
    cap.addEventListener('input', draw);

    const queue = h('div'), log = h('ul', { class: 'log', 'aria-live': 'polite' }), err = h('p', { class: 'error', role: 'alert' });
    const name = h('input', { type: 'text', maxlength: 40, autocomplete: 'off' });
    let pending = [];
    const ITEMS = [['Run the project’s tests', 'Runs repository code on your machine.'], ['Install two dependencies', 'Downloads third-party code.'], ['Deploy a preview', 'Publishes to an external service.']];
    function drawQueue() {
      fill(queue, pending.length ? pending.map(it => h('div', { class: 'capline' }, h('span', null, h('b', { text: it[0] }), h('br'), h('span', { class: 'muted', text: it[1] })),
        h('span', { class: 'row' }, ['Approve', 'Reject'].map(a => h('button', { type: 'button', text: a, 'aria-label': a + ': ' + it[0], onclick: () => {
          if (!name.value.trim()) { err.textContent = 'Enter your name first. Every decision is recorded against a person.'; name.focus(); return; }
          err.textContent = ''; pending = pending.filter(x => x !== it);
          log.append(h('li', { text: (a === 'Approve' ? 'Approved' : 'Rejected') + ': ' + it[0] + ' — by ' + name.value.trim() + ' (simulated)' }));
          drawQueue(); name.focus();
        } }))))) : h('p', { class: 'muted', text: 'No approvals waiting.' }));
    }
    const resetQ = () => { pending = ITEMS.slice(); fill(log); err.textContent = ''; drawQueue(); };
    fill($('#budget-app'), h('div', { class: 'two' },
      h('div', { class: 'panel' }, h('h3', { text: 'Budget' }), h('label', null, 'Project cap: ', capText, cap), meter, total, rows, h('div', { class: 'bar' }, run, h('button', { type: 'button', text: 'Reset budget', onclick: reset })), status),
      h('div', { class: 'panel' }, h('h3', { text: 'Approval queue' }), h('label', null, 'Your name ', name), err, queue, log, h('button', { type: 'button', text: 'Reset approvals', onclick: resetQ }))));
    reset(); resetQ();
  })();

  /* ---------- guided runner shared by sections 11 and 12 ---------- */
  function makeRunner(root, sc) {
    const n = sc.stages.length, state = sc.stages.map(() => 'locked');
    let view = 0, front = 0, lines = 0, playing = false, timer = 0, speed = 1, lastKey = '';
    state[0] = 'running';
    const say = h('p', { class: 'sr', role: 'status' });
    const prog = h('progress', { max: n, value: 0, 'aria-label': 'Run progress' });
    const bPlay = h('button', { type: 'button', class: 'primary', onclick: () => playing ? pause() : play() });
    const bStep = h('button', { type: 'button', text: 'Skip to stage result', onclick: () => { pause(); if (state[front] === 'running') { view = front; lines = sc.stages[front].lines.length; complete(false); } } });
    const bBack = h('button', { type: 'button', text: '‹ Back', onclick: () => { view = Math.max(0, view - 1); draw(); } });
    const bNext = h('button', { type: 'button', text: 'Next ›', onclick: () => { if (view < n - 1 && state[view + 1] !== 'locked') view++; draw(); } });
    const bRestart = h('button', { type: 'button', text: 'Restart', onclick: () => { pause(); state.fill('locked'); state[0] = 'running'; view = front = lines = 0; sc.ctx.reset(); lastKey = ''; play(); } });
    const sel = h('select', { onchange: e => { speed = Number(e.target.value); if (playing) play(); } }, [['1', 'Normal'], ['2.5', 'Fast'], ['0.5', 'Slow']].map(([v, t]) => h('option', { value: v, text: t })));
    const side = sc.stages.map((x, i) => { const tag = h('small'); const b = h('button', { type: 'button', onclick: () => { view = i; draw(); } }, h('span', { text: (i + 1) + '. ' + x.title }), tag); return [b, tag]; });
    const out = h('div', { class: 'out' });
    function schedule() { clearInterval(timer); timer = setInterval(tick, 650 / speed); }
    function play() { if (state[front] !== 'running') { playing = false; draw(); return; } playing = true; view = front; schedule(); draw(); }
    function pause() { playing = false; clearInterval(timer); draw(); }
    function tick() { if (!root.isConnected || state[front] !== 'running') return pause(); if (lines < sc.stages[front].lines.length) { lines++; draw(); } else complete(playing); }
    function advance(keep) {
      state[front] = 'done'; say.textContent = sc.stages[front].title + ' complete.';
      if (front < n - 1) { const follow = view === front; front++; state[front] = 'running'; lines = 0; if (follow && keep) view = front; if (keep) { playing = true; schedule(); } }
      else { playing = false; clearInterval(timer); say.textContent = 'Simulated run finished.'; }
      draw();
    }
    function complete(keep) {
      if (sc.stages[front].gate) { state[front] = 'gate'; view = front; playing = false; clearInterval(timer); say.textContent = sc.stages[front].title + ': waiting for your approval.'; draw(); }
      else advance(keep);
    }
    function gateBox(i) {
      const g = sc.stages[i].gate, err = h('p', { class: 'error', role: 'alert' }), extra = g.form ? g.form(sc.ctx) : null;
      return h('div', { class: 'note warn' }, h('p', null, h('b', { text: 'Approval needed: ' }), g.ask), extra, err,
        h('div', { class: 'bar' },
          h('button', { type: 'button', class: 'primary', text: 'Approve and continue', onclick: () => { const problem = g.check && g.check(sc.ctx); if (problem) { err.textContent = problem; return; } sc.ctx.approved.push(sc.stages[i].title); advance(true); bPlay.focus(); } }),
          h('button', { type: 'button', text: 'Reject', onclick: () => { state[i] = 'rejected'; say.textContent = 'Rejected. The run is halted.'; draw(); bRestart.focus(); } })));
    }
    function draw() {
      const x = sc.stages[view], st = state[view];
      bPlay.textContent = playing ? 'Pause' : state[n - 1] === 'done' ? 'Finished' : 'Play';
      bPlay.disabled = state[front] !== 'running';
      bStep.disabled = state[front] !== 'running';
      bBack.disabled = view === 0;
      bNext.disabled = view === n - 1 || state[view + 1] === 'locked';
      prog.value = state.filter(v => v === 'done').length;
      side.forEach(([b, tag], i) => { b.disabled = state[i] === 'locked'; tag.textContent = { locked: '', running: i === front && playing ? 'running' : 'ready', gate: 'approve', done: 'done', rejected: 'halted' }[state[i]]; if (i === view) b.setAttribute('aria-current', 'step'); else b.removeAttribute('aria-current'); });
      const key = view + st + (st === 'running' ? lines : '');
      if (key === lastKey) return;
      lastKey = key;
      const showResult = st !== 'running';
      fill(out, h('div', { class: showResult ? 'fade' : '' },
        h('h3', { text: x.title }),
        h('p', null, h('span', { class: 'chip demo', text: 'Simulated' }), ' Real Studio today: ', chip(CAP[x.cap].status), ' ', h('span', { class: 'muted', text: CAP[x.cap].name })),
        h('ul', { class: 'log' }, x.lines.slice(0, st === 'running' ? lines : x.lines.length).map(t => h('li', { text: t }))),
        showResult ? x.render(sc.ctx) : h('p', { class: 'muted', text: playing ? 'Working (simulated)…' : 'Paused. Press Play or “Skip to stage result”.' }),
        st === 'gate' ? gateBox(view) : null,
        st === 'rejected' ? h('p', { class: 'note bad', text: 'Rejected. Nothing further happens. Use Restart to begin again.' }) : null));
    }
    fill(root, h('div', { class: 'runner fade' }, h('div', { class: 'bar' }, bPlay, bStep, bBack, bNext, bRestart, h('label', null, 'Speed ', sel)), prog,
      h('div', { class: 'runbody' }, h('ol', { 'aria-label': 'Stages' }, side.map(([b]) => h('li', null, b))), out), say));
    play();
    return { stop: () => { clearInterval(timer); } };
  }

  /* ---------- 11 idea → application demo ---------- */
  const DOMAIN = {
    video: { match: /\b(videos?|edit|editing|editor|films?|filmmaking|captions?|reels?|youtube|premiere|clips?)\b/i, label: 'creative video tool', cap: 'media', market: ['Cloud editors: easy to start, uploads required', 'Desktop editors: powerful, steep learning', 'Gap: local, word-safe automatic cuts'], tech: [['Speech-to-text library', 'MIT (example)', 'Reuse'], ['Media toolkit', 'LGPL/GPL (example)', 'Call as external tool'], ['Timeline UI kit', 'No licence (example)', 'Reject']], users: 'Solo creators', scope: ['Import and transcribe', 'Remove silences', 'Editable captions'], arch: ['Editor UI', 'Local job service', 'Media worker', 'Project database'], tasks: ['Data model', 'Transcription adapter', 'Cut planner', 'Caption editor'], fail: 'a cut edge fell inside a word', fix: 'snap every cut edge to word boundaries', items: ['Intro (6s)', 'Silent gap (3s)', 'Main point (14s)', 'Silent gap (2s)', 'Outro (5s)'], action: 'Remove silent gaps', apply: a => a.filter(t => !/Silent/.test(t)) },
    game: { match: /\b(games?|gaming|unreal|player|quest)\b/i, label: 'game', cap: 'game', market: ['Many short narrative games; discovery is hard', 'Engine templates speed prototypes', 'Gap: a tight, testable first level'], tech: [['Dialogue graph library', 'MIT (example)', 'Reuse'], ['Game engine', 'Vendor licence', 'Use under its terms'], ['Asset pack', 'Unclear (example)', 'Reject']], users: 'Story-game players', scope: ['One playable level', 'Dialogue choices', 'Save and load'], arch: ['Engine project', 'Dialogue system', 'Save system', 'Asset pipeline'], tasks: ['Design document', 'Movement prototype', 'Dialogue', 'Playtest build'], fail: 'save file lost a dialogue choice', fix: 'store choices in the save record', items: ['Gate: locked'], action: 'Pick up the key', apply: () => ['Key collected', 'Gate: open'] },
    book: { match: /\b(books?|novel|story|screenplay|manuscript|writing)\b/i, label: 'writing project', cap: 'publishing', market: ['Genre readers expect a clear hook', 'Series need a consistent world', 'Gap: continuity tracking across drafts'], tech: [['Document converter', 'GPL (example)', 'Call as external tool'], ['E-book packager', 'MIT (example)', 'Reuse'], ['Scraped corpus', 'Unclear (example)', 'Reject']], users: 'Thriller readers', scope: ['World bible', 'Chapter outline', 'Continuity checks'], arch: ['Manuscript files', 'World bible', 'Continuity checker', 'Export pipeline'], tasks: ['World bible', 'Outline', 'Chapter 1 draft', 'Continuity pass'], fail: 'a character age differs between chapters', fix: 'read ages from the world bible', items: ['Chapter 1: draft'], action: 'Add next chapter', apply: a => a.concat('Chapter ' + (a.length + 1) + ': outline') },
    website: { match: /\b(website|landing|portfolio|blog|homepage)\b/i, label: 'website', cap: 'website', market: ['Templates look alike', 'Speed and clarity convert', 'Gap: distinctive design with checked layouts'], tech: [['Static page tooling', 'MIT (example)', 'Reuse'], ['Icon set', 'MIT (example)', 'Reuse with notice'], ['Tracker script', 'Proprietary (example)', 'Reject']], users: 'Small businesses', scope: ['Home, work, contact', 'Responsive layout', 'Accessibility checks'], arch: ['Static pages', 'Design tokens', 'Form handler', 'Deploy notes'], tasks: ['Content', 'Design tokens', 'Pages', 'Layout checks'], fail: 'horizontal scroll at 375px', fix: 'allow the grid columns to shrink', items: ['Hero', 'Work', 'Contact'], action: 'Add a testimonials section', apply: a => a.includes('Testimonials') ? a : a.concat('Testimonials') },
    saas: { match: /./, label: 'web application', cap: 'saas', market: ['Established tools are broad and costly', 'Niche users accept fewer features', 'Gap: one workflow done well'], tech: [['Web framework', 'MIT (example)', 'Reuse'], ['Database', 'Open source (example)', 'Use under its licence'], ['Admin theme', 'No licence (example)', 'Reject']], users: 'Small teams', scope: ['Sign-up and login', 'Records list', 'Add, edit, delete'], arch: ['Web UI', 'API', 'Auth', 'Database'], tasks: ['Schema', 'Auth', 'Record screens', 'Tests'], fail: 'a second user could see another user’s record', fix: 'filter every query by the signed-in user', items: ['Record 1'], action: 'Add a record', apply: a => a.concat('Record ' + (a.length + 1)) }
  };
  let demoRunner = null;
  function startDemo(idea) {
    const key = Object.keys(DOMAIN).find(k => DOMAIN[k].match.test(idea)), d = DOMAIN[key];
    const ctx = { approved: [], items: [], history: [], reset() { this.approved = []; this.items = d.items.slice(); this.history = []; } };
    ctx.reset();
    const st = (title, cap, lines, render, gate) => ({ title, cap, lines, render, gate });
    function preview() {
      const ul = h('ul', { class: 'clips', 'aria-live': 'polite' });
      const undo = h('button', { type: 'button', text: 'Undo', onclick: () => { ctx.items = ctx.history.pop() || ctx.items; draw(); } });
      const draw = () => { fill(ul, ctx.items.map(t => h('li', { class: /Silent|locked/.test(t) ? 'gap' : '', text: t }))); undo.disabled = !ctx.history.length; };
      const act = h('button', { type: 'button', class: 'primary', text: d.action, onclick: () => { const next = d.apply(ctx.items); if (next.join() !== ctx.items.join()) { ctx.history.push(ctx.items); ctx.items = next; draw(); } } });
      draw();
      return h('div', { class: 'app' }, h('header', null, h('b', { text: 'Sample ' + d.label }), h('span', { class: 'chip demo', text: 'Representative preview' })), h('div', { class: 'body' }, ul, h('div', { class: 'bar' }, act, undo)));
    }
    const report = () => ['SIMULATED DELIVERY REPORT (no real work was done)', 'Idea: ' + idea, 'Type: ' + d.label, 'Approvals given: ' + (ctx.approved.join(', ') || 'none'), 'Tests: 1 failure found, fixed, re-run passed (simulated)', 'Not verified: real users, real devices, security review, deployment', 'Real Studio status for this product type: ' + D.STATUS[CAP[d.cap].status].label].join('\n');
    const stages = [
      st('Understand the idea', 'intake', ['Reading the idea', 'Choosing a product type', 'Drafting essential questions'], () => [h('p', null, 'Idea: ', h('q', { text: idea })), h('p', { text: 'Recognised as: ' + d.label + ' (keyword match).' }), h('h4', { text: 'Questions Studio would ask' }), list(['Who is the first user?', 'What must work in version one?', 'What budget and deadline apply?'])]),
      st('Research the market', 'research', ['Listing comparable products', 'Summarising strengths and gaps', 'Marking unverified claims'], () => [list(d.market), h('p', { class: 'muted', text: 'Invented examples. Real research must cite sources.' })]),
      st('Discover technology', 'discover', ['Searching candidate repositories', 'Reading licences', 'Scoring fit'], () => table(['Candidate', 'Licence', 'Decision'], d.tech)),
      st('Product brief', 'prd', ['Writing scope', 'Writing acceptance criteria'], () => [h('p', { text: 'Primary users: ' + d.users + '.' }), h('h4', { text: 'Version one' }), list(d.scope)], { ask: 'Accept this scope before design starts?' }),
      st('Architecture', 'architecture', ['Choosing components', 'Recording decisions'], () => table(['Component', 'Order'], d.arch.map((a, i) => [a, String(i + 1)]))),
      st('Feature plan', 'prd', ['Ranking features'], () => table(['Feature', 'Priority'], d.scope.map((f, i) => [f, i < 2 ? 'Must' : 'Should']))),
      st('Development tasks', 'plan', ['Splitting work', 'Linking dependencies', 'Estimating cost'], () => [table(['Task', 'Depends on'], d.tasks.map((t, i) => [t, i ? d.tasks[i - 1] : 'nothing'])), h('p', { text: 'Simulated estimate: $7.40.' })], { ask: 'Allow a build with a simulated $10 budget cap?' }),
      st('Parallel sessions', 'parallel', ['Assigning file ownership', 'Session 1 working', 'Session 2 working', 'Merging after checks'], () => [table(['Session', 'Task', 'State'], d.tasks.map((t, i) => ['Session ' + (i % 2 + 1), t, 'merged (simulated)'])), CAP[d.cap].status === 'planned' ? h('p', { class: 'note warn', text: 'Studio has no ' + CAP[d.cap].name.toLowerCase() + ' pack yet. This shows the intended flow only.' }) : null]),
      st('Test and fix', 'testing', ['Running checks', 'Failure: ' + d.fail, 'Fix: ' + d.fix, 'Re-running checks'], () => [table(['Run', 'Result', 'Detail'], [['1', 'Failed', d.fail], ['2', 'Passed (simulated)', d.fix]]), h('p', { class: 'muted', text: 'Not covered: real devices and an independent security review.' })]),
      st('Delivery report', 'docs', ['Collecting evidence', 'Writing the report'], () => {
        const area = h('textarea', { rows: 8, readonly: true, 'aria-label': 'Simulated delivery report' }); area.value = report();
        const said = h('span', { role: 'status' });
        return [preview(), area, h('p', { class: 'bar' }, h('button', { type: 'button', text: 'Copy report', onclick: () => copy(area.value, area, said) }), said)];
      })
    ];
    if (demoRunner) demoRunner.stop();
    demoRunner = makeRunner($('#demo-app'), { stages, ctx });
  }
  $('#idea-form').addEventListener('submit', e => {
    e.preventDefault();
    const v = $('#idea').value.trim(), err = $('#idea-error');
    if (v.length < 8) { err.textContent = 'Describe the idea in at least 8 characters.'; $('#idea').focus(); return; }
    err.textContent = ''; startDemo(v);
  });
  const PRESETS = [['AI video editor', 'I want to build an AI video editing application.'], ['Story game', 'A story-driven game set in a mythological city'], ['Thriller novel', 'A mythology thriller novel and screenplay'], ['Studio website', 'A distinctive website for a small design studio'], ['Booking app', 'An app where clinics manage bookings']];
  $('#presets').append(...PRESETS.map(([label, idea]) => h('button', { type: 'button', text: label, onclick: () => { $('#idea').value = idea; $('#idea-error').textContent = ''; startDemo(idea); } })));

  /* ---------- 12 existing product walkthrough ---------- */
  let repoRunner = null;
  function startImport(repo) {
    const RECS = ['Add tests around booking conflicts', 'Fix the form that loses input on errors', 'Update two outdated dependencies', 'Write setup documentation'];
    const ctx = { approved: [], chosen: [], name: '', reset() { this.approved = []; this.chosen = [RECS[0]]; this.name = ''; } };
    ctx.reset();
    const st = (title, cap, lines, render, gate) => ({ title, cap, lines, render, gate });
    const chosen = () => ctx.chosen.length ? ctx.chosen : ['nothing'];
    const stages = [
      st('Import repository', 'repowork', ['Registering ' + repo + ' (label only)', 'Your checkout stays untouched'], () => h('p', { text: 'Sample record created for “' + repo + '”. Nothing was fetched.' })),
      st('Understand codebase', 'understand', ['Mapping folders', 'Reading licence and tests', 'Tracing the booking flow'], () => table(['Area', 'Finding (fictional)'], [['Stack', 'Web app with a small API'], ['Tests', '12 tests, none for booking conflicts'], ['Licence', 'Proprietary']])),
      st('Audit', 'understand', ['Checking quality', 'Checking dependencies', 'Checking user flows'], () => table(['Severity', 'Issue (fictional)'], [['High', 'Two people can book the same slot'], ['Medium', 'Form clears when validation fails'], ['Low', 'Setup steps are undocumented']])),
      st('Identify gaps', 'understand', ['Comparing behaviour with intended product'], () => list(['No conflict handling', 'No reminder emails', 'No documentation for new developers'])),
      st('Recommend improvements', 'understand', ['Ranking by impact, effort and risk'], () => table(['Recommendation', 'Effort', 'Risk'], RECS.map((r, i) => [r, ['Medium', 'Small', 'Medium', 'Small'][i], ['Low', 'Low', 'Medium', 'None'][i]]))),
      st('Approve', 'approvals', ['Preparing the decision'], () => h('p', { text: 'Nothing changes until you choose the work and approve it.' }), {
        ask: 'Choose what Studio may implement, and sign your name.',
        form: c => {
          const name = h('input', { type: 'text', maxlength: 40, value: c.name, oninput: e => { c.name = e.target.value; } });
          return h('fieldset', null, h('legend', { text: 'Recommendations' }), RECS.map(r => h('label', { class: 'inline' }, h('input', { type: 'checkbox', checked: c.chosen.includes(r), onchange: e => { c.chosen = e.target.checked ? c.chosen.concat(r) : c.chosen.filter(x => x !== r); } }), r)), h('label', null, 'Your name ', name));
        },
        check: c => !c.chosen.length ? 'Select at least one recommendation, or reject.' : !c.name.trim() ? 'Enter your name to record the decision.' : ''
      }),
      st('Implement', 'repowork', ['Creating an isolated branch', 'Editing files', 'Preparing the diff'], () => [h('p', null, 'Branch ', h('code', { text: 'studio/booking-app-change' }), ' (fictional)'), h('pre', { class: 'diff' }, chosen().map(r => h('div', { class: 'add', text: '+ change: ' + r })))]),
      st('Regression test', 'testing', ['Running existing tests', 'Running new tests'], () => h('p', { class: 'note good', text: 'Simulated: existing and new tests passed. A real run needs your approval first.' }), { ask: 'Accept this diff and these results?' }),
      st('Release', 'release', ['Writing release notes', 'Preparing the merge command'], () => h('p', { text: 'Release notes prepared. You run the merge and publish; Studio does not.' })),
      st('Maintain', 'monitor', ['Recording a health check plan'], () => [h('p', { text: 'Next: weekly regression run and dependency review (planned schedule, nothing is running).' }), h('p', { class: 'note', text: 'Walkthrough complete. Approved: ' + chosen().join('; ') + '.' })])
    ];
    if (repoRunner) repoRunner.stop();
    repoRunner = makeRunner($('#improve-app'), { stages, ctx });
  }
  $('#repo-form').addEventListener('submit', e => {
    e.preventDefault();
    const v = $('#repo').value.trim(), err = $('#repo-error');
    if (!/^[\w.-]+(\/[\w.-]+)?$/.test(v)) { err.textContent = 'Use a name such as team/project (letters, numbers, dot, dash, underscore).'; $('#repo').focus(); return; }
    err.textContent = ''; startImport(v);
  });
  const idle = (root, text) => fill(root, h('p', { class: 'note', text }));
  idle($('#demo-app'), 'Press “Start simulated run” or choose an example.');
  idle($('#improve-app'), 'Press “Start simulated import” to begin.');

  /* ---------- 10 portfolio, 13 specialists, products ---------- */
  const portfolio = (function () {
    const root = $('#portfolio-app'), cats = ['All', ...new Set(D.PORTFOLIO.map(p => p.category))];
    let cat = 'All', cur = D.PORTFOLIO[0].id;
    const filters = cats.map(c => h('button', { type: 'button', text: c, 'aria-pressed': String(c === cat), onclick: () => { cat = c; filters.forEach(b => b.setAttribute('aria-pressed', String(b.textContent === c))); const shown = visible(); if (!shown.some(p => p.id === cur)) cur = shown[0].id; draw(); } }));
    const listEl = h('div', { class: 'plist' }), orbit = h('div', { class: 'orbit' }), detail = h('div', { class: 'panel', 'aria-live': 'polite' });
    const visible = () => D.PORTFOLIO.filter(p => cat === 'All' || p.category === cat);
    function select(id) { cur = id; draw(); }
    function draw() {
      const shown = visible(), p = D.PORTFOLIO.find(x => x.id === cur);
      const btns = shown.map(x => h('button', { type: 'button', 'aria-pressed': String(x.id === cur), onclick: () => { select(x.id); const b = $('[data-id="' + x.id + '"]', listEl); if (b) b.focus(); }, 'data-id': x.id }, x.name, h('small', { text: x.stage })));
      fill(listEl, btns);
      const nodes = shown.map((x, i) => {
        const a = (i / shown.length) * Math.PI * 2 - Math.PI / 2, px = 230 + Math.cos(a) * 165, py = 190 + Math.sin(a) * 160, on = x.id === cur;
        return [s('path', { class: 'edge' + (on ? ' on' : ''), d: 'M230 190 L' + px + ' ' + py }), s('g', { class: 'node' + (on ? ' on' : ''), onclick: () => select(x.id) }, s('rect', { x: px - 58, y: py - 15, width: 116, height: 30, rx: 8 }), s('text', { x: px, y: py + 4, 'text-anchor': 'middle', text: x.name.length > 17 ? x.name.slice(0, 16) + '…' : x.name }))];
      });
      // Mouse shortcut only; the buttons above are the accessible control.
      fill(orbit, s('svg', { viewBox: '0 0 460 380', 'aria-hidden': 'true' }, nodes.map(n => n[0]), nodes.map(n => n[1]), s('g', { class: 'node on' }, s('rect', { x: 185, y: 168, width: 90, height: 44, rx: 12 }), s('text', { x: 230, y: 195, 'text-anchor': 'middle', text: 'Studio' }))));
      const by = {}; p.caps.forEach(c => { by[CAP[c].status] = (by[CAP[c].status] || 0) + 1; });
      const url = D.LINKS[p.id], existing = p.stage === 'Existing product';
      fill(detail, h('div', { class: 'fade' }, h('h3', { text: p.name }), h('p', { class: 'muted', text: p.category + ' · ' + p.stage }), h('p', { text: p.purpose }),
        h('h4', { text: 'Adapted workflow (intended)' }), h('p', { text: p.useCase }),
        h('h4', { text: 'Capabilities it needs: ' + Object.entries(by).map(([k, v]) => v + ' ' + D.STATUS[k].label.toLowerCase()).join(', ') }), p.caps.map(capLine),
        h('div', { class: 'bar' },
          h('button', { type: 'button', class: 'primary', text: existing ? 'Walk through an import' : 'Simulate this in the demo', onclick: () => {
            if (existing) { $('#repo').value = 'sample/' + p.id; startImport($('#repo').value); smooth($('#improve')); $('#repo').focus({ preventScroll: true }); }
            else { const idea = p.name + ': ' + p.purpose; $('#idea').value = idea.slice(0, 160); startDemo($('#idea').value); smooth($('#demo')); $('#idea').focus({ preventScroll: true }); }
          } }),
          url ? h('a', { class: 'btn', href: url, target: '_blank', rel: 'noopener noreferrer', text: 'Visit ' + p.name + ' site ↗' }) : null)));
    }
    fill(root, h('div', { class: 'bar', role: 'group', 'aria-label': 'Filter by category' }, filters), h('div', { class: 'portfolio' }, h('div', null, orbit, listEl), detail));
    draw();
    return { show(id) { cat = 'All'; filters.forEach(b => b.setAttribute('aria-pressed', String(b.textContent === 'All'))); select(id); smooth($('#portfolio')); const b = $('[data-id="' + id + '"]', listEl); if (b) b.focus({ preventScroll: true }); } };
  })();

  const ext = (url, text) => h('a', { class: 'btn', href: url, target: '_blank', rel: 'noopener noreferrer', text: text + ' ↗' });
  fill($('#products-app'), D.PORTFOLIO.filter(p => D.LINKS[p.id]).map(p => h('article', null, h('h3', { text: p.name }), h('p', { text: p.purpose }),
    h('div', { class: 'bar' }, ext(D.LINKS[p.id], 'Visit ' + p.name), h('button', { type: 'button', text: 'How Studio fits', 'aria-label': 'How Studio fits ' + p.name, onclick: () => portfolio.show(p.id) })))),
    h('article', null, h('h3', { text: 'The creator' }), h('p', { text: 'More work from the person building these products.' }), h('div', { class: 'bar' }, ext(D.CREATOR_URL, 'Visit portfolio'))));
  fill($('#footer-links'), D.PORTFOLIO.filter(p => D.LINKS[p.id]).map(p => h('a', { href: D.LINKS[p.id], target: '_blank', rel: 'noopener noreferrer', text: p.name + ' ↗' })), h('a', { href: D.CREATOR_URL, target: '_blank', rel: 'noopener noreferrer', text: 'Creator portfolio ↗' }));

  fill($('#specialists-app'), h('div', { class: 'cards' }, D.CAPABILITIES.filter(c => c.domain === 'Specialist packs' || c.id === 'website' || c.id === 'saas').map(c => {
    const used = D.PORTFOLIO.filter(p => p.caps.includes(c.id));
    return h('article', null, h('h3', { text: c.name }), h('p', null, chip(c.status)), h('p', { text: c.goal }), h('p', { class: 'muted', text: c.today }),
      used.length ? h('div', { class: 'bar' }, used.map(p => h('button', { type: 'button', text: p.name, 'aria-label': 'Show ' + p.name + ' in portfolio', onclick: () => portfolio.show(p.id) }))) : null);
  })));

  /* ---------- 15 beta request (local only) ---------- */
  $('#beta-form').addEventListener('submit', e => {
    e.preventDefault();
    const what = $('#b-what').value.trim(), err = $('#beta-error');
    if (what.length < 10) { err.textContent = 'Describe the product in at least 10 characters.'; $('#b-what').focus(); return; }
    err.textContent = '';
    $('#b-out').value = 'Token Zombie Studio beta request\nGoal: ' + new FormData(e.target).get('path') + '\nProduct: ' + what;
    $('#b-copy').disabled = false;
    $('#b-status').textContent = 'Prepared. Not sent anywhere.';
  });
  $('#b-copy').addEventListener('click', () => copy($('#b-out').value, $('#b-out'), $('#b-status')));

  setMotion(motion);
  onScroll();
})();
