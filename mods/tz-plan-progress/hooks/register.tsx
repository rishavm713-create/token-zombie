import type { Register } from 'claude-code'

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'progress', description: '/progress: checklist of done / doing / left' })
    return next(e)
  })
  on('command.run', { command: 'progress' }, async () => ({
    text: 'Asking Claude for a checklist.',
    context: ['Reply with a checklist of this task: [x] done, [~] in progress, [ ] left. One line each, nothing else.'],
    isTextDisplayOnly: true,
  }))
}
