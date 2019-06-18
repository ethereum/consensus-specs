# Test format: shuffling

The runner of the Shuffling test type has only one handler: `core`.

However, this does not mean that testing is limited.
Clients may take different approaches to shuffling, for optimizing,
 and supporting advanced lookup behavior back in older history.

For implementers, possible test runners implementing testing can include:
1) Just test `get_shuffled_index`.
2) Test the reverse lookup; implemented by running the shuffling rounds in reverse, from `round_count-1` to `0`.
3) Test the optimized complete shuffle, where all indices are shuffled at once.
4) Test complete shuffling in reverse (reverse rounds, similar to #2).

## Test case format

```yaml
seed: bytes32
count: int
shuffled: List[int]
```

- The `bytes32` is encoded as a string, hexadecimal encoding, prefixed with `0x`.
- Integers are validator indices. These are `uint64`, but realistically they are not as big.

The `count` specifies the count of validators being shuffled (i.e. active validators during committee computation).

One should test the shuffling for indices `0, 1, 2, 3, ..., count (exclusive)`.

`shuffled` is a mapping from `i` to `get_shuffled_index(i, count, seed)`.
- `i` here is the index within committee-partitioned space. `i...i+N (excl.)` is used to get the validators for a committee of size `N`.
- `get_shuffled_index(i, count, seed) -> int` returns the index within the active-validators space. Pointing to the validator assigned to the committee corresponding to `i`.

`seed` is the raw shuffling seed, passed to shuffling function. 

## Condition

For the `get_shuffled_index` implementation (or list-wise equivalent): `get_shuffled_index(i, count, seed) == shuffled[i]`
