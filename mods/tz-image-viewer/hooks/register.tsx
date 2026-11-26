import type { Register } from 'claude-code'

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'image', description: '/image <path>: open an image in the system viewer' })
    return next(e)
  })
  on('command.run', { command: 'image' }, async ($, e) => {
    const p = e.args.trim()
    if (!/^[\w./~ -]+\.(png|jpe?g|gif|webp|svg)$/i.test(p)) return { text: 'Usage: /image <path to png/jpg/gif/webp/svg>' }
    const r = await $.process.run(['open', p], { timeoutMs: 5000 }).catch(() => null)
    return { text: r ? `Opened ${p}` : 'Could not open it.' }
  })
}
