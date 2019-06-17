# SSZ, generic tests

This set of test-suites provides general testing for SSZ:
to instantiate any container/list/vector/other type from binary data.

Since SSZ is in a development-phase, the full suite of features is not covered yet.
Note that these tests are based on the older SSZ package.
The tests are still relevant, but limited in scope:
more complex object encodings have changed since the original SSZ testing.

A minimal but useful series of tests covering `uint` encoding and decoding is provided.
This is a direct port of the older SSZ `uint` tests (minus outdated test cases).

Test format documentation can be found here: [uint test format](./uint.md).

*Note*: The current Phase 0 spec does not use larger uints, and uses byte vectors (fixed length) instead to represent roots etc.
The exact uint lengths to support may be redefined in the future.

## Recommendation

For SSZ testing directly applicable to test-networks, refer to the [`ssz_static`](../ssz_static/README.md) tests,
which cover SSZ behavior for phase-0, for all container types.
