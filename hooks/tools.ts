

// Callable tz tools: each wraps an existing `tz` command (no new engine). Argv only, no shell; fixed command per tool.
// Also a hook-proof log: counts the hook events this session actually delivered (`tz hooks`-style evidence from a live host).
const TOOLS: Record<string, { desc: string; argv: (i: any) => string[] | null; props?: Record<string, unknown> }> = {
  tz_recall: { desc: 'Search saved tz memory (spilled outputs, handoffs, ledger) for a topic.', props: { query: { type: 'string' } },
    argv: i => (i.query ? ['recall', String(i.query)] : null) },
  tz_map: { desc: 'Compact map of a repository: files and their definitions.', props: { dir: { type: 'string' } },
    argv: i => ['map', String(i.dir || '.')] },
  tz_checkpoint: { desc: 'Save a checkpoint of current progress so a new chat can resume.', argv: () => ['checkpoint'] },
  tz_status: { desc: 'Context size, token burn and warn state for this chat.', argv: () => ['status'] },
}

export function startTools($: any) {
  return Promise.all(Object.entries(TOOLS).map(([name, t]) =>
    $.tool.register({ name, description: t.desc, isDeferred: false, inputSchema: { type: 'object', properties: t.props ?? {} } }))).catch(() => {})
}

const seen: Record<string, number> = {}
async function proof($: any, ev: string) {
  seen[ev] = (seen[ev] ?? 0) + 1
  try {
    const home = await $.env.get('HOME')
    const sid = String(await $.session.id()).replace(/[^A-Za-z0-9-]/g, '').slice(0, 64) || 'x'
    if (home) await $.fs.write(`${home}/.claude/token-zombie/hookproof-${sid}.json`, JSON.stringify({ seen, ts: Math.round(Date.now() / 1000) }))
  } catch { /* fail-open: proof must never break a call */ }
}

async function runTz($: any, name: string, e: any) {
  const argv = TOOLS[name]!.argv(e)
  if (!argv) return { deny: `token-zombie: ${name} needs its input` }
  try {
    const r = await $.process.run(['python3', `${$.plugin.root}/bin/tz`, ...argv], { timeoutMs: 60_000 })
    return { result: ((r.stdout + (r.exitCode ? '\n' + r.stderr : '')).slice(0, 20_000) || '(no output)') } as any
  } catch (err) {
    return { deny: `token-zombie: ${name} failed: ${String((err as Error)?.message ?? err).slice(0, 120)}` }
  }
}

export const registerTools = (on: any) => {
  for (const name of Object.keys(TOOLS)) {
    on('tool.call', { tool: `mcp__token-zombie__${name}` }, ($, e: any) => runTz($, name, e))
  }

  on('prompt.submit', async ($, e, next) => { await proof($, 'prompt.submit'); return next(e) })
  on('session.end', async ($, e, next) => { await proof($, 'session.end'); return next(e) })
}
