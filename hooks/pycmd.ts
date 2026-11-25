// Python launcher argv prefix for tools/panel. Windows: `python3` is a Store stub and `sh` is not on PATH (only hooks run in Git Bash), so use the `py` launcher.
// Mods run without Node: `process` may not exist, so guard it (an unguarded `process.platform` made the whole panel fail to load).
const win = typeof process !== 'undefined' && (process as { platform?: string }).platform === 'win32'
export const PY: string[] = win ? ['py', '-3'] : ['python3']
