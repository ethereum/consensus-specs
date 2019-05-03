# Test format: shuffling

The runner of the Shuffling test type has only one handler: `core`.

However, this does not mean that testing is limited.
Clients may take different approaches to shuffling, for optimizing,
 and supporting advanced lookup behavior back in older history.

For implementers, possible test runners implementing testing can include:
1) Just test permute-index, run it for each index `i` in `range(count)`, and check against expected `output[i]` (default spec implementation).
2) Test un-permute-index (the reverse lookup; implemented by running the shuffling rounds in reverse, from `round_count-1` to `0`).
3) Test the optimized complete shuffle, where all indices are shuffled at once; test output in one go.
4) Test complete shuffle in reverse (reverse rounds, same as #2).

## Test case format

```yaml
seed: bytes32
count: int
shuffled: List[int]
```

- The `bytes32` is encoded a string, hexadecimal encoding, prefixed with `0x`.
- Integers are validator indices. These are `uint64`, but realistically they are not as big.

The `count` specifies the validator registry size. One should compute the shuffling for indices `0, 1, 2, 3, ..., count (exclusive)`.
Seed is the raw shuffling seed, passed to permute-index (or optimized shuffling approach). 

## Condition

The resulting list should match the expected output `shuffled` after shuffling the implied input, using the given `seed`.

