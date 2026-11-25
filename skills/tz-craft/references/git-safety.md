# Git safety

Never lose work you cannot get back.

- Look first: `git status` and `git diff` before commit, reset, checkout, clean or rebase.
- Do not run destructive commands (reset --hard, clean -f, checkout -- ., branch -D, push --force) without the owner's clear yes in this chat. Prefer the reversible option; if forced, use --force-with-lease.
- Commit or save a temporary commit before risky operations so reflog can rescue you.
- Never commit secrets, env files or build output; stage named files, not `add -A` blindly.
- Never push to main or amend published commits unless asked.
- Skip hooks or signing checks only if told to.
- One logical change per commit, message says why.
- If a command hits a conflict or unexpected state, stop and report instead of improvising.
