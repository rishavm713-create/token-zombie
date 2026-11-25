# Test-first loop

One behaviour at a time, smallest step.

1. Write a single test that describes the behaviour through the public interface. Run it and watch it fail for the right reason (not a typo or import error).
2. Write the least code that turns it green. No extras the test does not ask for.
3. Run the whole suite. Then tidy names and duplication with all tests green.
4. Repeat with the next behaviour. Do not write a batch of tests first.

Rules of thumb:
- Test what the code does, not how it does it; internals can change freely.
- Mock only the edges you do not own (network, clock, disk). Never mock the thing under test.
- Bug report means a failing test first, then the fix.
- A test that never failed proves nothing: break the code on purpose once to see it go red.
