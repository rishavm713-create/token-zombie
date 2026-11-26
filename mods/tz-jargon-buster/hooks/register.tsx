import type { Register } from 'claude-code'

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'jargon', description: '/jargon <term or text>: explain in plain words' })
    return next(e)
  })
  on('command.run', { command: 'jargon' }, async ($, e) => {
    const t = e.args.trim()
    if (!t) return { text: 'Usage: /jargon <term or text>' }
    const r = await $.model.complete({ model: 'haiku', prompt: `Explain in plain English for a non-expert, max 60 words, no jargon, one example if it helps:\n${t}` })
    return { text: r.isAnswered ? r.text : `Failed: ${r.reason}`, isTextDisplayOnly: true }
  })
}
