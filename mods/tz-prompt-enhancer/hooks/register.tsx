import type { Register } from 'claude-code'

// One explicit Haiku call per /enhance. Never runs on normal prompts (no always-on cost).
export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'enhance', description: 'Rewrite a rough prompt: skills to load, questions to ask first, what done looks like' })
    return next(e)
  })
  on('command.run', { command: 'enhance' }, async ($, e) => {
    const rough = e.args.trim()
    if (!rough) return { text: 'Usage: /enhance <rough prompt>' }
    const skills = (await $.command.list()).map(c => c.name).slice(0, 60).join(', ')
    const prompt = `Rewrite this rough request as a short, clear prompt for a coding agent. Output only the prompt, max 120 words, with three labelled lines after it: "Load:" (names from this list that fit, or none): ${skills}; "Ask first:" (big choices, max 3); "Done looks like:". Keep the owner's intent; add nothing unasked.\n\nRough: ${rough}`
    const r = await $.model.complete({ model: 'haiku', prompt })
    return { text: r.isAnswered ? r.text : `Enhance failed: ${r.reason}` }
  })
}
