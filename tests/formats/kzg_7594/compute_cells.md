# Test format: Compute cells

Compute the cells for a given `blob`.

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input:
  blob: Blob -- the data blob
output: List[Cell] -- the cells
```

- `Blob` is a 131072-byte hexadecimal string, prefixed with `0x`.
- `Cell` is a 2048-byte hexadecimal string, prefixed with `0x`.

All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with
`0x`.

## Condition

The `compute_cells` handler should compute the cells (chunks of an extended
blob) for `blob`, and the result should match the expected `output`. If the blob
is invalid (e.g. incorrect length or one of the 32-byte blocks does not
represent a BLS field element) it should error, i.e. the output should be
`null`.
