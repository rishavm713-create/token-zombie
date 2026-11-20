import { expect, mock, test } from 'claude-code/testing'

// Release checks: the four bar numbers follow their real sources on the 5 s poll, and
// what the Mod keeps in $.state outlives a second session.start (what a hot reload runs).

const BAND = {
  plugin: 'token-zombie',
  component: 'AbovePrompt',
  props: { hasSurvey: false, isCollapsed: false, isWorking: false, maxRows: 20, bodyColumns: 120, scroll: { offset: 0, bodyRows: 20 }, view: {} },
} as const

const PANE = {
  plugin: 'token-zombie',
  component: 'Pane',
  requestId: 'token-zombie',
  props: { title: 'TOKEN ZOMBIE', isFocused: false, bodyColumns: 60, placement: 'dock', scroll: { offset: 0, bodyRows: 30 }, view: {} },
} as const

const NOW = 1_800_000_000_000

type W = { files: Record<string, string>; agents: number; skills: string[]; writes: Record<string, string> }
const world = (on: any, w: W) => {
  on('env.get', () => ({ value: '/h' }))
  on('command.register', () => ({ value: { command: 'tz' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.status', () => ({ value: undefined }))
  on('session.start', (_: any, e: any) => ({ cwd: e.cwd }))
  on('agent.list', () => ({ value: Array.from({ length: w.agents }, (_, i) => ({ id: `a${i}`, status: 'running' })) }))
  on('session.id', () => ({ value: 's1' }))
  on('fs.read', (_: any, e: any) => {
    const name = e.path.split('/').pop()!
    const f = name === 'live-s1.json' && w.skills.length ? JSON.stringify({ skills: { invoked: Object.fromEntries(w.skills.map(n => [n, 1])) } }) : w.files[name]
    return f === undefined ? { deny: 'ENOENT' } : { value: f }
  })
  on('fs.write', (_: any, e: any) => {
    w.writes[e.path] = String(e.data ?? e.text ?? e.content ?? '')
    return { value: undefined }
  })
}

const led = (n: number) => JSON.stringify(Array.from({ length: n }, (_, i) => ({ t: NOW / 1000 - 10, kind: 'filter', tok: 100, basis: 'measured' })))

test('bar numbers follow agent.list, skills invoked this session and ledger.json on the poll', async ($, on) => {
  const clock = mock.clock(on, { now: NOW })
  const w: W = { files: { 'ledger.json': led(1) }, agents: 1, skills: ['a'], writes: {} }
  world(on, w)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount({ ...BAND, surface: 'desktop' })
  const val = async (label: RegExp) => {
    const all = await ui.findAll({ type: 'Text' })
    return all[all.findIndex(x => label.test(x.text)) - 1]?.text
  }
  expect(await val(/^AGENTS$/)).toBe('1')
  expect(await val(/^SKILLS USED$/)).toBe('1')
  expect(await val(/^TOKENS SAVED · EST$/)).toBe('100')
  expect(await val(/^OPTIMIZATIONS$/)).toBe('1')
  expect(JSON.parse(w.writes['/h/.claude/token-zombie/agents.json']!).running).toBe(1)

  // sources change; the next poll picks them up
  w.agents = 4
  w.skills = ['a', 'b', 'c']
  w.files['ledger.json'] = led(3)
  await clock.advance(61_000)
  expect(await val(/^AGENTS$/)).toBe('4')
  expect(await val(/^SKILLS USED$/)).toBe('3')
  expect(await val(/^TOKENS SAVED · EST$/)).toBe('300')
  expect(await val(/^OPTIMIZATIONS$/)).toBe('3')
  expect(JSON.parse(w.writes['/h/.claude/token-zombie/agents.json']!).running).toBe(4)
  await ui.unmount()
})

test('pane totals in $.state survive a second session.start (hot reload)', async ($, on) => {
  mock.clock(on, { now: NOW })
  world(on, { files: {}, agents: 0, skills: [], writes: {} })
  on('turn.complete', (_: any, e: any) => ({ text: e.answer }))
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  const usage = { input_tokens: 1234, output_tokens: 56, cache_read_input_tokens: 0, cache_creation_input_tokens: 0, model: 'm' }
  await $.turn.complete({ answer: '', durationMs: 1000, isAborted: false, turnId: 't1', usage, reason: 'end_turn' } as any)
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /1\.2k/ })).toBeDefined()
  await ui.unmount()
})

test('a value stored under an older shape tag is declined, not misread', async ($, on) => {
  mock.clock(on, { now: NOW })
  world(on, { files: {}, agents: 0, skills: [], writes: {} })
  on('state.get', () => ({ value: { value: { shape: 'stats-0', value: { inp: 'bad' } }, version: 1 } }))
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /TOKEN ZOMBIE/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /bad/ })).toBeUndefined()
  await ui.unmount()
})
