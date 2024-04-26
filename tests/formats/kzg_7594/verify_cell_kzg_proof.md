# Test format: Verify cell KZG proof

Use the cell KZG `proof` to verify that the KZG `commitment` for a given `cell` is correct.

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input:
  commitment: Bytes48 -- the KZG commitment
  cell_id: CellID -- the identifier for the cell
  cell: Cell -- the cell
  proof: Bytes48 -- the KZG proof for the cell
output: bool -- true (correct proof) or false (incorrect proof)
```

- `Bytes48` is a 48-byte hexadecimal string, prefixed with `0x`.
- `CellID` is an unsigned 64-bit integer.
- `Cell` is a 2048-byte hexadecimal string, prefixed with `0x`.

All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with `0x`.

## Condition

The `verify_cell_kzg_proof` handler should verify that `commitment` is a correct KZG commitment to `cell` by using the cell KZG proof `proof`, and the result should match the expected `output`. If the commitment or proof is invalid (e.g. not on the curve or not in the G1 subgroup of the BLS curve), `cell` is invalid (e.g. incorrect length or one of the 32-byte blocks does not represent a BLS field element), or `cell_id` is invalid (e.g. greater than the number of cells for an extended blob), it should error, i.e. the output should be `null`.
