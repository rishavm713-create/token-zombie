# Plan

Plan only as much as the risk needs; small, obvious tasks need none.

- Restate the goal and a checkable "done". Ambiguous: ask, or state your assumption.
- Read the code that will change first. Look up facts yourself; decisions are the owner's.
- Thin vertical slices: each runs through every layer, checkable alone, fits one fresh chat. Riskiest first. Preparatory refactors first.
- Mark which steps block which; any unblocked step may start.
- Wide mechanical change: expand (new beside old), migrate callers in green batches, delete the old.
- List files to touch and files to leave alone.
- Simplest approach that meets the goal; note one rejected alternative and why.
- Plan changes: rewrite it, don't drift.
- Behaviour that must outlive this session: `tz spec new|check|status|archive <name>`.
