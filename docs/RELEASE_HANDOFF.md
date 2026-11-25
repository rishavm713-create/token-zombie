# Release handoff
## v2.1.0 (done)
PR #4 merged (78743eb), tag v2.1.0 pushed, GitHub release created. g0 merged via PR #6.
## merge/g123 (local only, NOT pushed, no PR)
g1, g2, g3 merged on top of main; see docs/INTEGRATION_STATUS.md (conflicts + open items) and docs/TEST_EVIDENCE.md (suite: pending at time of writing).
## Owner tasks
- Run `./install.sh` yourself (Claude never runs it on live ~/.claude); then `tz hooks live`, HOST-VERIFY checklist.
- OK needed for: paid `tz ab` trials; deleting remote group branches; pushing/merging merge/g123.
- Licence review: claude-squad LICENSE (possibly AGPL) and token-optimizer LICENSE were deleted by the group branches.
## Next steps, in order
1. Read final suite TOTAL in TEST_EVIDENCE; fix any failure.
2. Licence review; restore or justify deleted LICENSE files.
3. Verify g1 `tz budget` vs v21; push merge/g123 and open PR only with owner OK.
4. Windows session: 11 CI failures, separate work.
Rules: one integration owner; no force push; full suite after each merge.
