import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Act, Bar, Files, Note, Stats } from '../types'

const PANE = 'token-zombie'
const STALE_S = 600
const KEEP = 'current task, files changed, test results, next step'
const MODES = ['off', 'lite', 'full', 'ultra'] as const
// one colour per mode so each reads apart at a glance; off stays dim
const MODE_COLOR: Record<string, string | undefined> = { off: undefined, lite: '#5ad1ff', full: 'green', ultra: '#ff8a1f' }
const TAGLINE = 'MAKE EVERY SINGLE TOKEN COUNT.'
// sounds/mode-*.wav come from bin/tzsfx.py; never block or fail a mode switch on audio
const sfx = ($: any, m: string) => void $.audio.play({ asset: `sounds/mode-${m}.wav` }, { gain: 0.6 }).catch(() => {})

const ST = { plugin: 'token-zombie', key: 'stats' } as const
const FI = { plugin: 'token-zombie', key: 'files' } as const
const AC = { plugin: 'token-zombie', key: 'acts' } as const
const NO = { plugin: 'token-zombie', key: 'note' } as const
const stats = atom(ST, { inp: 0, out: 0, cr: 0, cw: 0, ms: 0, turns: 0, spawns: 0, model: '' }, { shape: 'stats-1' })
const files = atom(FI, { sig: '', status: null, isStale: false, host: null, isHostFresh: false, mode: 'full' }, { shape: 'files-1' })
const acts = atom(AC, [], { shape: 'acts-1' })
const note = atom(NO, { label: '', lines: [], err: '' }, { shape: 'note-1' })
const BA = { plugin: 'token-zombie', key: 'bar' } as const
const bar = atom(BA, { sig: '', agents: null, skills: null, saved: 0, opts: 0, hasLedger: false, recentAt: 0 } as Bar, { shape: 'bar-1' })

let isPlaced = true // module copy of ui.open's answer; a reload resets it, harmless

const obj = (t: string): Record<string, unknown> | null => {
  try {
    const v = JSON.parse(t)
    return v && typeof v === 'object' && !Array.isArray(v) ? v : null
  } catch {
    return null
  }
}
const num = (v: unknown) => (typeof v === 'number' && isFinite(v) ? v : undefined)
const k = (n: number) => (n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? (n / 1e3).toFixed(1) + 'k' : String(n))
const dur = (ms: number) => (ms >= 60000 ? Math.floor(ms / 60000) + 'm' + Math.round((ms % 60000) / 1000) + 's' : Math.round(ms / 1000) + 's')
const oneLine = (e: unknown) => String((e as Error)?.message ?? e).split('\n')[0]!.slice(0, 120)

const readOr = async ($: any, p: string) => {
  try {
    return await $.fs.read(p)
  } catch {
    return ''
  }
}

// Read the three state files; write the atom only when their content (or staleness) changed.
// Real running-subagent count for the HTML dashboard (it cannot see the host): $.agent.list(), written only on change.
let lastAgents = ''
let lastAgentsAt = 0
async function writeAgents($: any, d: string, now: number): Promise<number | null> {
  try {
    const list: any[] = await $.agent.list()
    const running = list.filter(a => a && a.status === 'running').length
    // rewrite on change, else once a minute so the dashboard can tell fresh from stale
    if (String(running) === lastAgents && now - lastAgentsAt < 60) return running
    lastAgents = String(running)
    lastAgentsAt = now
    await $.fs.write(`${d}/agents.json`, JSON.stringify({ running, total: list.length, ts: Math.round(now), src: 'mods agent.list' }))
    return running
  } catch {
    return null /* host without agent.list: dashboard shows UNKNOWN */
  }
}

// SKILLS ON = ~/.claude/skills/*/SKILL.md on disk (installed + on, not invocations); listed at most once a minute.
let skillsN: number | null = null
let skillsAt = -1e9
async function countSkills($: any, home: string, now: number) {
  if (now - skillsAt < 60) return skillsN
  skillsAt = now
  try {
    const dir = `${home}/.claude/skills`
    const ents: any[] = await $.fs.list(dir)
    const has = await Promise.all(ents.filter(x => x.kind !== 'file').map(x => $.fs.exists(`${dir}/${x.name}/SKILL.md`).catch(() => false)))
    skillsN = has.filter(Boolean).length
  } catch {
    skillsN = null
  }
  return skillsN
}

