import type { Register } from 'claude-code'

// Counts screenshot-type tool calls; warns, never blocks.
export const register: Register = on => {
  let n = 0
  on('tool.call', async ($, e, next) => {
    if (/computer|screenshot/i.test(String(e.tool))) {
      n++
      if (n === 3 || (n > 3 && n % 5 === 0)) $.ui.toast(`${n} screenshots this session: prefer read_page / get_page_text`)
    }
    return next(e)
  })
}
