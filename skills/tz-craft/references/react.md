# React and Next.js

- Fetch data in parallel, not in a waterfall: start independent requests together and await them together. Fetch on the server where the framework allows.
- Keep client bundles small: import only what you use, split heavy or rarely-seen components with lazy loading, keep server-only code out of client files.
- Derive values during render instead of copying props into state or syncing with effects. An effect is for talking to the outside world, not for computing.
- Keep state as low and as local as it can be; lift only when two siblings need it.
- Give list items stable keys from data, never the array index when order can change.
- Memoize only after you measured a slow render; unstable object or function props are the usual cause.
- Show loading and error states for every async part, and use semantic elements with labels so the UI is accessible.
