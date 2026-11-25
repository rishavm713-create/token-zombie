// Python launcher argv prefix for tools/panel. Windows: `python3` is a Store stub and `sh` is not on PATH (only hooks run in Git Bash), so use the `py` launcher.
export const PY: string[] = process.platform === 'win32' ? ['py', '-3'] : ['python3']
