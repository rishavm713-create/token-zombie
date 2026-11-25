# Git safety

Never lose work you cannot get back.

- Look first: `git status` and `git diff` before commit, reset, checkout, clean or rebase.
- No destructive commands (reset --hard, clean -f, checkout/restore ., branch -D, push --force) without the owner's clear yes in this chat. Prefer reversible; if forced, use --force-with-lease.
- Commit (or temp commit) before risky steps so reflog can rescue you.
- Stage named files, not `add -A`; never commit secrets, env files or build output.
- Never push to main, amend published commits or skip hooks unless asked.
- One logical change per commit; message says why.
- A guard blocked a command: do not rephrase around it; ask the owner.

Merge or rebase conflict:
- Read why each side changed (commit, PR, issue) before editing; do not blanket take ours or theirs.
- Keep both intents; if they clash, follow the merge's goal and say what was lost. Add no new behaviour.
- Run the project checks, then finish. Abort only if the owner asks.
