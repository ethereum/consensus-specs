# Test format: Compute cells and KZG proofs

Compute the cells and cell KZG proofs for a given `blob`.

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input:
  blob: Blob -- the data blob
output: Tuple[List[Cell], List[KZGProof]] -- the cells and proofs
```

- `Blob` is a 131072-byte hexadecimal string, prefixed with `0x`.
- `Cell` is a 2048-byte hexadecimal string, prefixed with `0x`.
- `KZGProof` is a 48-byte hexadecimal string, prefixed with `0x`.

All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with
`0x`.

## Condition

The `compute_cells_and_kzg_proofs` handler should compute the cells (chunks of
an extended blob) and cell KZG proofs for `blob`, and the result should match
the expected `output`. If the blob is invalid (e.g. incorrect length or one of
the 32-byte blocks does not represent a BLS field element) it should error, i.e.
the output should be `null`.
