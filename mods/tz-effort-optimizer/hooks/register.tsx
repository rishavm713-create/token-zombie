import type { Register } from 'claude-code'

// Keyword heuristic, no model call.
export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'effort-tip', description: '/effort-tip <task>: suggest an effort level' })
    return next(e)
  })
  on('command.run', { command: 'effort-tip' }, async (_$, e) => {
    const t = e.args.toLowerCase()
    if (!t.trim()) return { text: 'Usage: /effort-tip <task>' }
    const hard = /(architect|design|debug|race|security|refactor|migrate|multi-file|why)/.test(t)
    const easy = /(rename|typo|format|list|show|summar|translate|one line|comment)/.test(t)
    const lvl = hard ? 'high' : easy ? 'low' : 'medium'
    return { text: `Suggested effort: ${lvl}. Set it with the effort picker.`, isTextDisplayOnly: true }
  })
}
