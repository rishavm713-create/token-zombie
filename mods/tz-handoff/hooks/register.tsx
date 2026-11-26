import type { Register } from 'claude-code'

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'handoff-note', description: '/handoff-note: write handoffs/YYYY-MM-DD.md (done/left/next)' })
    return next(e)
  })
  on('command.run', { command: 'handoff-note' }, async () => ({
    text: 'Asking Claude to write the handoff.',
    context: ['Write <project>/handoffs/YYYY-MM-DD.md (today) with Done / Left / Next, at most 30 lines. Then say the path only.'],
    isTextDisplayOnly: true,
  }))
}
