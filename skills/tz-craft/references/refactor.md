# Refactor

Behaviour stays the same; only structure moves.

- Start green. If the area has no tests, add characterization tests that pin today's output, then refactor.
- Small steps, one idea each (rename, extract, move, inline). Run the tests after every step; revert a step that goes red instead of patching forward.
- Never mix a refactor with a feature or bug fix in one commit.
- Prefer deleting code over reorganizing it: remove dead branches, unused params and one-use wrappers first.
- Do not add an abstraction for a single use. Wait for the third similar case.
- Touch only what the goal needs; leave unrelated style alone.
- Finish by comparing the diff size and the test result with the start.
