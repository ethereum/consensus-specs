# Test format: Compute blob KZG proof

Compute the blob KZG proof for a given `blob`, that helps with quickly verifying
that the KZG commitment for the blob is correct.

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input:
  blob: Blob -- the data blob
  commitment: Bytes48 -- the commitment to the blob
output: KZGProof -- The blob KZG proof
```

- `blob` here is encoded as a string: hexadecimal encoding of
  `4096 * 32 = 131072` bytes, prefixed with `0x`.
- `commitment` here is encoded as a string: hexadecimal encoding of `48` bytes,
  prefixed with `0x`.

All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with
`0x`.

## Condition

The `compute_blob_kzg_proof` handler should compute the blob KZG proof for
`blob`, and the result should match the expected `output`. If the blob is
invalid (e.g. incorrect length or one of the 32-byte blocks does not represent a
BLS field element) it should error, i.e. the output should be `null`.
