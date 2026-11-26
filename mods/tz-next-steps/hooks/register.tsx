import type { Register } from 'claude-code'

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'next', description: '/next: three useful next actions' })
    return next(e)
  })
  on('command.run', { command: 'next' }, async () => ({
    text: 'Asking Claude for next steps.',
    context: ['Suggest exactly three useful next actions based on the work so far, one line each, numbered. No other text.'],
    isTextDisplayOnly: true,
  }))
}
