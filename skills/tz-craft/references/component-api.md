# Component API design

- A growing set of boolean props means many untested combinations. Replace them with named variants, or with parts the caller assembles.
- For complex widgets, expose a parent plus subcomponents that share state through context, so callers choose the layout.
- Prefer passing children over render callbacks or `renderX` props; use a callback only when the child needs data from the parent.
- Let one provider own the state and publish a small interface (current values and actions). Consumers then do not care whether it is local, global or remote.
- Lift state into the provider when a sibling outside the visual box needs it; do not sync copies with effects or refs.
- Pick controlled or uncontrolled per value and document it; if both, use the usual value / defaultValue / onChange trio.
- Forward standard attributes and the ref to the real element.
- Check the framework version in use before applying newer ref or context syntax.
