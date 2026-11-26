---
name: tz-loop
description: Short rules for agent loops (change, locked check scores it, keep only if better, log rounds). ONLY when a single pass cannot do the job and the task repeats with a clear score; always ask the owner first.
license: MIT
---
# tz-loop
Own wording from a video on loop engineering (2026). Full version and scaffold script: TZ Studio `loop-engineering`.
0. Smallest loop (3 rounds default). Ask the owner in one line before starting; never start on your own.
1. Worth it only if: repeated often, budget fits many rounds, score needs no human, agent can run what it built.
2. Checks written first, locked read-only, never edited by the agent; include "wired in" and "really saved" checks.
3. Fresh builder per feature; keep a change only if the score improves; log every round in results.tsv.
4. Cap rounds at 3 (ask before more); work on a branch/copy.
