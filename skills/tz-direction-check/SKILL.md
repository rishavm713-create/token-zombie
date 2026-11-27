---
name: tz-direction-check
description: Check the app against its PRD and requirement docs and give a scorecard plus a to-do list. Use at milestones or when work feels busy but unsure it is going the right way; tokens spent and changes shipped measure effort, not direction.
license: MIT
---
# direction-check
Idea source: interview with the Vercel CEO on working with AI agents (2026), as summarised in a pasted list of 7 tips. Own wording.
1. Find the PRD/requirements (README, docs/, issues). None: ask for the goal in 3 lines first.
2. List each requirement; mark Done / Partial / Missing / Drifted (built but not asked for), with the file or test that proves it.
3. Scorecard: counts per mark, then the 3 biggest gaps by user impact.
4. To-do list ordered by impact; flag anything built that no requirement asked for.
Read only the docs and entry points, not the whole repo.
