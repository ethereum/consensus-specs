<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Single leaf merkle proof tests](#single-leaf-merkle-proof-tests)
  - [Test case format](#test-case-format)
    - [`object.ssz_snappy`](#objectssz_snappy)
    - [`proof.yaml`](#proofyaml)
  - [Condition](#condition)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Single leaf merkle proof tests

This series of tests provides reference test vectors for validating correct
generation and verification of merkle proofs based on static data.

## Test case format

Tests for each individual SSZ type are grouped into a `suite` indicating the SSZ type name.

### `object.ssz_snappy`

A SSZ-snappy encoded object from which other data is generated. The SSZ type can be determined from the test `suite` name.

### `proof.yaml`

A proof of the leaf value (a merkle root) at generalized-index `leaf_index` in the given `object`.

```yaml
leaf: Bytes32            # string, hex encoded, with 0x prefix
leaf_index: int          # integer, decimal
branch: list of Bytes32  # list, each element is a string, hex encoded, with 0x prefix
```

## Condition

A test-runner can implement the following assertions:
- Check that `is_valid_merkle_branch` confirms `leaf` at `leaf_index` to verify
  against `hash_tree_root(object)` and `branch`.
- If the implementation supports generating merkle proofs, check that the
  self-generated proof matches the `branch` provided with the test.
