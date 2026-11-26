import type { Register } from 'claude-code'

// /idea <text> parks an idea; /idea list; /idea send <n> prints it to paste; /idea drop <n>; /idea clear.
// Stored per project folder in $.store (survives closing). No model call, no always-on drawing.
export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'idea',
      description: 'Park an idea for later: /idea <text> | list | send <n> | drop <n> | clear',
    })
    return next(e)
  })

  on('command.run', { command: 'idea' }, async ($, e) => {
    const dir = (await $.env.get('PWD')) ?? 'default'
    const key = `ideas:${dir}`
    const list = ((await $.store.get(key)) as string[] | undefined) ?? []
    const [word, ...rest] = e.args.trim().split(/\s+/)
    const n = Number(rest[0]) - 1
    if (e.args.trim() === '' || word === 'list') {
      return { text: list.length ? list.map((t, i) => `${i + 1}. ${t}`).join('\n') : 'No parked ideas.' }
    }
    if (word === 'clear') {
      await $.store.delete(key)
      return { text: 'Ideas cleared.' }
    }
    if (word === 'send' || word === 'drop') {
      if (!(n >= 0 && n < list.length)) return { text: 'No such idea number.' }
      if (word === 'drop') {
        await $.store.set(key, list.filter((_, i) => i !== n))
        return { text: 'Dropped.' }
      }
      return { text: `Paste as your next prompt:\n${list[n]}` }
    }
    await $.store.set(key, [...list, e.args.trim()].slice(-100))
    return { text: `Parked idea ${list.length + 1}.` }
  })
}
