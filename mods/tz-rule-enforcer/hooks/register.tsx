import type { Register } from 'claude-code'

// /rule add <regex> | list | drop <n>. Bash commands matching any rule are refused. Enforced by the engine, not by asking the model.
export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'rule', description: '/rule add <regex> | list | drop <n>: block matching Bash commands' })
    return next(e)
  })
  on('command.run', { command: 'rule' }, async ($, e) => {
    const rules = ((await $.store.get('rules')) as string[] | undefined) ?? []
    const [w, ...r] = e.args.trim().split(/\s+/)
    if (w === 'add' && r.length) {
      const src = r.join(' ')
      try { new RegExp(src) } catch { return { text: 'Not a valid regex.' } }
      await $.store.set('rules', [...rules, src])
      return { text: `Rule ${rules.length + 1} added.` }
    }
    if (w === 'drop') { await $.store.set('rules', rules.filter((_, i) => i !== Number(r[0]) - 1)); return { text: 'Dropped.' } }
    return { text: rules.length ? rules.map((t, i) => `${i + 1}. ${t}`).join('\n') : 'No rules.' }
  })
  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const rules = ((await $.store.get('rules')) as string[] | undefined) ?? []
    const cmd = String((e.input as { command?: string }).command ?? '')
    for (const src of rules) {
      let hit = false
      try { hit = new RegExp(src).test(cmd) } catch {}
      if (hit) return { deny: `Blocked by rule /${src}/` }
    }
    return next(e)
  })
}