// Same rule as bin/tzdash.py metrics(): measured non-overhead cuts minus overhead (EST); opts = measured entries.
function ledger(t: string) {
  let l: unknown
  try {
    l = JSON.parse(t)
  } catch {
    l = null
  }
  const led = (Array.isArray(l) ? l : []).filter((x: any) => x && typeof x === 'object' && num(x.tok) !== undefined) as any[]
  const isOver = (x: any) => String(x.kind ?? '').startsWith('overhead')
  const done = led.filter(x => x.basis === 'measured' && !isOver(x))
  const over = led.filter(isOver).reduce((a, x) => a + x.tok, 0)
  const lastAt = Math.max(0, ...done.filter(x => x.tok > 0).map(x => num(x.t) ?? 0))
  return { saved: done.reduce((a, x) => a + x.tok, 0) - over, opts: done.length, hasLedger: led.length > 0, recentAt: lastAt }
}

async function poll($: any) {
  try {
    const home = await $.env.get('HOME')
    if (!home) return
    const d = `${home}/.claude/token-zombie`
    const [s, h, c, lg] = await Promise.all([
      readOr($, `${d}/status.json`),
      readOr($, `${d}/host.json`),
      readOr($, `${d}/config.json`),
      readOr($, `${d}/ledger.json`),
    ])
    const now = (await $.clock.now()) / 1000
    const status = obj(s)
    const ts = num(status?.ts)
    const isStale = ts === undefined || now - ts > STALE_S
    const hj = obj(h)
    const cost = num(hj?.cost_usd)
    const hts = num(hj?.ts) ?? 0
    const host = cost === undefined ? null : { cost_usd: cost, ts: hts, session: typeof hj?.session === 'string' ? hj.session : undefined }
    const isHostFresh = host !== null && now - hts <= STALE_S
    const m = obj(c)?.mode
    const mode = typeof m === 'string' && m ? m : 'full'
    const agents = await writeAgents($, d, now)
    const skills = await countSkills($, home, now)
    const b = { agents, skills, ...ledger(lg) }
    const bsig = JSON.stringify(b)
    if (bsig !== (await read($, bar)).sig) await update($, bar, () => ({ sig: bsig, ...b }))
    const sig = JSON.stringify([s, h, mode, isStale, isHostFresh])
    if (sig === (await read($, files)).sig) return
    await update($, files, () => ({ sig, status, isStale, host, isHostFresh, mode }))
    if (!isPlaced) void $.ui.status(await oneliner($))
  } catch {
    /* a poll never breaks the session */
  }
}

const ctx = (f: Files) => {
  const s = f.status
  if (!s) return 'no data'
  return `${num(s.ctx_pct) ?? '?'}% ${String(s.level ?? '')}`.trim() + (f.isStale ? ' (stale)' : '')
}

async function oneliner($: any) {
  const f = await read($, files)
  const t = await read($, stats)
  return `TZ ${f.mode} ctx ${ctx(f)} in ${k(t.inp)} out ${k(t.out)}`
}

// Plain-text copy of exactly what the panel shows.
async function summary($: any) {
  const f = await read($, files)
  const t = await read($, stats)
  const s = f.status
  const a = Array.isArray(s?.actions) ? (s!.actions as unknown[]).length : 0
  return [
    `TOKEN ZOMBIE mode ${f.mode}`,
    `tokens in ${t.inp} out ${t.out} cache read ${t.cr} write ${t.cw} (MEASURED, this session)`,
    `model ${t.model || 'n/a'}, agent time ${dur(t.ms)} over ${t.turns} turns, subagents ${t.spawns}`,
    `cost ${f.host && f.isHostFresh ? '$' + f.host.cost_usd.toFixed(2) + ' (host)' : 'n/a (statusline not wired)'}`,
    `context ${ctx(f)}`,
    s && !f.isStale
      ? `supervisor ${String(s.state ?? '?')} risk ${String(s.risk ?? '?')} activity ${String(s.activity ?? '?')} open_tasks ${num(s.open_tasks) ?? '?'} actions ${a}`
      : 'supervisor no data',
  ].join('\n')
}

