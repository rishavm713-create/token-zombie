import type { Register } from 'claude-code'

const RULES = 'Plain English: short common words, no jargon, short sentences. Put the answer first, then one closing summary and up to 3 next steps.'
// Off by default: adds nothing to the prompt until /plain on. No Haiku checker (extra cost).
export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'plain', description: '/plain on|off: plain-English reply rules' })
    if ((await $.store.get('plain')) === true) $.ui.status('plain-english on')
    return next(e)
  })
  on('command.run', { command: 'plain' }, async ($, e) => {
    const on_ = e.args.trim() === 'on'
    if (!on_ && e.args.trim() !== 'off') return { text: `Plain English is ${(await $.store.get('plain')) === true ? 'on' : 'off'}. Use /plain on or /plain off.` }
    await $.store.set('plain', on_)
    $.ui.status(on_ ? 'plain-english on' : undefined)
    return { text: `Plain English ${on_ ? 'on' : 'off'}.` }
  })
  on('prompt.compose', async ($, e, next) => {
    const r = await next(e)
    if ((await $.store.get('plain')) !== true) return r
    return { sections: [...r.sections, { id: 'tz-plain-english:rules', text: RULES, scope: 'session' as const }] }
  })
}
