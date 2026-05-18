# Test format: Verify cell KZG proof batch

Use the cell KZG `proofs` to verify that the KZG `commitments` for the given
`cells` are correct.

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input:
  commitments: List[Bytes48] -- the KZG commitments for each cell
  cell_indices: List[CellIndex] -- the cell index for each cell
  cells: List[Cell] -- the cells
  proofs: List[Bytes48] -- the KZG proof for each cell
output: bool -- true (all proofs are correct) or false (some proofs incorrect)
```

- `Bytes48` is a 48-byte hexadecimal string, prefixed with `0x`.
- `CellIndex` is an unsigned 64-bit integer.
- `Cell` is a 2048-byte hexadecimal string, prefixed with `0x`.

All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with
`0x`.

## Condition

The `verify_cell_kzg_proof_batch` handler should verify that `commitments` are
correct KZG commitments to `cells` by using the cell KZG proofs `proofs`, and
the result should match the expected `output`. If any of the commitments or
proofs are invalid (e.g. not on the curve or not in the G1 subgroup of the BLS
curve), any cell is invalid (e.g. incorrect length or one of the 32-byte blocks
does not represent a BLS field element), or any `cell_index` is invalid (e.g.
greater than the number of cells for an extended blob), it should error, i.e.
the output should be `null`.
