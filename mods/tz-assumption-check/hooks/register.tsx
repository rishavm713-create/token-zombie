import type { Register } from 'claude-code'

// No always-on hook. /assumptions asks Claude to number its guesses; /assumptions wrong 2 4 sends those back.
export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'assumptions', description: 'List Claude\'s guesses; "/assumptions wrong 2 4" sends the wrong ones back' })
    return next(e)
  })
  on('command.run', { command: 'assumptions' }, async (_$, e) => {
    const m = e.args.trim().match(/^wrong\s+([\d\s,]+)$/i)
    const ask = m
      ? `Assumptions numbered ${m[1].trim().replace(/\s+/g, ', ')} from your list were WRONG. Redo the affected work without them and ask me if unsure.`
      : 'List the small assumptions you made so far in this task, numbered, one line each, nothing else.'
    return { text: m ? `Sent back: ${m[1].trim()}` : 'Asked Claude for its assumptions. Reply: /assumptions wrong 2 4', context: [ask], isTextDisplayOnly: true }
  })
}
