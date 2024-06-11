# Test format: Recover cells and KZG proofs

Recover all cells/proofs given at least 50% of the original `cells` and `proofs`.

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input:
  cell_ids: List[CellID] -- the cell identifier for each cell
  cells: List[Cell] -- the partial collection of cells
output: Tuple[List[Cell], List[KZGProof]] -- all cells and proofs
```

- `CellID` is an unsigned 64-bit integer.
- `Cell` is a 2048-byte hexadecimal string, prefixed with `0x`.
- `KZGProof` is a 48-byte hexadecimal string, prefixed with `0x`.

All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with `0x`.

## Condition

The `recover_cells_and_kzg_proofs` handler should recover missing cells and proofs, and the result should match the expected `output`. If any cell is invalid (e.g. incorrect length or one of the 32-byte blocks does not represent a BLS field element), any proof is invalid (e.g. not on the curve or not in the G1 subgroup of the BLS curve), or any `cell_id` is invalid (e.g. greater than the number of cells for an extended blob), it should error, i.e. the output should be `null`.
