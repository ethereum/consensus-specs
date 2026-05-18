# Test format: Blob to KZG commitment

Compute the KZG commitment for a given `blob`.

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input:
  blob: Blob -- the data blob
output: KZGCommitment -- The KZG commitment
```

- `blob` here is encoded as a string: hexadecimal encoding of
  `4096 * 32 = 131072` bytes, prefixed with `0x`.

All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with
`0x`.

## Condition

The `blob_to_kzg_commitment` handler should compute the KZG commitment for
`blob`, and the result should match the expected `output`. If the blob is
invalid (e.g. incorrect length or one of the 32-byte blocks does not represent a
BLS field element) it should error, i.e. the output should be `null`.
