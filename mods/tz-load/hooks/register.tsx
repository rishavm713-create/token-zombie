import type { Register } from 'claude-code'

// Wraps the owner's existing ~/.claude/skillpack script. Only pack names [a-z0-9-] are passed through.
export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'load', description: '/load <pack> | off <pack> | list' })
    return next(e)
  })
  on('command.run', { command: 'load' }, async ($, e) => {
    const home = (await $.env.get('HOME')) ?? ''
    const [a, b] = e.args.trim().split(/\s+/)
    const ok = (s?: string) => !!s && /^[a-z0-9-]+$/.test(s)
    let args: string[]
    if (a === 'list' || !a) args = ['list']
    else if (a === 'off' && ok(b)) args = ['off', b!]
    else if (ok(a) && !b) args = ['on', a]
    else return { text: 'Usage: /load <pack> | /load off <pack> | /load list' }
    const r = await $.process.run([`${home}/.claude/skillpack`, ...args], { timeoutMs: 20000 }).catch(() => null)
    return { text: r ? String(r.stdout || r.stderr).trim().slice(0, 2000) || 'done' : 'skillpack failed', isTextDisplayOnly: true }
  })
}
