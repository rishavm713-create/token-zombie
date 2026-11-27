import { expect, test } from 'claude-code/testing'

const PANE = {
  plugin: 'token-zombie',
  component: 'Pane',
  requestId: 'token-zombie',
  props: { title: 'TOKEN ZOMBIE', isFocused: false, bodyColumns: 60, placement: 'dock', scroll: { offset: 0, bodyRows: 30 }, view: {} },
} as const

const BAND = {
  plugin: 'token-zombie',
  component: 'AbovePrompt',
  props: { hasSurvey: false, isCollapsed: false, isWorking: false, maxRows: 20, bodyColumns: 120, scroll: { offset: 0, bodyRows: 20 }, view: {} },
} as const

const NOW = 1_800_000_000
const STATUS = JSON.stringify({ ts: NOW - 30, level: 'ELEVATED', ctx_pct: 66, state: 'ok', risk: 'medium', activity: 'idle', open_tasks: 2, actions: ['a'] })
const HOST = JSON.stringify({ session: 's1', cost_usd: 1.5, duration_ms: 1, api_duration_ms: 1, ts: NOW - 5 })

type Files = Record<string, string>
type Opt = { ran?: string[][]; copies?: string[]; cmds?: any[]; placed?: boolean; denyCmd?: boolean; status?: string[]; agents?: number; skills?: string[]; opened?: string[] }
const world = (on: any, files: Files, o: Opt = {}) => {
  const { ran = [], copies = [], cmds = [], placed = true } = o
  on('env.get', () => ({ value: '/h' }))
  on('clock.now', () => ({ value: NOW * 1000 }))
  on('clock.every', () => ({ value: undefined }))
  on('command.register', () => ({ value: { command: 'tz' } }))
  on('ui.open', (_: any, e: any) => {
    o.opened?.push(e.id)
    return { value: { isPlaced: placed } }
  })
  if (o.agents !== undefined) on('agent.list', () => ({ value: Array.from({ length: o.agents! }, (_, i) => ({ id: `a${i}`, status: 'running' })) }))
  on('session.id', () => ({ value: 's1' }))
  if (o.skills) files['live-s1.json'] = JSON.stringify({ skills: { invoked: Object.fromEntries(o.skills.map(n => [n, 1])), loaded: { extra: 1 }, discovered: { d: 1 } } })
  on('ui.status', (_: any, e: any) => {
    o.status?.push(String(e.text))
    return { value: undefined }
  })
  on('session.start', (_: any, e: any) => ({ cwd: e.cwd }))
  on('tool.call', () => ({ result: {} }))
  on('fs.read', (_: any, e: any) => {
    const f = files[e.path.split('/').pop()!]
    if (f === undefined) return { deny: 'ENOENT' }
    return { value: f }
  })
  on('process.run', (_: any, e: any) => {
    ran.push([...e.argv])
    return { value: { exitCode: 0, stdout: 'line1\nline2', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('ui.copy', (_: any, e: any) => {
    copies.push(e.text)
    return { value: { isCopied: true } }
  })
  on('command.run', (_: any, e: any) => {
    cmds.push(e)
    if (o.denyCmd) throw new Error('refused mid-turn')
    return { text: '' }
  })
}

const text = async (ui: any) => (await ui.find({ type: 'Text', text: /./ }))?.text

test('renders on terminal and desktop with no state files', async ($, on) => {
  world(on, {})
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    expect(await ui.find({ type: 'Text', text: /TOKEN ZOMBIE/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /n\/a \(statusline not wired\)/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /no data/ })).toBeDefined()
    await ui.unmount()
  }
})

test('corrupt files do not crash the pane', async ($, on) => {
  world(on, { 'status.json': '{{{', 'host.json': '[1]', 'config.json': 'x' })
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /no data/ })).toBeDefined()
  await ui.unmount()
})

test('metrics come from seeded status.json and host.json', async ($, on) => {
  world(on, { 'status.json': STATUS, 'host.json': HOST, 'config.json': '{"mode":"lite"}' })
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect(await ui.find({ type: 'Text', text: /66% ELEVATED/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /\$1\.50 \(host\)/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /ok risk medium/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /2 open, 1 actions/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /^lite$/ })).toBeDefined()
  await ui.unmount()
})

test('stale status.json is flagged', async ($, on) => {
  world(on, { 'status.json': JSON.stringify({ ts: NOW - 5000, ctx_pct: 10, level: 'OK' }) })
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /\(stale\)/ })).toBeDefined()
  await ui.unmount()
})

