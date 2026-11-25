import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'
import { PY } from './pycmd'
import { registerTools, startTools } from './tools'

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
const files = atom(FI, { sig: '', status: null, isStale: false, host: null, isHostFresh: false, mode: 'full', mood: null }, { shape: 'files-1' })
const acts = atom(AC, [], { shape: 'acts-1' })
const note = atom(NO, { label: '', lines: [], err: '' }, { shape: 'note-1' })
const BA = { plugin: 'token-zombie', key: 'bar' } as const
const bar = atom(BA, { sig: '', agents: null, skills: null, saved: 0, opts: 0, hasLedger: false, recentAt: 0 } as Bar, { shape: 'bar-1' })

let isPlaced = true // module copy of ui.open's answer; a reload resets it, harmless

const obj = (t: unknown): Record<string, unknown> | null => {
  try {
    const v = typeof t === 'string' ? JSON.parse(t) : t
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
    const sid = String(await $.session.id()).replace(/[^A-Za-z0-9-]/g, '').slice(0, 64) || 'x'
    await $.fs.write(`${d}/agents-${sid}.json`, JSON.stringify({ running, total: list.length, ts: Math.round(now), src: 'mods agent.list' }))
    return running
  } catch {
    return null /* host without agent.list: dashboard shows UNKNOWN */
  }
}

// SKILLS USED = skills the model invoked (Skill tool) in THIS session, from the hook ledger live-<session>.json (tzlive.py).
// Not skills on disk or enabled (`tz live skills` lists installed/enabled/discovered/loaded/invoked apart). No ledger yet => UNKNOWN.
async function countSkills($: any, d: string) {
  try {
    const v = JSON.parse(await $.fs.read(`${d}/live-${await $.session.id()}.json`))
    const inv = v?.skills?.invoked
    return inv && typeof inv === 'object' ? Object.keys(inv).length : null
  } catch {
    return null
  }
}

// Same rule as bin/tzdash.py metrics(): measured non-overhead cuts minus overhead (EST); opts = measured entries.
// Rolling last 24 h, all chats (owner 2026-11-22); same rule as bin/tzdash.py window().
function block(led: any[], now: number) {
  const start = now - 86400
  return led.filter(x => (num(x.t) ?? 0) >= start)
}