async function open($: any) {
  const r = await $.ui.open({ id: PANE, title: 'TOKEN ZOMBIE' })
  isPlaced = r.isPlaced !== false
  await poll($)
  if (!isPlaced) void $.ui.status(await oneliner($))
}

// Mascot visual state: same order as bin/tzzombie.py visual_state() over bin/tzmascot.py mascot_state().
function visual(f: Files, b: Bar, isWorking: boolean, now: number) {
  const s = f.status
  const ts = num(s?.ts)
  if (s && ['CRITICAL', 'EXHAUSTED', 'APPROACHING LIMIT'].includes(String(s.level)) || s?.risk === 'high') return 'alert'
  if (s?.task_just_done || (b.recentAt > 0 && now - b.recentAt <= 120)) return 'excited'
  if (isWorking || (b.agents ?? 0) > 0 || s?.level === 'ELEVATED' || s?.activity === 'working') return 'working'
  if (!s || ts === undefined || now - ts > 1800 || s.level !== 'NORMAL') return 'sleep'
  return 'idle'
}

const big = (n: number) => (Math.abs(n) >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : Math.abs(n) >= 1e4 ? Math.round(n / 1e3) + 'K' : Math.abs(n) >= 1e3 ? (n / 1e3).toFixed(1) + 'K' : String(n))
const svgs = new Map<string, string>() // asset text by state; a reload re-reads, harmless