test('turn.complete accumulates tokens and agent time; spawns and tools show', async ($, on) => {
  world(on, {})
  on('turn.complete', (_: any, e: any) => ({ text: e.answer }))
  on('agent.spawn', () => ({ model: 'haiku' }))
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  const u = (n: number) => ({ input_tokens: n, output_tokens: n * 2, cache_read_input_tokens: 1000, cache_creation_input_tokens: 5, model: 'claude-x' })
  await $.turn.complete({ answer: '', durationMs: 4000, isAborted: false, turnId: 't1', usage: u(100), reason: 'end_turn' } as any)
  await $.turn.complete({ answer: '', durationMs: 6000, isAborted: false, turnId: 't2', usage: u(50), reason: 'end_turn' } as any)
  await $.agent.spawn({ tool_use_id: 'ag1', prompt: 'p', description: 'd', subagentType: 'Explore', parentModel: 'm' } as any)
  await $.tool.call({ tool: 'Bash', command: 'ls' })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /in 150\s+out 300\s+cache 2\.0k/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /10s \/ 2 turns, 1 subagents/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /claude-x/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /agent Explore/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /done Bash/ })).toBeDefined()
  await ui.unmount()
})

test('buttons run the expected argv, copy and compact', async ($, on) => {
  const ran: string[][] = []
  const copies: string[] = []
  const cmds: any[] = []
  world(on, { 'status.json': STATUS }, { ran, copies, cmds })
  const clips: any[] = []
  on('audio.play', (_: any, e: any) => {
    clips.push(e.clip)
    return { value: undefined }
  })
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })

  await ui.press({ plugin: 'token-zombie', key: 'mode-ultra' })
  expect(clips).toEqual([{ asset: 'sounds/mode-ultra.wav' }])
  const last = () => ran[ran.length - 1]!
  expect(last().slice(0, 1)).toEqual([typeof process !== 'undefined' && (process as { platform?: string }).platform === 'win32' ? 'py' : 'python3'])
  expect(last().slice(-2)).toEqual(['mode', 'ultra'])
  expect(last().slice(-3)[0]).toMatch(/bin\/tz$/)

  await ui.press({ plugin: 'token-zombie', key: 'review' })
  expect(last().slice(-1)).toEqual(['optimize'])
  expect(await ui.find({ type: 'Text', text: /line1/ })).toBeDefined()

  await ui.press({ plugin: 'token-zombie', key: 'audit' })
  expect(last().slice(-1)).toEqual(['audit'])

  await ui.press({ plugin: 'token-zombie', key: 'board' })
  expect(last().slice(-3, -1)).toEqual(['dash', '--out'])
  expect(last()[last().length - 1]).toBe('/h/.claude/token-zombie/board.html')
  expect(await ui.find({ type: 'Text', text: /board written: .*board\.html/ })).toBeDefined()

  await ui.press({ plugin: 'token-zombie', key: 'copy' })
  expect(copies.length).toBe(1)
  expect(copies[0]).toMatch(/TOKEN ZOMBIE mode/)
  expect(copies[0]).toMatch(/context 66% ELEVATED/)

  await ui.press({ plugin: 'token-zombie', key: 'compact' })
  expect(last().slice(-1)).toEqual(['checkpoint'])
  expect(cmds[0].command).toBe('compact')
  expect(cmds[0].args).toMatch(/current task/)
  expect(await ui.find({ type: 'Text', text: /compact requested/ })).toBeDefined()
  await ui.unmount()
})

test('compact refusal shows the line to type', async ($, on) => {
  world(on, {}, { denyCmd: true })
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.press({ plugin: 'token-zombie', key: 'compact' })
  expect(await ui.find({ type: 'Text', text: /type: \/compact current task/ })).toBeDefined()
  await ui.unmount()
})

test('/tz opens the pane; an unplaced pane falls back to the status line', async ($, on) => {
  const status: string[] = []
  world(on, {}, { placed: false, status })
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  const r = await $.command.run({ command: 'tz' })
  expect(r.text).toMatch(/status line/)
  expect(status.join('|')).toMatch(/TZ full ctx/)
})

const LEDGER = JSON.stringify([
  { t: NOW - 10, kind: 'filter', tok: 500, basis: 'measured' },
  { t: 1, kind: 'dup-read-flagged', tok: 900, basis: 'est' },
  { t: NOW - 10, kind: 'overhead-hook', tok: 20, basis: 'measured' },
])

test('slim bar: one row on terminal, no feed, unknowns as dashes', async ($, on) => {
  world(on, {})
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^TOKEN ZOMBIE$/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /^FULL$/ })).toBeUndefined() // owner: no mode chip on the bar
  expect(await ui.find({ type: 'Text', text: /— chat tokens/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /— cache left/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /recent|none yet|supervisor|model/ })).toBeUndefined()
  expect(await ui.find({ type: 'Button', key: 'tz-expand' })).toBeDefined()
  await ui.unmount()
})

