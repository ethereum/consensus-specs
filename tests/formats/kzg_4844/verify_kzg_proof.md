<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Test format: Verify KZG proof](#test-format-verify-kzg-proof)
  - [Test case format](#test-case-format)
  - [Condition](#condition)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Test format: Verify KZG proof

Verify the KZG proof for a given `blob` and an evaluation point `z` that claims to result in a value of `y`.

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input:
  commitment: KZGCommitment -- the KZG commitment to the data blob
  z: Bytes32 -- bytes encoding the BLS field element at which the polynomial should be evaluated
  y: Bytes32 -- the claimed result of the evaluation
  proof: KZGProof -- The KZG proof
output: bool -- true (valid proof) or false (incorrect proof)
```

- `z` here is encoded as a string: hexadecimal encoding of `32` bytes representing a big endian encoded field element, prefixed with `0x`.
- `y` here is encoded as a string: hexadecimal encoding of `32` bytes representing a big endian encoded field element, prefixed with `0x`.

All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with `0x`.

## Condition

The `verify_kzg_proof` handler should verify the KZG proof for evaluating the polynomial represented by `blob` at `z` resulting in the value `y`, and the result should match the expected `output`. If the commitment or proof is invalid (e.g. not on the curve or not in the G1 subgroup of the BLS curve) or `z` or `y` are not a valid BLS field element, it should error, i.e. the output should be `null`.
