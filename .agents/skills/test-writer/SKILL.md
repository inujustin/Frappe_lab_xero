---
name: test-writer
description: Write tests for code that already exists, changing test files only. Use when asked to write tests.
---

# Test writer

The production code is frozen for this work. Your job is to describe its intended behaviour in tests, not to make the code pass.

## Steps

1. Take from the request which behaviour to cover and the example cases. If there are none, propose the cases and ask before writing.
2. Read the production code under test (read-only) and any existing tests next to it. Follow their structure and naming.
3. Write the smallest set of tests that covers those cases:
   - one behaviour per test, named for the behaviour (`test_rejects_discount_above_limit`),
   - the example cases, the main failure path, and the permission case if the code checks permissions,
   - no sleeping, no network, no real external services; use the project's fixtures and factories.
4. Do not run the tests. Put the exact run command under "You run" in your summary.
5. If the code looks wrong for one of those cases, keep the failing test and say `FAILS: suspected bug in <file:line>`. Do not change production code and do not soften the assertion.

## Never

- Edit files that are not tests.
- Assert on implementation details (private helpers, exact SQL) instead of behaviour.
- Copy production logic into the test to compute the expected value.
