# SSZ tests

SSZ has changed throughout the development of ETH 2.0.

## Contents

A minimal but useful series of tests covering `uint` encoding and decoding is provided.
This is a direct port of the older SSZ `uint` tests (minus outdated test cases).

[uint test format](./uint.md).

Note: the current phase-0 spec does not use larger uints, and uses byte vectors (fixed length) instead to represent roots etc.
The exact uint lengths to support may be redefined in the future.

Extension of the SSZ tests collection is planned, see CI/testing issues for progress tracking.
