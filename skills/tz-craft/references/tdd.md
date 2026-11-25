# Test-first loop

First name the seams: the public interfaces you will test through. Confirm them if the owner is around; test the critical paths, not everything.

One thin end-to-end slice at a time:

1. Write a single test of one behaviour. Run it and watch it fail for the right reason (not a typo or import error).
2. Write the least code that turns it green. No extras for future tests.
3. Run the whole suite. Tidy only with all tests green.
4. Repeat. Never write all tests first, then all code.

Bad tests:
- Coupled to internals (private methods, call order, reading the DB behind the interface): breaks on refactor.
- Tautological: expected value computed the way the code does it. Use known literals or the spec.

Mock only system edges (network, third-party API, clock, randomness, sometimes disk or DB), never your own modules. Pass those edges in; one function per external call.

Bug report means a failing test first, then the fix. A test that never failed proves nothing.
