import type { Register } from 'claude-code'

// Explore/search subagents run on Haiku unless they already name a model.
export const register: Register = on => {
  on('agent.spawn', async ($, e, next) => {
    if (e.subagentType === 'Explore' && !e.model) {
      try { return await next({ ...e, model: 'haiku' }) } catch {}
    }
    return next(e)
  })
}
