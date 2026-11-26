import type { Register } from 'claude-code'

const RULE = 'Fake data mode: in examples, fixtures, tests and demos use obviously fake data only (example.com, 555-01xx numbers, "Jane Doe", test keys). Never real personal data, real keys or the owner\'s details.'
export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'fake', description: '/fake on|off: placeholder-only data rule' })
    if ((await $.store.get('fake')) === true) $.ui.status('fake data on')
    return next(e)
  })
  on('command.run', { command: 'fake' }, async ($, e) => {
    const v = e.args.trim()
    if (v !== 'on' && v !== 'off') return { text: `Fake data mode is ${(await $.store.get('fake')) === true ? 'on' : 'off'}. /fake on|off` }
    await $.store.set('fake', v === 'on')
    $.ui.status(v === 'on' ? 'fake data on' : undefined)
    return { text: `Fake data mode ${v}.` }
  })
  on('prompt.compose', async ($, e, next) => {
    const r = await next(e)
    if ((await $.store.get('fake')) !== true) return r
    return { sections: [...r.sections, { id: 'tz-fake-data-mode:rule', text: RULE, scope: 'session' as const }] }
  })
}
