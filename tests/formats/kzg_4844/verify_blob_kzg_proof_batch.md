# Test format: Verify blob KZG proof batch

Use the blob KZG proofs to verify that the KZG commitments for given `blobs` are
correct

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input:
  blobs: List[Blob] -- the data blob
  commitments: List[KZGCommitment] -- the KZG commitment to the data blob
  proofs: List[KZGProof] -- The KZG proof
output: bool -- true (all proofs are valid) or false (some proofs incorrect)
```

- `blobs` here are encoded as a string: hexadecimal encoding of
  `4096 * 32 = 131072` bytes, prefixed with `0x`.

All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with
`0x`.

## Condition

The `verify_blob_kzg_proof_batch` handler should verify that `commitments` are
correct KZG commitments to `blobs` by using the blob KZG proofs `proofs`, and
the result should match the expected `output`. If any of the commitments or
proofs are invalid (e.g. not on the curve or not in the G1 subgroup of the BLS
curve) or any blob is invalid (e.g. incorrect length or one of the 32-byte
blocks does not represent a BLS field element), it should error, i.e. the output
should be `null`.
