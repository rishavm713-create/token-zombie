# Web UI review

Report each problem as file:line, the fault, the fix.

- Use native elements: button for actions, link for navigation. No click handlers on plain divs.
- Every control works by keyboard and shows a visible focus mark; dialogs take focus, keep it, then return it.
- Inputs have a label, a correct type and autocomplete hint; never block paste; show errors beside the field.
- Icon-only controls and meaningful images have text names; decorative ones are hidden from screen readers.
- Colour is never the only signal; text contrast meets WCAG AA; zoom stays enabled.
- Honour reduced-motion; animate transform and opacity; motion can be interrupted.
- Reserve space for images and late content so nothing jumps.
- Handle empty, loading, error, very long text and narrow screens.
- Keep shareable state (filters, tabs, page) in the URL.
- Confirm destructive actions or offer undo.
