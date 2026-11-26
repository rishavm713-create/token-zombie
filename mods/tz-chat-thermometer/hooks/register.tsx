import type { Register } from 'claude-code'

// Chat size from the last turn's input-side tokens, at the owner's 100k / 175k rule. Never calls a model.
export const register: Register = on => {
  on('turn.complete', async ($, e, next) => {
    const u = e.usage
    if (u) {
      const k = Math.round(((u.input_tokens ?? 0) + (u.cache_read_input_tokens ?? 0) + (u.cache_creation_input_tokens ?? 0)) / 1000)
      const w = k >= 175 ? 'HOT stop' : k >= 100 ? 'hot, hand off' : k >= 60 ? 'warm' : 'cool'
      $.ui.status(`chat ${k}k ${w}`)
      if (k >= 100 && k < 110) $.ui.toast(`Chat is ${k}k tokens: finish the task, then /compact or a fresh chat`)
    }
    return next(e)
  })
}
