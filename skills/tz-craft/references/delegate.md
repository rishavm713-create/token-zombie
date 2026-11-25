# Delegate to subagents

Subagents cost tokens. Use them for independent work; related failures or shared files stay with one worker.

- Brief each one cold: one scope, goal, context (exact errors, paths), constraints (what not to touch), what to return. Never paste your history.
- Pick the model per task and set it: cheap for clear 1-2 file work, stronger for integration, design and tricky review.
- Parallel only when they cannot collide; send those calls together. Implementers editing one tree go one at a time.
- Handle blocked or "needs context" replies by supplying what is missing, not by resending the same brief.
- A report is a claim: read the diff, check for conflicts, run the full suite.
- Review gets requirement plus diff; do not tell the reviewer what to ignore.
- Running a plan: record minor snags as your own ruling and go on; stop for destructive, irreversible or owner-level choices.
