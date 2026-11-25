# Plan

Plan only as much as the risk needs. Small, obvious tasks need none.

- Restate the goal and a checkable "done". Ambiguous: ask, or state your assumption.
- Read the code that will change first. Look up facts yourself; decisions are the owner's.
- Cut thin vertical slices: each runs through every layer, is checkable alone and fits one fresh chat. Riskiest first.
- Do preparatory refactors first: make the change easy, then make it.
- Mark which steps block which; any unblocked step may start.
- Wide mechanical change (rename, retype) that cannot land as slices: expand (add new beside old), migrate callers in batches that stay green, then delete the old.
- List files you expect to touch and files you will leave alone.
- Pick the simplest approach; note one rejected alternative and why.
- When the plan changes, rewrite it instead of drifting.
- Pick the simplest approach that meets the goal; note one rejected alternative and why.
- A behaviour change that must outlive this session: `tz spec new <name>` (proposal, requirement deltas, tasks), `tz spec check <name>`, then work from `tz spec status <name>` (prints only the next step); `tz spec archive <name>` folds the deltas into openspec/specs/.
- Small, obvious tasks need no plan: just do them.
- When the plan changes mid-way, rewrite the list instead of silently drifting.
