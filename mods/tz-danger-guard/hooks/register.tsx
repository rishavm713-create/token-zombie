import type { Register } from 'claude-code'

// Safe defaults for unattended runs. /danger off pauses it for this repo.
const BAD: [RegExp, string][] = [
  [/\brm\s+-[a-z]*r[a-z]*f?[a-z]*\s+(\/|~|\$HOME)(\s|$)/, 'rm -rf on root/home'],
  [/git\s+push\b[^|;&]*(--force\b|-f\b)/, 'force push'],
  [/git\s+reset\s+--hard\s+origin/, 'hard reset to origin'],
  [/\bdrop\s+(table|database)\b/i, 'DROP'],
  [/\bmkfs\b|\bdd\s+if=.*of=\/dev\//, 'disk wipe'],
]
export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'danger', description: '/danger off | on: pause or resume destructive-command blocking' })
    return next(e)
  })
  on('command.run', { command: 'danger' }, async ($, e) => {
    const off = e.args.trim() === 'off'
    await $.store.set('off', off)
    return { text: off ? 'Danger guard paused.' : 'Danger guard on.' }
  })
  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    if (await $.store.get('off')) return next(e)
    const cmd = String(e.command ?? '')
    for (const [r, why] of BAD) if (r.test(cmd)) return { deny: `Blocked by tz-danger-guard: ${why}. Use /danger off to allow.` }
    return next(e)
  })
}
