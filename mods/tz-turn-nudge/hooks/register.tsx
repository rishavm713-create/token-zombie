import type { Register } from 'claude-code'

// Every 25 turns: toast to save a handoff and start fresh. /nudge N changes the step.
export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'nudge', description: '/nudge <turns>: remind to hand off every N turns (default 25)' })
    return next(e)
  })
  on('command.run', { command: 'nudge' }, async ($, e) => {
    const n = Number(e.args.trim())
    if (!n || n < 3) return { text: 'Usage: /nudge <turns> (3 or more).' }
    await $.store.set('step', n)
    return { text: `Reminder every ${n} turns.` }
  })
  on('turn.complete', async ($, e, next) => {
    const c = (((await $.store.get('count')) as number | undefined) ?? 0) + 1
    await $.store.set('count', c)
    const step = ((await $.store.get('step')) as number | undefined) ?? 25
    if (c % step === 0) $.ui.toast(`${c} turns: save a handoff and start a fresh chat soon`)
    return next(e)
  })
}
