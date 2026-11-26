import type { Register } from 'claude-code'

// No timer: compares timestamps. Cache lives ~5 min (1 h on long TTL).
export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'cache', description: '/cache: time since last turn and cache state' })
    return next(e)
  })
  on('turn.complete', async ($, e, next) => { await $.store.set('lastTurn', Date.now()); return next(e) })
  on('prompt.submit', async ($, e, next) => {
    const last = (await $.store.get('lastTurn')) as number | undefined
    if (last && Date.now() - last > 300000) $.ui.toast(`Cache likely cold (${Math.round((Date.now() - last) / 60000)} min idle): next turn pays full price`)
    return next(e)
  })
  on('command.run', { command: 'cache' }, async $ => {
    const last = (await $.store.get('lastTurn')) as number | undefined
    if (!last) return { text: 'No turn recorded yet.' }
    const m = (Date.now() - last) / 60000
    return { text: `${m.toFixed(1)} min since last turn: ${m < 5 ? 'cache warm' : m < 60 ? 'cold on 5-min TTL, warm on 1-h TTL' : 'cold'}.`, isTextDisplayOnly: true }
  })
}
