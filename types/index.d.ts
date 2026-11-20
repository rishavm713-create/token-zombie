export type Stats = {
  inp: number
  out: number
  cr: number
  cw: number
  ms: number
  turns: number
  spawns: number
  model: string
}
// Files the panel reads: raw text kept to skip redraws when nothing changed.
export type Files = {
  sig: string
  status: Record<string, unknown> | null
  isStale: boolean
  host: { cost_usd: number; ts: number; session?: string } | null
  isHostFresh: boolean
  mode: string
}
export type Act = { id: string; tool: string; isDone: boolean }
export type Note = { label: string; lines: string[]; err: string }

declare module 'claude-code' {
  interface PluginState {
    'token-zombie': {
      stats: Shaped<Stats>
      files: Shaped<Files>
      acts: Shaped<Act[]>
      note: Shaped<Note>
    }
  }
}
