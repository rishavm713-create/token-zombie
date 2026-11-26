import type { Register } from 'claude-code'
import { makeColors } from './make-colors.js'

const roles = { accent: '#2f5d8c', danger: '#b3392f', success: '#4e7d3a', warning: '#a86f14', pro: '#6d4f94' }
const gray = (s: string[], t: string[]) => ({ anchors: { 'surface-0': s[0], 'surface-1': s[1], 'surface-2': s[2], 'surface-3': s[3], 'text-primary': t[0], 'text-secondary': t[1], 'text-muted': t[2] } })
const THEMES: Record<string, () => ReturnType<typeof makeColors>> = {
  paper: () => makeColors({ label: 'Paper', roles, light: { gray: gray(['#efe6d3', '#f4ecdc', '#faf5e9', '#fffaf0'], ['#2a241d', '#544a3d', '#6a5f50']) }, dark: { gray: gray(['#1f1a15', '#28221b', '#312a22', '#3a3229'], ['#f0e7d7', '#cfc4b2', '#aca08d']) } }),
  midnight: () => makeColors({ label: 'Midnight', roles: { ...roles, accent: '#6ea8ff' }, light: { gray: gray(['#eef1f7', '#f4f6fb', '#fafbfe', '#ffffff'], ['#161b2b', '#3d465e', '#5a647d']) }, dark: { gray: gray(['#0e1220', '#151a2c', '#1c2238', '#242b45'], ['#e8ecf8', '#bcc4dc', '#99a2bd']) } }),
  forest: () => makeColors({ label: 'Forest', roles: { ...roles, accent: '#2f7d4f' }, light: { gray: gray(['#e9f0e6', '#f0f6ed', '#f6faf4', '#fcfffb'], ['#1b2a1f', '#3f5545', '#5a7060']) }, dark: { gray: gray(['#101a13', '#17231a', '#1e2c21', '#263628'], ['#e3f0e6', '#b7cdbb', '#93ac99']) } }),
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'skin', description: '/skin paper|midnight|forest|off' })
    const saved = (await $.store.get('theme')) as string | undefined
    if (saved && THEMES[saved]) try { await $.theme.set({ colors: THEMES[saved]().theme }) } catch {}
    return next(e)
  })
  on('command.run', { command: 'skin' }, async ($, e) => {
    const name = e.args.trim()
    if (name === 'off') { try { await $.theme.clear() } catch {}; await $.store.delete('theme'); return { text: 'Theme cleared.' } }
    if (!THEMES[name]) return { text: 'Use /skin paper, midnight, forest or off.' }
    await $.store.set('theme', name)
    let r: { isDrawn?: boolean } | null = null
    try { r = await $.theme.set({ colors: THEMES[name]().theme }) } catch {}
    return { text: r?.isDrawn ? `Theme ${name} set.` : `Theme ${name} saved; this surface draws no themes (desktop/mobile only).` }
  })
}
