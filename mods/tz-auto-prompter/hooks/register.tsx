import type { Register } from 'claude-code'

// /queue add <text> | list | clear | pause | go. After each finished turn the next queued prompt is submitted.
let paused = false
export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'queue', description: '/queue add <prompt> | list | clear | pause | go' })
    return next(e)
  })
  on('command.run', { command: 'queue' }, async ($, e) => {
    const q = ((await $.store.get('queue')) as string[] | undefined) ?? []
    const [w, ...r] = e.args.trim().split(/\s+/)
    if (w === 'add' && r.length) { await $.store.set('queue', [...q, r.join(' ')].slice(-50)); return { text: `Queued (${q.length + 1}).` } }
    if (w === 'clear') { await $.store.delete('queue'); return { text: 'Queue cleared.' } }
    if (w === 'pause') { paused = true; return { text: 'Paused.' } }
    if (w === 'go') { paused = false; return { text: 'Running queue after each turn.' } }
    return { text: q.length ? q.map((t, i) => `${i + 1}. ${t}`).join('\n') : 'Queue empty. /queue add <prompt>' }
  })
  on('turn.complete', async ($, e, next) => {
    const r = await next(e)
    if (!paused && e.reason === 'answer') {
      const q = ((await $.store.get('queue')) as string[] | undefined) ?? []
      if (q.length) {
        await $.store.set('queue', q.slice(1))
        void $.prompt.submit({ text: q[0] })
      }
    }
    return r
  })
}
