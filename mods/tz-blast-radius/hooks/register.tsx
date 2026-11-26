import type { Register } from 'claude-code'

// Warns (toast) on destructive commands; never blocks. Use tz-rule-enforcer to block.
const RISKY: [RegExp, string][] = [
  [/\brm\s+-[a-z]*r/i, 'recursive delete'],
  [/git\s+reset\s+--hard/, 'discards uncommitted changes'],
  [/git\s+push\s+.*(--force|-f\b)/, 'force push rewrites remote history'],
  [/git\s+clean\s+-[a-z]*f/, 'deletes untracked files'],
  [/\bdrop\s+(table|database)\b/i, 'drops data'],
  [/\bchmod\s+-R|\bchown\s+-R/, 'recursive permission change'],
]
export const register: Register = on => {
  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const cmd = String(e.command ?? '')
    const hit = RISKY.find(([re]) => re.test(cmd))
    if (hit) $.ui.toast(`Blast radius: ${hit[1]}`)
    return next(e)
  })
}
