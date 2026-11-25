# Learn from a mistake

Turn one solved, verified problem into the cheapest thing that stops a repeat.

1. Keep it only if the reason is not readable from code, tests, checks or docs, and losing it would likely cause a repeat or a long re-investigation. Else write nothing and say why.
2. One lesson per run. Name symptom, root cause (not the symptom), fix.
3. Take the first form that works: remove the second way of doing it; a test or lint rule (see it fail on the defect, pass on the tree); a line in an existing coding standard; a learning doc.
4. Doc: `tz learn capture --title T --symptom S --cause C --fix F --detect D` (dry run; `--apply` writes `docs/solutions/`, 1.5 KB max). A wrong or overlapping doc is updated, never duplicated.
5. A habit or project fact instead: one "when X, do Y" line in project or global notes; merge near duplicates, drop stale rules.
6. Before similar work: `tz learn recall WORDS`. After refactors: `tz learn check` flags stale citations; fix them, do not delete unasked.
