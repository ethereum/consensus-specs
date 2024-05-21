# Shuffling Tests

Tests for the swap-or-not shuffling in the beacon chain.

Tips for initial shuffling write:
- run with `round_count = 1` first, do the same with pyspec.
- start with permute index
- optimized shuffling implementations:
  - vitalik, Python: https://github.com/ethereum/consensus-specs/pull/576#issue-250741806
  - protolambda, Go: https://github.com/protolambda/eth2-shuffle