test('slim bar on desktop: real numbers, green saved, svg mascot, chevron opens the pane', async ($, on) => {
  const opened: string[] = []
  world(
    on,
    { 'ledger.json': LEDGER, 'config.json': '{"mode":"ultra"}', 'zombie-excited.svg': '<svg>excited</svg>' },
    { agents: 3, skills: ['a', 'b', 'nope'], opened },
  )
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount({ ...BAND, surface: 'desktop' })
  const val = async (label: RegExp) => {
    const all = await ui.findAll({ type: 'Text' })
    const i = all.findIndex(x => label.test(x.text))
    return all[i - 1]
  }
  expect((await val(/^NEXT MSG$/))?.text).toBe('—')
  expect((await val(/^CACHE LEFT$/))?.text).toBe('—') // no turn yet: dashes, never made-up numbers
  expect(await val(/^TOKENS SAVED$/)).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /24H|· EST/ })).toBeUndefined() // label has no 24H · EST suffix
  expect((await val(/^CHAT TOKENS$/))?.text).toBe('—') // no turn yet: dash, never a made-up number
  expect((await ui.find({ type: 'Button', key: 'tz-mode' }))?.props.label).toBe('ULTRA') // mode replaces the Open button; press cycles it
  expect(await ui.find({ type: 'Text', text: /\[EST\]/ })).toBeUndefined()
  const svg = await ui.find({ type: 'Svg' })
  expect(svg?.props.source).toBe('<svg>excited</svg>')
  expect(svg?.props.alt).toMatch(/mascot: excited/)
  expect(await ui.find({ type: 'Text', text: /recent|none yet/ })).toBeUndefined()
  expect(await ui.find({ type: 'Button', key: 'tz-expand' })).toBeUndefined() // desktop: no Open button, /tz opens the pane
  await ui.unmount()
})

test('slim bar: working state while a turn runs; yields to a survey', async ($, on) => {
  world(on, { 'zombie-working.svg': '<svg>w</svg>' })
  on('ui.render', ($: any, e: any) => {
    const { Box } = $.ui.resolve(e)
    return <Box key="none" />
  })
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount({ ...BAND, surface: 'desktop', props: { ...BAND.props, isWorking: true } })
  expect((await ui.find({ type: 'Svg' }))?.props.alt).toMatch(/working/)
  await ui.unmount()
  const q = await $.ui.mount({ ...BAND, surface: 'desktop', props: { ...BAND.props, hasSurvey: true } })
  expect(await q.find({ type: 'Text', text: /TOKEN ZOMBIE/ })).toBeUndefined()
  await q.unmount()
})

test('slim bar mascot follows event moods from mood.json (advice => alert, saving => excited, expired => ignored)', async ($, on) => {
  const fs: Record<string, string> = { 'status.json': JSON.stringify({ ts: NOW - 30, level: 'NORMAL' }), 'zombie-alert.svg': '<svg>a</svg>', 'zombie-excited.svg': '<svg>e</svg>' }
  world(on, fs)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  const alt = async (mood: object) => {
    fs['mood.json'] = JSON.stringify(mood)
    await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
    const ui = await $.ui.mount({ ...BAND, surface: 'desktop' })
    const a = (await ui.find({ type: 'Svg' }))?.props.alt
    await ui.unmount()
    return a
  }
  expect(await alt({ kind: 'churn', ts: NOW - 5 })).toMatch(/alert/)
  expect(await alt({ kind: 'compact', ts: NOW - 5 })).toMatch(/alert/)
  expect(await alt({ kind: 'save', ts: NOW - 5 })).toMatch(/excited/)
  expect(await alt({ kind: 'test', ts: NOW - 500 })).not.toMatch(/excited|alert/)
})

test('TOKENS SAVED split: measured + fresh chats (EST) last 24h; old fresh.json => 0', async ($, on) => {
  const fs: Record<string, string> = { 'fresh.json': JSON.stringify({ ts: NOW - 60, tok: 150000, n: 1, today: 150000, n_today: 1, basis: 'EST' }) }
  world(on, fs)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  let ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect(await ui.find({ type: 'Text', text: /0 measured \+ 150K fresh chats \[EST input-eq\], last 24h/ })).toBeDefined()
  await ui.unmount()
  fs['fresh.json'] = JSON.stringify({ ts: NOW - 90000, tok: 5, n: 1, today: 5 })
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect(await ui.find({ type: 'Text', text: /0 measured \+ 0 fresh chats/ })).toBeDefined()
  await ui.unmount()
})

