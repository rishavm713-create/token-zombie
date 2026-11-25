# Isolate and finish a branch

Start:
- Already isolated if `git rev-parse --git-dir` differs from `--git-common-dir` (and not a submodule): do not nest.
- Else prefer the harness worktree tool over `git worktree add`; ask before creating one unless told. A worktree folder inside the repo must be git-ignored.
- Set up, run tests: know the baseline before editing. Red baseline: report, ask.

Finish:
1. Full test suite green, or stop and report.
2. Confirm the base branch; do not guess.
3. Offer: merge locally, push and open a PR, or keep. Wait for the choice.
4. After a local merge, test the merged result before removing anything.
5. Remove only worktrees you created, from outside them, then `git branch -d`. Keep it for an open PR.
6. Discard only on explicit request, after listing what will be lost.
