# Test format: Compute challenge

Compute the Fiat-Shamir challenge value for KZG operations.

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input:
  blob: Blob -- the blob data
  commitment: Bytes48 -- the KZG commitment
output: Bytes32 -- the computed challenge value
```

- `Blob` is a 131072-byte hexadecimal string, prefixed with `0x`.
- `Bytes48` is a 48-byte hexadecimal string, prefixed with `0x`.
- `Bytes32` is a 32-byte hexadecimal string, prefixed with `0x`.

All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with
`0x`.

## Condition

The `compute_challenge` handler should compute a challenge value using the
Fiat-Shamir heuristic by hashing together the protocol domain separator, the
polynomial degree, the blob, and the commitment. This is an internal helper
function, so all inputs are assumed to be valid. The computed challenge should
match the expected `output`.

Note: This function is not a public method but an internal helper used by other
KZG functions. It assumes all inputs are already validated.