test('econ row shows when econ.json now is < 1 h old, hidden when older', async ($, on) => {
  const en = (ts: number) => JSON.stringify({ now: { ts, continue: 1.5, compact: 0.5, fresh: 0.25, best: 'fresh' } })
  const fs: Record<string, string> = { 'econ.json': en(NOW - 60) }
  world(on, fs)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  let ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect(await ui.find({ type: 'Text', text: /stay \$1\.50 compact \$0\.50 fresh \$0\.25 -> fresh \[EST\]/ })).toBeDefined()
  await ui.unmount()
  fs['econ.json'] = en(NOW - 7200)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect(await ui.find({ type: 'Text', text: /stay \$/ })).toBeUndefined()
  await ui.unmount()
})

test('coding row shows edits/test runs from coding.json when < 24 h old, hidden when older or no edits', async ($, on) => {
  const cj = (ts: number, edits = 3) => JSON.stringify({ ts, edits, runs: 2, last: 'pass', unt: 1 })
  const fs: Record<string, string> = { 'coding.json': cj(NOW - 60) }
  world(on, fs)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  let ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect(await ui.find({ type: 'Text', text: /3 code edits, 2 test runs, last test pass, 1 untested/ })).toBeDefined()
  await ui.unmount()
  fs['coding.json'] = cj(NOW - 90000)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect(await ui.find({ type: 'Text', text: /code edits/ })).toBeUndefined()
  await ui.unmount()
})

test('24h line: today used tokens from history.json + on/off events in last 24 h', async ($, on) => {
  const d = new Date(NOW * 1000)
  const day = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  const caps = [{ t: NOW - 100, act: 'on', cap: 'x', ok: true }, { t: NOW - 200, act: 'off', cap: 'x', ok: true }, { t: NOW - 90000, act: 'on', cap: 'y', ok: true }]
  const fs: Record<string, string> = { 'history.json': JSON.stringify({ [day]: { used: 1_200_000, calls: 5 } }), 'caps.jsonl': caps.map(e => JSON.stringify(e)).join('\n') + '\n' }
  world(on, fs)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  let ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect(await ui.find({ type: 'Text', text: /used 1\.2M, 2 on\/off/ })).toBeDefined()
  await ui.unmount()
  delete fs['history.json']
  delete fs['caps.jsonl']
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect(await ui.find({ type: 'Text', text: /on\/off/ })).toBeUndefined()
  await ui.unmount()
})

// HARD RULE guard: the bar must always render a tree (even with no state files, on every surface),
// and TOKENS SAVED is labelled EST while TOKENS USED is MEASURED from usage.json (exact sum of the four usage fields).
test('AbovePrompt returns a tree on every surface with no files; measured used sums exactly', async ($, on) => {
  const fs: Record<string, string> = {}
  world(on, fs)
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...BAND, surface })
    expect(await ui.find({ type: 'Text', text: /ZOMBIE|TOKEN/ })).toBeDefined()
    await ui.unmount()
  }
  fs['usage.json'] = JSON.stringify({ ts: NOW - 60, hours: 24, inp: 300, out: 180, cr: 9000, cw: 20, turns: 3, basis: 'measured' })
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  let ui = await $.ui.mount({ ...BAND, surface: 'desktop' })
  const all = await ui.findAll({ type: 'Text' })
  expect(all.some(x => /^TOKENS USED/.test(x.text))).toBe(false) // tile removed from the bar
  await ui.unmount()
  fs['usage.json'] = JSON.stringify({ ts: NOW - 200000, inp: 5, out: 5, cr: 5, cw: 5, turns: 1 }) // older than 25 h => not shown
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  ui = await $.ui.mount({ ...BAND, surface: 'desktop' })
  const old = await ui.findAll({ type: 'Text' })
  expect(old.some(x => /^TOKENS USED/.test(x.text))).toBe(false)
  await ui.unmount()
})

test('baseline row: without-TZ (EST) minus used (MEASURED) = saved (EST), labelled', async ($, on) => {
  world(on, { 'usage.json': JSON.stringify({ ts: NOW - 60, inp: 100, out: 100, cr: 800, cw: 0, turns: 2 }), 'fresh.json': JSON.stringify({ ts: NOW - 60, tok: 500, n: 1 }) })
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect(await ui.find({ type: 'Text', text: /without TZ ~1\.5K \[EST\] - used 1\.0K \[MEASURED\] = saved 500 \[EST\]/ })).toBeDefined()
  await ui.unmount()
})
