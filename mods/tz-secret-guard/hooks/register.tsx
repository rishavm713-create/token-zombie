import type { Register } from 'claude-code'

// Refuses Bash commands that would expose secrets. Enforced by the engine, not the model.
const BAD = [
  /\bcat\s+[^|;&]*(\.env\b|id_rsa|id_ed25519|\.pem\b|credentials)/,
  /\b(printenv|env)\b[^|;&]*\|\s*(curl|nc|wget)/,
  /curl[^|;&]*(-d|--data)[^|;&]*(AKIA|sk-|ghp_|xox[bp]-)/,
  /(AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{30,})/,
]
export const register: Register = on => {
  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const cmd = String(e.command ?? '')
    if (BAD.some(r => r.test(cmd))) return { deny: 'Blocked by tz-secret-guard: command may expose a secret.' }
    return next(e)
  })
}
