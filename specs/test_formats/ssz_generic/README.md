# SSZ, generic tests

This set of test-suites provides general testing for SSZ:
 to instantiate any container/list/vector/other type from binary data.

Since SSZ is in a development-phase, not the full suite of features is covered yet.
Note that these tests are based on the older SSZ package.
The tests are still relevant, but limited in scope:
 more complex object encodings have changed since the original SSZ testing.

A minimal but useful series of tests covering `uint` encoding and decoding is provided.
This is a direct port of the older SSZ `uint` tests (minus outdated test cases).

[uint test format](./uint.md).

Note: the current phase-0 spec does not use larger uints, and uses byte vectors (fixed length) instead to represent roots etc.
The exact uint lengths to support may be redefined in the future.

Extension of the SSZ tests collection is planned, with an update to the new spec-maintained `minimal_ssz.py`,
 see CI/testing issues for progress tracking.
