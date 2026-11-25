# Tests worth having

- Name the break: what realistic bug turns this test red? None: delete it.
- Expected values come from literals or hand checks, never from the code under test.
- Assert behaviour, not source text, private calls or framework features. A test that fails on every intended change is noise.
- Exercise the real thing; mock only slow or external edges, after learning their side effects. Never assert on the mock itself.
- Doubles mirror real data in full and check arguments and order when those matter.
- No test-only methods in production classes.
- Mutation check: break the code on purpose, see red, restore.
