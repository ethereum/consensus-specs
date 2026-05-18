# Test format: shuffling

The runner of the Shuffling test type has only one handler: `core`.

However, this does not mean that testing is limited. Clients may take different
approaches to shuffling, for optimizing, and supporting advanced lookup behavior
back in older history.

For implementers, possible test runners implementing testing can include:

1. Just test permute-index, run it for each index `i` in `range(count)`, and
   check against expected `mapping[i]` (default spec implementation).
2. Test un-permute-index (the reverse lookup; implemented by running the
   shuffling rounds in reverse, from `round_count-1` to `0`).
3. Test the optimized complete shuffle, where all indices are shuffled at once;
   test output in one go.
4. Test complete shuffle in reverse (reverse rounds, same as #2).

## Test case format

### `mapping.yaml`

```yaml
seed: bytes32
count: int
mapping: List[int]
```

- The `bytes32` is encoded as a string, hexadecimal encoding, prefixed with
  `0x`.
- Integers are validator indices. These are `uint64`, but realistically they are
  not as big.

The `count` specifies the validator registry size. One should compute the
shuffling for indices `0, 1, 2, 3, ..., count (exclusive)`.

The `seed` is the raw shuffling seed, passed to permute-index (or optimized
shuffling approach).

The `mapping` is a look up array, constructed as
`[spec.compute_shuffled_index(i, count, seed) for i in range(count)]` I.e.
`mapping[i]` is the shuffled location of `i`.

## Condition

The resulting list should match the expected output after shuffling the implied
input, using the given `seed`. The output is checked using the `mapping`, based
on the shuffling test type (e.g. can be backwards shuffling).
