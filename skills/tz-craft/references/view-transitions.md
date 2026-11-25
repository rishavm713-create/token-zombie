# View transitions

- Animate only to explain a change: same object moving between views, direction of navigation, content arriving. If it explains nothing, skip it.
- Treat it as progressive enhancement: feature-detect, and make the plain state change work without it.
- A shared element needs a name that is unique on screen at that moment; duplicates cancel the transition.
- Name only the elements that move; naming many adds snapshot cost.
- Keep the DOM update inside the transition callback fast; fetch data before starting.
- Turn motion off or reduce it for users who ask for reduced motion.
- In React or a framework router, check which version provides the API and whether it is still experimental; use its wrapper so rendering and the snapshot stay in step.
- Test back navigation, rapid repeat clicks and an unsupported browser.
