# Module design

Aim for deep modules: much behaviour behind a small interface.

- Interface means all a caller must know: types, invariants, ordering, errors, config, speed.
- Deletion test: remove the module in your head. If complexity vanishes it was a pass-through; if it reappears in many callers it earns its keep.
- Fewer methods and parameters; hide more inside.
- Accept dependencies instead of creating them; return results instead of mutating.
- Test through the same interface callers use. Needing to reach past it means the shape is wrong.
- Add a seam (swap point) only when something really varies: one adapter is hypothetical, two are real.
- Unsure of the interface: sketch two very different ones and compare.

Words and decisions:
- If GLOSSARY.md exists, use its terms; keep it free of implementation detail.
- Write a short ADR only when a decision is hard to reverse, surprising without context and a real trade-off.
