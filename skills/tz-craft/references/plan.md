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
