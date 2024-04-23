# Test format: Recover all cells

Recover all cells given at least 50% of the original `cells`.

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input:
  cell_ids: List[CellID] -- the cell identifier for each cell
  cells: List[Cell] -- the partial collection of cells
output: List[Cell] -- all cells, including recovered cells
```

- `CellID` is an unsigned 64-bit integer.
- `Cell` is a 2048-byte hexadecimal string, prefixed with `0x`.

All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with `0x`.

## Condition

The `recover_all_cells` handler should recover missing cells, and the result should match the expected `output`. If any cell is invalid (e.g. incorrect length or one of the 32-byte blocks does not represent a BLS field element) or any `cell_id` is invalid (e.g. greater than the number of cells for an extended blob), it should error, i.e. the output should be `null`.
