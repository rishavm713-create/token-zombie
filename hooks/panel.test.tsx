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
  if (o.skills) {
    on('fs.list', () => ({ value: [...o.skills!.map(name => ({ name, kind: 'dir' })), { name: 'README.md', kind: 'file' }] }))
    on('fs.exists', (_: any, e: any) => ({ value: !e.path.includes('/nope/') }))
  }
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
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })

  await ui.press({ plugin: 'token-zombie', key: 'mode-ultra' })
  const last = () => ran[ran.length - 1]!
  expect(last().slice(0, 1)).toEqual(['python3'])
  expect(last().slice(-2)).toEqual(['mode', 'ultra'])
  expect(last()[1]).toMatch(/bin\/tz$/)

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
  { t: 1, kind: 'overhead-hook', tok: 20, basis: 'measured' },
])

test('slim bar: one row on terminal, no feed, unknowns as dashes', async ($, on) => {
  world(on, {})
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^TOKEN ZOMBIE$/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /^FULL$/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /— agents/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /— skills/ })).toBeDefined()
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
  expect((await val(/^AGENTS$/))?.text).toBe('3')
  expect((await val(/^SKILLS$/))?.text).toBe('2')
  const saved = await val(/^TOKENS SAVED · EST$/)
  expect(saved?.text).toBe('480')
  expect(saved?.props.color).toBe('green')
  expect((await val(/^OPTIMIZATIONS$/))?.text).toBe('1')
  expect(await ui.find({ type: 'Text', text: /^ULTRA$/ })).toBeDefined()
  const svg = await ui.find({ type: 'Svg' })
  expect(svg?.props.source).toBe('<svg>excited</svg>')
  expect(svg?.props.alt).toMatch(/mascot: excited/)
  expect(await ui.find({ type: 'Text', text: /recent|none yet/ })).toBeUndefined()
  await ui.press({ plugin: 'token-zombie', key: 'tz-expand' })
  expect(opened).toEqual(['token-zombie'])
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
