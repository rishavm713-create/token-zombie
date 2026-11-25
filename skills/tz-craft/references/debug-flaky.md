# Flaky tests and waits

Pass sometimes, fail under load or in parallel.

- Reproduce first: loop the test, run it in parallel, pin seed, clock, order and network.
- Replace guessed sleeps with waiting for the condition you care about (event seen, state reached, count met, file exists).
- Poll about every 10 ms, always with a timeout whose message names what never happened. Read fresh state inside the loop.
- A fixed delay is right only when timing itself is under test (debounce, tick): first wait for the trigger, then sleep a known multiple, and comment why.
- Never just raise a timeout or add a retry; find the race or shared state.