async function mascot($: any, vs: string) {
  if (!svgs.has(vs)) svgs.set(vs, await readOr($, `${$.plugin.root}/assets/zombie-${vs}.svg`))
  return svgs.get(vs)!
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    try {
      await $.command.register({ name: 'tz', description: 'Open the TOKEN ZOMBIE pane' })
      $.clock.every(5000, () => void poll($))
      await poll($)
    } catch {
      /* keep the session going */
    }
    return next(e)
  })

  on('command.run', { command: 'tz' }, async $ => {
    await open($)
    return { text: isPlaced ? 'TOKEN ZOMBIE pane opened.' : 'No pane here; status line set instead.' }
  })

  on('turn.complete', async ($, e, next) => {
    const u = e.usage
    if (u && !e.agentId) {
      await update($, stats, s => ({
        ...s,
        inp: s.inp + u.input_tokens,
        out: s.out + u.output_tokens,
        cr: s.cr + u.cache_read_input_tokens,
        cw: s.cw + u.cache_creation_input_tokens,
        ms: s.ms + e.durationMs,
        turns: s.turns + 1,
        model: u.model || s.model,
      }))
    }
    return next(e)
  })

  on('agent.spawn', async ($, e, next) => {
    try {
      await update($, stats, s => ({ ...s, spawns: s.spawns + 1 }))
      const a: Act = { id: e.tool_use_id, tool: `agent ${e.subagentType}`, isDone: false }
      await update($, acts, l => [...l, a].slice(-20))
    } catch {
      /* never block a spawn */
    }
    return next(e)
  }).catch(($, e, next) => next(e))

  on('tool.call', async ($, e, next) => {
    const a: Act = { id: e.tool_use_id, tool: e.tool, isDone: false }
    try {
      await update($, acts, l => [...l, a].slice(-20))
    } catch {
      /* never block a tool */
    }
    const ran = await next(e)
    try {
      await update($, acts, l => l.map(x => (x.id === a.id ? { ...x, isDone: true } : x)))
    } catch {
      /* ignore */
    }
    return ran
  }).catch(($, e, next) => next(e))

  // Default view: one slim bar above the prompt. The chevron opens the detailed pane (same as /tz).
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) return next(e)
    const { Box, Text, Button } = $.ui.resolve(e)
    const f = await read($, files)
    const b = await read($, bar)
    const now = (await $.clock.now()) / 1000
    const vs = visual(f, b, e.props.isWorking, now)
    const G = 'green'
    const mode = f.mode.toUpperCase()
    const isOff = f.mode === 'off'
    const MC = MODE_COLOR[f.mode] ?? G
    const dot = vs === 'alert' ? 'yellow' : isOff || f.isStale ? 'gray' : G
    const state = vs === 'alert' ? 'Alert' : isOff ? 'Off' : f.isStale ? 'Stale' : 'Active'
    const nums: [string, string, string, boolean][] = [
      ['agents', b.agents === null ? '—' : String(b.agents), 'AGENTS', false],
      ['skills', b.skills === null ? '—' : String(b.skills), 'SKILLS ON', false],
      ['saved', b.hasLedger ? big(b.saved) : '0', 'TOKENS SAVED · EST', true],
      ['opts', String(b.opts), 'OPTIMIZATIONS', false],
    ]
    const expand = (
      <Button key="tz-expand" label="Open TOKEN ZOMBIE details" plain onPress={() => void open($)}>
        ⌄
      </Button>
    )

    if (e.surface === 'terminal') {
      // shortcut: the terminal band has no Svg; Image would need a PNG raster of the mascot. Emoji stands in.
      return (
        <Box flexDirection="row" gap={1}>
          <Text>🧟</Text>
          <Text bold>
            TOKEN <Text color={G}>ZOMBIE</Text>
          </Text>
          <Text bold color={isOff ? undefined : MC} dimColor={isOff}>{mode}</Text>
          {nums.map(([k, v, l, isG]) => (
            <Text key={`t-${k}`}>
              <Text bold color={isG ? G : undefined}>{v}</Text>
              <Text dimColor> {l.toLowerCase()}</Text>
            </Text>
          ))}
          <Text color={dot}>●</Text>
          {expand}
        </Box>
      )
    }

    const { Svg } = $.ui.resolve(e)
    const src = await mascot($, vs)
    return (
      // 2 cells above the bar hold the head; assets/zombie-*.svg puts the grip line 38px down (~2 cells), on the border
      <Box flexDirection="column" paddingTop={2}>
        <Box
          borderStyle="round"
          borderColor={isOff ? 'gray' : MC}
          flexDirection="row"
          alignItems="center"
          justifyContent="space-between"
          gap="md"
          paddingX="sm"
        >
          <Box flexDirection="row" alignItems="center" gap="sm" flexShrink={0}>
            <Box width={6} />
            <Box flexDirection="column">
              <Text weight="bold">
                TOKEN <Text weight="bold" color={G}>ZOMBIE</Text>
              </Text>
              <Text size="caption" weight="bold" wrap="truncate-end">
                {TAGLINE}
              </Text>
            </Box>
            <Text size="caption" weight="bold" color={isOff ? undefined : MC} dimColor={isOff}>
              {mode}
            </Text>
          </Box>
          {nums.map(([k, v, l, isG]) => (
            <Box key={`n-${k}`} flexDirection="column" flexShrink={1}>
              <Text weight="semibold" tabular color={isG ? G : undefined}>
                {v}
              </Text>
              <Text size="caption" dimColor wrap="truncate-end">
                {l}
              </Text>
            </Box>
          ))}
          <Box flexDirection="row" alignItems="center" gap="sm" flexShrink={0}>
            <Text color={dot}>●</Text>
            <Text size="caption" dimColor>{state}</Text>
            {expand}
          </Box>
        </Box>
        {src ? (
          <Box key="tz-mascot" position="absolute" top={0} left={1}>
            <Svg source={src} alt={`TOKEN ZOMBIE mascot: ${vs}`} width={42} height={62} />
          </Box>
        ) : (
          <Box key="tz-mascot" position="absolute" top={2} left={1}>
            <Text>🧟</Text>
          </Box>
        )}
      </Box>
    )
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button } = $.ui.resolve(e)
    const f = await read($, files)
    const t = await read($, stats)
    const list = (await read($, acts)).slice(-5)
    const n = await read($, note)
    const s = f.status
    const A = 'green'
    const row = (label: string, value: string, key: string) => (
      <Box key={key}>
        <Text dimColor>{label.padEnd(9)}</Text>
        <Text>{value}</Text>
      </Box>
    )
    const hostCost = f.host && f.isHostFresh ? `$${f.host.cost_usd.toFixed(2)} (host)` : 'n/a (statusline not wired)'
    const fresh = s && !f.isStale
    const run = async (label: string, argv: string[], keepLines = 12) => {
      try {
        const r = await $.process.run(argv, { timeoutMs: 30000 })
        const out = (r.stdout.trim() || r.stderr.trim()).split('\n').slice(0, keepLines)
        await update($, note, () => ({ label, lines: out, err: r.exitCode ? `exit ${r.exitCode}` : '' }))
      } catch (x) {
        await update($, note, () => ({ label, lines: [], err: oneLine(x) }))
      }
    }
    const tz = (...args: string[]) => ['python3', `${$.plugin.root}/bin/tz`, ...args]
    const btn = (key: string, label: string, onPress: () => Promise<void>) => (
      <Button key={key} onPress={onPress}>
        {label}
      </Button>
    )

    return (
      <Box flexDirection="column">
        <Box>
          <Text bold>
            TOKEN <Text color={A}>ZOMBIE</Text>
          </Text>
          <Text dimColor>  mode </Text>
          <Text bold color={MODE_COLOR[f.mode]} dimColor={f.mode === 'off'}>{f.mode}</Text>
        </Box>
        <Text bold>{TAGLINE}</Text>
        <Box>
          {MODES.map(m =>
            btn(`mode-${m}`, f.mode === m ? `[${m}]` : m, async () => {
              sfx($, m)
              await run(`mode ${m}`, tz('mode', m), 6)
              await poll($)
            }),
          )}
        </Box>
        {row('tokens', `in ${k(t.inp)}  out ${k(t.out)}  cache ${k(t.cr)}`, 'tok')}
        {row('model', t.model || 'n/a', 'model')}
        {row('agent', `${dur(t.ms)} / ${t.turns} turns, ${t.spawns} subagents`, 'agent')}
        {row('cost', hostCost, 'cost')}
        {row('context', ctx(f), 'ctx')}
        {row(
          'super',
          fresh ? `${String(s.state ?? '?')} risk ${String(s.risk ?? '?')} ${String(s.activity ?? '')}`.trim() : 'no data',
          'sup',
        )}
        {fresh &&
          row(
            'tasks',
            `${num(s.open_tasks) ?? '?'} open, ${Array.isArray(s.actions) ? s.actions.length : 0} actions`,
            'tasks',
          )}
        <Text dimColor>recent</Text>
        {list.length === 0 && <Text dimColor>none yet</Text>}
        {list.map(a => (
          <Text key={`a-${a.id}`} dimColor={a.isDone}>
            {a.isDone ? 'done' : 'runs'} {a.tool}
          </Text>
        ))}
        <Box>
          {btn('copy', 'Copy', async () => {
            const r = await $.ui.copy({ text: await summary($), surface: e.surface })
            await update($, note, () => ({ label: 'copy', lines: [], err: r.isCopied ? '' : 'copy refused here' }))
          })}
          {btn('review', 'Review', () => run('review', tz('optimize')))}
          {btn('audit', 'Audit', () => run('audit', tz('audit')))}
          {btn('board', 'Board', async () => {
            const home = (await $.env.get('HOME')) ?? ''
            const out = `${home}/.claude/token-zombie/board.html`
            await run('board', tz('dash', '--out', out), 3)
            const cur = await read($, note)
            if (!cur.err) await update($, note, () => ({ ...cur, lines: [`board written: ${out}`, 'open it in a browser'] }))
          })}
          {btn('compact', 'Compact', async () => {
            await run('compact', tz('checkpoint'), 3)
            const typed = `/compact ${KEEP}`
            try {
              await $.command.run({ command: 'compact', args: KEEP })
              await update($, note, () => ({ label: 'compact', lines: ['compact requested', `if nothing happens, type: ${typed}`], err: '' }))
            } catch (x) {
              await update($, note, () => ({ label: 'compact', lines: [`type: ${typed}`], err: oneLine(x) }))
            }
          })}
        </Box>
        {(n.label || n.err) && (
          <Box flexDirection="column">
            <Text color={A}>{n.label}</Text>
            {n.lines.map((l, i) => (
              <Text key={`n-${i}`} dimColor>{l}</Text>
            ))}
            {n.err && <Text dimColor>{n.err}</Text>}
          </Box>
        )}
      </Box>
    )
  })
}
