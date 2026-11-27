import type { Register } from 'claude-code'

// Stores the last prompt + time per turn; /checkpoint prints it for pasting into a fresh chat.
export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'checkpoint', description: '/checkpoint: show the last task and time, ready to paste into a new chat' })
    return next(e)
  })
  on('prompt.submit', async ($, e, next) => {
    await $.store.set('last', { text: String((e as any).text ?? '').slice(0, 300), at: Date.now() })
    return next(e)
  })
  on('command.run', { command: 'checkpoint' }, async $ => {
    const l = (await $.store.get('last')) as { text: string; at: number } | undefined
    return { text: l ? `Resume: ${l.text}\n(at ${new Date(l.at).toLocaleString()})` : 'Nothing saved yet.' }
  })
}
