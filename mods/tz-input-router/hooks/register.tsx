import type { Register } from 'claude-code'
// One Haiku call, only when /route is used.
export const register: Register = on => {
  on('session.start', async ($, e, next) => { await $.command.register({ name: 'route', description: '/route <task>: suggest model, effort and skill pack' }); return next(e) })
  on('command.run', { command: 'route' }, async ($, e) => {
    const t = e.args.trim()
    if (!t) return { text: 'Usage: /route <task>' }
    const r = await $.model.complete({ model: 'haiku', prompt: `Task: ${t}\nReply in 3 short lines: Model (haiku/sonnet/opus), Effort (low/medium/high), Skill pack (video, sound, motion, design, content, book, coding, none). Cheapest that still gives equal quality.` })
    return { text: r.isAnswered ? r.text : `Failed: ${r.reason}`, isTextDisplayOnly: true }
  })
}
