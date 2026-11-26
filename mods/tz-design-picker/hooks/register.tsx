import type { Register } from 'claude-code'

const STYLES: [string, string, string, string][] = [
  ['Minimal light', '#ffffff', '#111111', '600 28px Inter,sans-serif'],
  ['Dark neon', '#0b0b14', '#39ff88', '700 28px monospace'],
  ['Editorial serif', '#f6f1e7', '#2b2118', '700 30px Georgia,serif'],
  ['Brutalist', '#ffe600', '#000000', '900 30px Arial Black,sans-serif'],
  ['Soft pastel', '#fde8f0', '#5a3d6b', '600 28px Trebuchet MS,sans-serif'],
  ['Glass gradient', 'linear-gradient(135deg,#4f46e5,#ec4899)', '#ffffff', '700 28px Helvetica,sans-serif'],
  ['Corporate blue', '#eef3fb', '#12356b', '600 28px Segoe UI,sans-serif'],
  ['Retro terminal', '#001a00', '#33ff33', '400 26px Courier,monospace'],
]

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'design-picker', description: 'Write a page showing design styles you can pick by sight' })
    return next(e)
  })
  on('command.run', { command: 'design-picker' }, async $ => {
    const cards = STYLES.map(([n, bg, fg, font], i) =>
      `<div style="background:${bg};color:${fg};font:${font};padding:28px;border-radius:12px;min-height:110px">${i + 1}. ${n}<div style="font:400 13px sans-serif;margin-top:10px">Heading, body text and a button sample</div><span style="display:inline-block;margin-top:12px;padding:6px 14px;border:2px solid ${fg};font:600 13px sans-serif">Button</span></div>`).join('')
    const html = `<!doctype html><meta charset=utf-8><title>Design styles</title><body style="margin:24px;font-family:sans-serif"><h2>Pick a style, tell Claude its number</h2><div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px">${cards}</div>`
    const tmp = (await $.env.get('TMPDIR')) ?? '/tmp'
    const path = `${tmp.replace(/\/$/, '')}/design-picker.html`
    await $.fs.write(path, html)
    return { text: `Open this file, then tell Claude the number: ${path}` }
  })
}
