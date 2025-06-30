# KZG tests

A test type for KZG libraries. Tests all the public interfaces that a KZG
library required to implement EIP-4844 needs to provide, as defined in
`polynomial-commitments.md`.

We do not recommend rolling your own crypto or using an untested KZG library.

The KZG test suite runner has the following handlers:

- [`blob_to_kzg_commitment`](./blob_to_kzg_commitment.md)
- [`compute_kzg_proof`](./compute_kzg_proof.md)
- [`verify_kzg_proof`](./verify_kzg_proof.md)
- [`compute_blob_kzg_proof`](./compute_blob_kzg_proof.md)
- [`verify_blob_kzg_proof`](./verify_blob_kzg_proof.md)
- [`verify_blob_kzg_proof_batch`](./verify_blob_kzg_proof_batch.md)
