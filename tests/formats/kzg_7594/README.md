# KZG tests for EIP-7594

A test type for KZG libraries. Tests all the public interfaces that a KZG library is required to implement for EIP-7594, as defined in `polynomial-commitments-sampling.md`.

We do not recommend rolling your own crypto or using an untested KZG library.

The KZG test suite runner has the following handlers:

- [`compute_cells`](./compute_cells.md)
- [`compute_cells_and_kzg_proofs`](./compute_cells_and_kzg_proofs.md)
- [`verify_cell_kzg_proof`](./verify_cell_kzg_proof.md)
- [`verify_cell_kzg_proof_batch`](./verify_cell_kzg_proof_batch.md)
- [`recover_all_cells`](./recover_all_cells.md)