function ledger(t: string, now: number) {
  let l: unknown
  try {
    l = JSON.parse(t)
  } catch {
    l = null
  }
  const led = block((Array.isArray(l) ? l : []).filter((x: any) => x && typeof x === 'object' && num(x.tok) !== undefined) as any[], now)
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
    const [s, h, c, lg, md, fr, ec, hi, cp, cd] = await Promise.all([
      readOr($, `${d}/status.json`),
      readOr($, `${d}/host.json`),
      readOr($, `${d}/config.json`),
      readOr($, `${d}/ledger.json`),
      readOr($, `${d}/mood.json`),
      readOr($, `${d}/fresh.json`),
      readOr($, `${d}/econ.json`),
      readOr($, `${d}/history.json`),
      readOr($, `${d}/caps.jsonl`),
      readOr($, `${d}/coding.json`),
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
    const mj = obj(md)
    const mts = num(mj?.ts)
    const mood = mts !== undefined && typeof mj?.kind === 'string' ? { kind: mj.kind, ts: mts } : null
    const agents = await writeAgents($, d, now)
    const skills = await countSkills($, d)
    const fj = obj(fr)
    // fresh-chat counterfactual (EST, from measured contexts): written by tz stats / chat start; shown only if < 24 h old
    const fresh = fj && (num(fj.ts) ?? 0) >= now - 86400 && num(fj.tok) !== undefined ? { tok: num(fj.tok) as number, n: num(fj.n) ?? 0 } : null
    // session economics (EST, API-equivalent $): written by tz stats; shown only if < 1 h old
    const en = obj(obj(ec)?.now)
    const econ =
      en && now - (num(en.ts) ?? 0) <= 3600 && typeof en.best === 'string'
        ? { cont: num(en.continue) ?? 0, compact: num(en.compact) ?? 0, fresh: num(en.fresh) ?? 0, best: en.best }
        : null
    // 24h line: today's history.json entry (tz stats) + on/off events in caps.jsonl within 24 h
    const dt = new Date(now * 1000)
    const used = num(obj(obj(hi)?.[`${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`])?.used)
    const evs = cp.split('\n').filter(l => (num(obj(l)?.t) ?? 0) >= now - 86400).length
    const day = used === undefined && evs === 0 ? null : { used: used ?? 0, events: evs }
    // coding quality (MEASURED counts; pass/fail read from test output text): written by the hooks, shown only if < 24 h old
    const cj = obj(cd)
    const coding =
      cj && now - (num(cj.ts) ?? 0) <= 86400 && (num(cj.edits) ?? 0) > 0
        ? { edits: num(cj.edits) as number, runs: num(cj.runs) ?? 0, last: typeof cj.last === 'string' ? cj.last : 'none', unt: num(cj.unt) ?? 0 }
        : null
    const b = { agents, skills, ...ledger(lg, now), fresh, econ, day, coding }
    const bsig = JSON.stringify(b)
    if (bsig !== (await read($, bar)).sig) await update($, bar, () => ({ sig: bsig, ...b }))
    const sig = JSON.stringify([s, h, mode, isStale, isHostFresh, md])
    if (sig === (await read($, files)).sig) return
    await update($, files, () => ({ sig, status, isStale, host, isHostFresh, mode, mood }))
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
  const md = f.mood && now - f.mood.ts <= 120 ? f.mood.kind : '' // MOOD_TTL in bin/tzbus.py
  const h = new Date(now * 1000).getHours()
  if (s && ['CRITICAL', 'EXHAUSTED', 'APPROACHING LIMIT'].includes(String(s.level)) || s?.risk === 'high') return 'alert'
  if (['churn', 'fresh', 'compact'].includes(md)) return 'alert'
  if (s?.task_just_done || ['save', 'test'].includes(md) || (b.recentAt > 0 && now - b.recentAt <= 120)) return 'excited'
  if (isWorking || (b.agents ?? 0) > 0 || s?.activity === 'working') return 'working'
  if (!s || ts === undefined || now - ts > 1800 || h >= 23 || h < 6) return 'sleep' // long idle or night
  if (s.level === 'ELEVATED') return 'working'
  return s.level !== 'NORMAL' ? 'sleep' : 'idle'
}

const big = (n: number) => (Math.abs(n) >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : Math.abs(n) >= 1e4 ? Math.round(n / 1e3) + 'K' : Math.abs(n) >= 1e3 ? (n / 1e3).toFixed(1) + 'K' : String(n))
const svgs = new Map<string, string>() // asset text by state; a reload re-reads, harmless

async function mascot($: any, vs: string) {
  if (!svgs.has(vs)) svgs.set(vs, await readOr($, `${$.plugin.root}/assets/zombie-${vs}.svg`))
  return svgs.get(vs)!
}

export const register: Register = on => {
  registerTools(on)
  on('session.start', async ($, e, next) => {
    await startTools($)
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
    const nums: [string, string, string, boolean][] = [
      ['agents', b.agents === null ? '—' : String(b.agents), 'AGENTS', false],
      ['skills', b.skills === null ? '—' : String(b.skills), 'SKILLS USED', false],
      ['saved', b.hasLedger || b.fresh?.tok ? big(b.saved + (b.fresh?.tok ?? 0)) : '0', 'TOKENS SAVED', true],
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
    // owner: no gap between head and the border: drop the empty top 60 units of the 260x385 art, same height => zombie ~18% bigger
    const crop = src && src.replace('viewBox="0 0 260 385"', 'viewBox="0 60 260 325"')
    const nextMode = MODES[(MODES.indexOf(f.mode as (typeof MODES)[number]) + 1) % MODES.length]
    return (
      // owner-approved design (2026-11-21 preview "option 1"): zombie 68x101 absolute at the left, top on the border;
      // title + 4 numbers packed left; dot + mode button (press cycles off > lite > full > ultra); paddingBottom holds the feet
      <Box flexDirection="column" paddingBottom={2}>
        <Box
          borderStyle="round"
          borderColor={isOff ? 'gray' : MC}
          flexDirection="row"
          alignItems="center"
          justifyContent="flex-start"
          gap="md"
          paddingX="sm"
        >
          <Box width={10} flexShrink={0} />
          <Text weight="bold">
            TOKEN <Text weight="bold" color={G}>ZOMBIE</Text>
          </Text>
          {nums.map(([k, v, l, isG]) => (
            <Box key={`n-${k}`} flexDirection="column" alignItems="center" flexShrink={1}>
              <Text weight="semibold" tabular color={isG ? G : undefined}>
                {v}
              </Text>
              <Text size="caption" dimColor wrap="truncate-end">
                {l}
              </Text>
            </Box>
          ))}
          <Text color={dot}>●</Text>
          <Button
            key="tz-mode"
            label={mode}
            plain
            onPress={async () => {
              sfx($, nextMode)
              await $.process.run([...PY, `${$.plugin.root}/bin/tz`, 'mode', nextMode], { timeoutMs: 30000 }).catch(() => {})
              await poll($)
            }}
          >
            {mode}
          </Button>
        </Box>
        <Box key="tz-mascot" position="absolute" top={0} left={1}>
          {src ? <Svg source={crop} alt={`TOKEN ZOMBIE mascot: ${vs}`} width={81} height={101} /> : <Text>🧟</Text>}
        </Box>
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
    const fb = await read($, bar)
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
    const tz = (...args: string[]) => [...PY, `${$.plugin.root}/bin/tz`, ...args]
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
        <Box>
          {btn('act-checkpoint', 'checkpoint', async () => { await run('checkpoint', tz('checkpoint'), 4) })}
          {btn('act-verify', 'verify', async () => { await run('verify', tz('handoff', 'verify'), 6) })}
          {btn('act-ship', 'ship?', async () => { await run('ship', tz('handoff', 'status'), 6) })}
        </Box>
        {row('tokens', `in ${k(t.inp)}  out ${k(t.out)}  cache ${k(t.cr)}`, 'tok')}
        {row('model', t.model || 'n/a', 'model')}
        {row('agent', `${dur(t.ms)} / ${t.turns} turns, ${t.spawns} subagents`, 'agent')}
        {row('cost', hostCost, 'cost')}
        {row('saved', `${big(fb.saved)} measured + ${big(fb.fresh?.tok ?? 0)} fresh chats [EST input-eq], last 24h`, 'saved')}
        {fb.coding &&
          row(
            'coding',
            `${fb.coding.edits} code edits, ${fb.coding.runs} test runs, last test ${fb.coding.last}, ${fb.coding.unt} untested [MEASURED counts]`,
            'coding',
          )}
        {fb.econ &&
          row(
            'econ',
            `10 turns: stay $${fb.econ.cont.toFixed(2)} compact $${fb.econ.compact.toFixed(2)} fresh $${fb.econ.fresh.toFixed(2)} -> ${fb.econ.best} [EST]`,
            'econ',
          )}
        {fb.day && row('24h', `used ${big(fb.day.used)}, ${fb.day.events} on/off`, 'day')}
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
