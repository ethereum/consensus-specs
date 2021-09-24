# Merkle tests

This series of tests provides reference test vectors for validating correct
generation and verification of merkle proofs based on static data.

## Test case format

### `meta.yaml`

```yaml
leaf_index: int        -- Generalized leaf index, verifying against the proof.
proof_count: int       -- Amount of proof elements.
```

### `state.ssz_snappy`

An SSZ-snappy encoded `BeaconState` object from which other data is generated.

### `leaf.ssz_snappy`

An SSZ-snappy encoded `Bytes32` reflecting the merkle root of `leaf_index` at
the given `state`.

### `proof_<index>.ssz_snappy`

A series of files, with `<index>` in range `[0, proof_count)`. Each file is an
SSZ-snappy encoded `Bytes32` and represents one element of the merkle proof for
`leaf_index` at the given `state`.

## Condition

A test-runner can implement the following assertions:
- Check that `is_valid_merkle_branch` confirms `leaf` at `leaf_index` to verify
  against `has_tree_root(state)` and `proof`.
- If the implementation supports generating merkle proofs, check that the
  self-generated proof matches the `proof` provided with the test.
