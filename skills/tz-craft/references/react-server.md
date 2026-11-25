# React on the server

- Treat every server action and route handler as a public endpoint: check identity, permission and input inside it, not only in the page or middleware that calls it.
- Never keep per-request data in module-level variables; concurrent requests share them and can leak one user's data to another.
- De-duplicate repeated reads within a request. Cache across requests only with a key that includes everything the result depends on (user, tenant, locale), plus an expiry or invalidation.
- Pass client components only the fields they render. Whole records cost transfer size and can expose private columns.
- Start independent reads early and await each where it is needed; a branch that exits early should not pay for data it never uses.
- Move work the response does not depend on (logging, analytics) to after the response, with its errors still reported.
- Stream slow parts behind their own loading boundary so the rest of the page appears first.
