import type { Register } from 'claude-code'

const PANE = 'studio-tasks'
type Task = { id: string; status: string; title: string; approval?: unknown }

// Read-only view of ~/tz-studio-data/state/<project>/{project,tasks}.json (STUDIO_HOME honoured).
// Nothing runs until /studio-tasks opens the pane; no timer, no model call.
export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'studio-tasks', description: 'Show TZ Studio projects, tasks and status in a pane' })
    return next(e)
  })

  on('command.run', { command: 'studio-tasks' }, async $ => {
    await $.ui.open({ id: PANE, title: 'Studio tasks' })
    return { text: 'Studio tasks pane opened.' }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const home = (await $.env.get('STUDIO_HOME')) ?? `${(await $.env.get('HOME')) ?? ''}/tz-studio-data`
    const rows: { k: string; text: string; dim: boolean }[] = []
    try {
      const ids = (await $.fs.list(`${home}/state`)).filter(x => x.kind === 'directory' && !x.name.startsWith('quality-'))
      for (const d of ids.slice(0, 20)) {
        try {
          const t = JSON.parse(await $.fs.read(`${home}/state/${d.name}/tasks.json`))
          const tasks: Task[] = Array.isArray(t) ? t : (t.tasks ?? [])
          if (!tasks.length) continue
          rows.push({ k: d.name, text: d.name, dim: false })
          for (const k of tasks.slice(0, 15)) {
            rows.push({ k: d.name + k.id, text: `  ${k.id} ${k.status}${k.approval ? ' (needs approval)' : ''}  ${k.title}`, dim: k.status === 'done' })
          }
        } catch {}
      }
    } catch {}
    return (
      <Box flexDirection="column">
        {rows.length === 0 && <Text dimColor>No Studio tasks found.</Text>}
        {rows.slice(0, Math.max(1, (e.viewport?.rows ?? 24) - 3)).map(r => (
          <Text key={r.k} dimColor={r.dim}>{r.text}</Text>
        ))}
      </Box>
    )
  })
}
