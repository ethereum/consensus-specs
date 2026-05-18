# Test format: Verify blob KZG proof

Use the blob KZG proof to verify that the KZG commitment for a given `blob` is
correct

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input:
  blob: Blob -- the data blob
  commitment: KZGCommitment -- the KZG commitment to the data blob
  proof: KZGProof -- The KZG proof
output: bool -- true (valid proof) or false (incorrect proof)
```

- `blob` here is encoded as a string: hexadecimal encoding of
  `4096 * 32 = 131072` bytes, prefixed with `0x`.

All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with
`0x`.

## Condition

The `verify_blob_kzg_proof` handler should verify that `commitment` is a correct
KZG commitment to `blob` by using the blob KZG proof `proof`, and the result
should match the expected `output`. If the commitment or proof is invalid (e.g.
not on the curve or not in the G1 subgroup of the BLS curve) or `blob` is
invalid (e.g. incorrect length or one of the 32-byte blocks does not represent a
BLS field element), it should error, i.e. the output should be `null`.
