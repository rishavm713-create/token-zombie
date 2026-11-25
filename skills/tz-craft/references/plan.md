# Plan

Plan only as much as the risk needs.

- Restate the goal and what done looks like as something checkable. If it is ambiguous, ask one short question or state the assumption you are taking.
- Read the code that will change before deciding how.
- Break the work into steps that each leave things working and each have their own check. Put the riskiest or least-known step first.
- List files you expect to touch and files you will leave alone.
- Pick the simplest approach that meets the goal; note one rejected alternative and why.
- A behaviour change that must outlive this session: `tz spec new <name>` (proposal, requirement deltas, tasks), `tz spec check <name>`, then work from `tz spec status <name>` (prints only the next step); `tz spec archive <name>` folds the deltas into openspec/specs/.
- Small, obvious tasks need no plan: just do them.
- When the plan changes mid-way, rewrite the list instead of silently drifting.
