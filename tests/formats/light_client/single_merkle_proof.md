# Single leaf merkle proof tests

This series of tests provides reference test vectors for validating correct
generation and verification of merkle proofs based on static data.

## Test case format

### `state.ssz_snappy`

An SSZ-snappy encoded `BeaconState` object from which other data is generated.

### `proof.yaml`

A proof of the leaf value (a merkle root) at generalized-index `leaf_index` in the given `state`.

```yaml
leaf: Bytes32            # string, hex encoded, with 0x prefix
leaf_index: int          # integer, decimal
branch: list of Bytes32  # list, each element is a string, hex encoded, with 0x prefix 
```

## Condition

A test-runner can implement the following assertions:
- Check that `is_valid_merkle_branch` confirms `leaf` at `leaf_index` to verify
  against `has_tree_root(state)` and `proof`.
- If the implementation supports generating merkle proofs, check that the
  self-generated proof matches the `proof` provided with the test.
