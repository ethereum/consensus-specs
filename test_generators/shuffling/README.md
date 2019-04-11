# Shuffling Tests

Tests for the swap-or-not shuffling in ETH 2.0.

For implementers, possible test runners implementing testing can include:
1) just test permute-index, run it for each index `i` in `range(count)`, and check against expected `output[i]` (default spec implementation)
2) test un-permute-index (the reverse lookup. Implemented by running the shuffling rounds in reverse: from `round_count-1` to `0`)
3) test the optimized complete shuffle, where all indices are shuffled at once, test output in one go.
4) test complete shuffle in reverse (reverse rounds, same as 2)

Tips for initial shuffling write:
- run with `round_count = 1` first, do the same with pyspec.
- start with permute index
- optimized shuffling implementations:
  - vitalik, Python: https://github.com/ethereum/eth2.0-specs/pull/576#issue-250741806
  - protolambda, Go: https://github.com/protolambda/eth2-shuffle
