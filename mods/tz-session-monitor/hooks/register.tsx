import type { Register } from 'claude-code'

type S = { pid: number; sessionId: string; cwd: string; name?: string; status?: string; updatedAt: number }
async function load($: any): Promise<S[]> {
  const home = (await $.env.get("HOME")) ?? ""
  const dir = `${home}/.claude/sessions`
  const out: S[] = []
  try {
    for (const f of await $.fs.list(dir)) {
      if (!f.name.endsWith(".json")) continue
      try { out.push(JSON.parse(await $.fs.read(`${dir}/${f.name}`))) } catch {}
    }
  } catch {}
  if (!out.length) return out
  const ps = await $.process.run(["ps", "-o", "pid=", "-p", out.map(s => s.pid).join(",")], { timeoutMs: 5000 }).catch(() => null)
  const alive = new Set(String(ps?.stdout ?? "").split(/\s+/).filter(Boolean).map(Number))
  return out.filter(s => alive.has(s.pid))
}
const label = (s: S, now: number) => `${(s.status ?? "?").padEnd(8)} ${Math.round((now - s.updatedAt) / 60000)}m  ${s.name ?? s.sessionId.slice(0, 8)}  ${s.cwd}`

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'sessions', description: 'List running Claude Code sessions and their status' })
    return next(e)
  })
  on('command.run', { command: 'sessions' }, async $ => {
    const now = await $.clock.now()
    const list = (await load($)).sort((a, b) => b.updatedAt - a.updatedAt)
    return { text: list.length ? list.map(s => label(s, now)).join('\n') : 'No running sessions found.', isTextDisplayOnly: true }
  })
}
