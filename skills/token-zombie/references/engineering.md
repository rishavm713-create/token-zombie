# Engineering rules

Adapted from the `karpathy-guidelines` skill (MIT licence), itself derived from Andrej Karpathy's public notes on LLM coding pitfalls (https://x.com/karpathy/status/2015883857489522876). TOKEN ZOMBIE keeps the principles, not the text.

1. Understand first: read the code and callers the change touches; say assumptions in one line.
2. Simplicity: the simplest code that works; no abstraction, option or config nobody asked for.
3. Minimal, focused change: touch only what the task needs; match the existing style.
4. Test real behaviour: define a check (test, run, screenshot) before editing; loop until it passes.
5. Verify before "done": report failures with their output; never claim an untested result.
6. Docs follow code: update README/help/references in the same change.

Why it saves tokens: wrong guesses and rewrites are the most expensive tokens in a chat. A failed check caught early costs one round trip; a wrong "done" costs a whole new task.
