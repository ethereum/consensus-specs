# Test format: Compute verify cell KZG proof batch challenge

Compute the challenge value used for batch verification of cell KZG proofs.

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input:
  commitments: List[Bytes48] -- the unique KZG commitments
  commitment_indices: List[CommitmentIndex] -- the commitment index for each cell
  cell_indices: List[CellIndex] -- the cell index for each cell
  cosets_evals: List[CosetEvals] -- the coset evaluations for each cell
  proofs: List[Bytes48] -- the KZG proof for each cell
output: Bytes32 -- the computed challenge value
```

- `Bytes48` is a 48-byte hexadecimal string, prefixed with `0x`.
- `Bytes32` is a 32-byte hexadecimal string, prefixed with `0x`.
- `CommitmentIndex` is an unsigned 64-bit integer.
- `CellIndex` is an unsigned 64-bit integer.
- `CosetEvals` is a list of field elements, each encoded as a 32-byte
  hexadecimal string prefixed with `0x`.

All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with
`0x`.

## Condition

The `compute_verify_cell_kzg_proof_batch_challenge` handler should compute a
challenge value by hashing together all the inputs according to the Fiat-Shamir
heuristic. This is an internal helper function, so all inputs are assumed to be
valid. The computed challenge should match the expected `output`.

Note: This function is not a public method but an internal helper used by
`verify_cell_kzg_proof_batch`. It assumes all inputs are already validated.
